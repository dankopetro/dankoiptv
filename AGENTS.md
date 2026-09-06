# Dankoiptv - Project Context

## Qué es esto
Reproductor IPTV propio (nombre de trabajo: **Dankoiptv**) construido con "lo mejor de ambos mundos":
**yuki-iptv** (Python/PyQt6 + libmpv embebido) y **open-tv / "FredTV"** (Fredolx, Rust/Tauri + mpv
proceso externo). Esta sesión (23/08/2026, desde ~11:53) investigó a fondo ambos proyectos, parchó
yuki-iptv en producción hasta lograr reconexión seamless, y verificó empíricamente qué enfoques
funcionan y cuáles NO. Todo ese conocimiento se volca acá para no perderlo.

**Estado al cerrar esta sesión:** el parche de reconexión seamless está funcionando en producción
en la laptop danko (conectada al TV). El proyecto Dankoiptv aún no tiene código — arranca en una
nueva sesión.

---

## 1. Investigación: cómo funciona cada proyecto

### yuki-iptv (https://github.com/itachi-re/yuki-iptv) — GPL-3.0
Lenguaje: Python. Rama main. Fork comunitario mantenido por itachi-re.

**Arquitectura de reproducción:**
- **libmpv embebido vía ctypes** — fork del binding python-mpv en `usr/lib/yuki-iptv/thirdparty/mpv.py`
- Video embebido en la ventana Qt con la opción `wid` (winId del contenedor)
- Eventos de libmpv procesados en hilo daemon interno (`MPVEventHandlerThread`) y reenviados al
  hilo Qt vía `execute_in_main_thread()` (señal pyqtSignal que transporta un `functools.partial`)
  — ver `yuki_iptv/threads.py`
- La instancia mpv se crea UNA sola vez (`init_mpv_player()`) y se reutiliza para todo (TV, VOD,
  logo en pausa). La reconexión NUNCA recrea la instancia: es `loadfile(url, 'replace')`
- Código principal monolítico: `usr/lib/yuki-iptv/yuki-iptv.py` (~266KB, 6187 líneas)
- Opciones base en el dict `options` (~línea 4212): `osc=True, hwdec="no", ytdl=False,
  force-window=True, force-seekable=True, wid=..., loglevel=info, script-opts=osc-layout=slimbox...`
- Settings en JSON: `~/.config/yuki-iptv/settings.json` (clave `cache_secs` 0-120, default 0;
  `autoreconnection` default False; `mpv_options` string libre de overrides)

**Mecanismo de reconexión ORIGINAL (el malo):**
- Detectores: evento `end_file` con reason `error` + poller QTimer de 100ms que chequea
  `cache_buffering_state == 0` (buffer agotado al 100%)
- Acción: overlay "Playing error" + delay FIJO (1s o 5s) + `doPlay()` = `loadfile(replace)`
  → teardown completo de demuxer + reconexión TCP + re-apertura = **freeze/negro visible garantizado**
- Sin límite de reintentos ni backoff; default apagado; solo modo TV (`playing_group == 0`)
- NO configura ninguna opción de reconexión de red en playback (su grabador ffmpeg sí usa
  `-reconnect*`, pero el player no)

### open-tv / FredTV (https://github.com/Fredolx/open-tv) — GPL-2.0
Lenguaje: **Rust** (reescrito desde Python/Electron; antes era Electron). 3990 estrellas.

**Arquitectura de reproducción:**
- **mpv como proceso EXTERNO** (`tokio::process::Command` en `src-tauri/src/mpv.rs`), SIN IPC:
  no observa propiedades, no lee eventos. Solo captura stdout por si mpv muere con error
- UI: Tauri 2 + Angular; la ventana de video es la ventana nativa de mpv, separada de la app
- **CERO lógica de reconexión en la app.** No hay watchdog, polling, ni handlers de eventos

**EL TRUCO (toda la magia son 2 flags de CLI):**
```
mpv <url> --prefetch-playlist=yes --loop-playlist=inf     [solo para livestreams]
```
- La playlist de mpv tiene UNA entrada (la URL). Al EOF, el motor de playlist de mpv avanza a la
  siguiente entrada (= misma URL) **dentro del mismo proceso y la misma ventana**: no destruye
  nada, mantiene el último frame en pantalla → transición sin negro
- Historial git relevante (verificado en el repo): el autor PROBÓ PRIMERO
  `--keep-open=yes --keep-open-pause=no --stream-lavf-o=reconnect_streamed=1,reconnect_at_eof=1...`
  (commit `dfc0dfb` "stream-keep-open") y LO ABANDONÓ al día siguiente por
  `prefetch-playlist + loop-playlist` (commit `b71330f`), porque el reconnect de ffmpeg/lavf no
  cubre todos los tipos de corte (playlist HLS 404, errores de demuxer)

---

## 2. Lecciones EMPÍRICAS (verificadas en pruebas reales con IPTV en producción)

Estas son las joyas de la sesión — cada una fue probada en vivo sobre canales reales del proveedor:

| # | Experimento | Resultado | Conclusión |
|---|---|---|---|
| 1 | `stream-lavf-o=reconnect=1,reconnect_streamed=1,reconnect_on_network_error=1,reconnect_delay_max=5` | ❌ **Rebobinados de 10-15s**: en streams lineales (TS/HTTP), al cortarse la conexión ffmpeg reconecta y el servidor RETOMA desde un punto anterior de su buffer → el contenido rebobina → PTS de audio saltan atrás → "Reset playback" | NO usar lavf-reconnect en playback IPTV. Coincide con que el autor de open-tv lo abandonara |
| 2 | `prefetch-playlist=yes` con playlist de 1 entrada en loop | ❌ **Rebobinados de ~10s**: mpv pre-abre una 2ª conexión ANTES del corte; al avanzar salta a esa conexión vieja cuyo contenido empezó minutos atrás | Prefetch en playlist de entrada única = máquina de rebobinar. Además duplica conexiones (riesgo con paneles que limitan conexiones simultáneas) |
| 3 | `loop-playlist=inf` SOLO (sin prefetch, sin lavf) | ✅ **El punto dulce**: corte → congelamiento de ~2s en el último frame → recupera saltando ~5s hacia ADELANTE (lo que duró el congelamiento, no pierde contenido previo) | Mecanismo base recomendado |
| 4 | `force-seekable=True` (default de Yuki) en live | ❌ Con proveedores que mandan PTS de audio rotos, mpv hace seeks hacia atrás visibles | Para live: `force_seekable=False`. Para VOD/catchup: True (necesita seek) |
| 5 | Cache grande (`cache_secs=45`) | ⚠️ Matiz: absorbe cortes de RED (datos dejan de llegar pero conexión vive), pero NO absorbe `end-file (reason: eof)` cuando la FUENTE termina el stream | Cache sí, pero no resuelve cortes de origen |
| 6 | keep-open + eof-reached + backoff en cascada | ✅ Implementado al final (última iteración) — congela en el último frame y dosifica recargas cuando el codificador del proveedor está en cascada | En prueba al cierre de la sesión |

**Características del proveedor IPTV del usuario (Xtream API, catchup 7 días):**
- Playlist M3U de **88 MB, 347.171 canales, 310 grupos** (tarda ~26s en descargar → el timeout
  default de 20s de yuki-iptv era insuficiente, se parchó a 120s en `requests_timeout.py`)
- Algunos canales (sobre todo deportes en vivo 720p59.94) tienen **encoders rotos**:
  - PTS de audio saltan atrás 10-15s cada ~20s → mpv: "Invalid audio PTS" +
    "Reset playback due to audio timestamp reset" (con force-seekable esto rebobina contenido)
  - El stream TERMINA cada ~18-30s (`end-file reason: eof`) → ciclo infinito de cortes
  - Tras un reinicio del encoder, las reconexiones inmediatas pueden cortar en cascada 2-3 veces
    hasta que una conexión se sostiene (~15-20s de buffer)
- Canales con feed sano: cortes esporádicos, el mecanismo seamless los resuelve en 2-3s

---

## 3. El parche final que FUNCIONA en yuki-iptv (referencia para Dankoiptv)

Aplicado en `danko@192.168.0.200:~/yuki-iptv/usr/lib/yuki-iptv/yuki-iptv.py`
(backup del original: `yuki-iptv.py.bak-20260823` junto al archivo).

### Opciones mpv para TV en vivo (la receta final):
```python
player.keep_open = True          # al EOF: congela en el último frame (cero negro)
player.keep_open_pause = False   # al EOF: stop en vez de pausa
player.loop_playlist = "no"      # el advance lo manejamos nosotros (loop causaba cascadas sin control)
player.force_seekable = False    # evita seeks hacia atrás por PTS rotos del proveedor
# NO usar: prefetch-playlist, stream-lavf-o reconnect* (ver lecciones 1 y 2)
# cache: settings → cache_secs=45 (absorbe micro-cortes de red)
```
Para VOD/catchup/archivo: `keep_open=False, force_seekable=True` (seek normal del archivo).

### Algoritmo de reconexión (manejo propio del EOF):
1. Observador de propiedad **`eof-reached`** (con keep-open ya NO se dispara `end-file` en EOF)
2. Al detectar EOF con seamless activo y playing_channel:
   - Si el EOF anterior fue hace <20s → `cascade += 1`; si no → `cascade = 0`
   - Delay = `min(cascade * 2, 8)` segundos
   - Recarga con `doPlay()` (= loadfile replace, misma instancia/ventana) tras el delay en un thread
3. `file_loaded` resetea el contador de reintentos de errores
4. Errores reales (`end-file` reason `error`): backoff exponencial 2^n cap 30s, máximo 10 reintentos,
   overlay "Playing error" solo si se rindió
5. Poller de `cache_buffering_state == 0` como ÚLTIMO recurso: 30s (antes 5s) antes de reload forzado
6. Al parar reproducción (`mpv_override_stop`): restaurar `keep_open=False` (si no, el logo
   main.png en pausa loopea)

### Flujo de eventos Qt/libmpv (crítico para no bloquear la GUI):
- Callbacks de mpv llegan en el hilo del event handler → SIEMPRE reenviar al hilo Qt con
  `execute_in_main_thread(partial(fn, args))`
- Los delays se hacen con `threading.Thread(target=..., args=(delay,), daemon=True)` que duerme y
  luego reinyecta al hilo Qt

---

## 4. Recomendaciones de diseño para Dankoiptv

### Stack sugerido (lo mejor de ambos):
- **Python 3.12 + PyQt6 + libmpv embebido** (como Yuki — ventana integrada, control total de
  eventos/propiedades) — NO proceso mpv externo como Fred (ventana separada, sin control)
- Estructura MODULAR (lección del monolito de 266KB de Yuki): separar player, playlist, xtream,
  epg, gui, reconnect
- Binding mpv: usar python-mpv actual o copiar el fork de Yuki (`thirdparty/mpv.py`) que ya
  resuelve ctypes y el hilo de eventos

### Motor de reproducción live (lo verificado):
```
Opciones base live:
  keep_open=yes, keep_open_pause=no, loop-playlist=no, force-seekable=no
  cache=auto, demuxer-readahead-secs=<configurable 0-120>, cache-secs=<ídem>
  user-agent / http-header-fields (referer/origin) configurables por playlist y por canal
VOD/catchup:
  keep_open=no, force-seekable=yes, save-position-on-quit (como Fred)
PROHIBIDOS (verificados empíricamente): prefetch-playlist, stream-lavf-o=reconnect*
```

### Reconexión:
- keep-open + observador `eof-reached` + backoff en cascada (algoritmo de la sección 3)
- Backoff exponencial para errores reales, con límite de reintentos
- Overlay de UI discreto durante recargas (nunca bloquear, nunca pantalla negra)

### Playlist / Xtream:
- Descarga con timeout TOTAL generoso (≥120s para playlists enormes) — el timeout de requests
  nativo solo cubre conexión/lectura entre bytes, NO tiempo total; técnica de Yuki:
  `sys.settrace` con trace_func que corta a los N segundos (ver `yuki_iptv/requests_timeout.py`)
- Xtream API: login → player_api.php con username/password; catchup-days; streams live con
  formato `http://host/usuario/pass/<id>`; EPG xmltv.gz
- Cachear la playlist parseada; 347k canales exigen modelo de datos eficiente (filtros por grupo,
  búsqueda incremental)

### Funciones a considerar (de ambos mundos + propias):
- De Yuki: EPG + catchup + grabación (ffmpeg con -reconnect*, ahí SÍ sirve) + editor de listas +
  Xtream API + i18n + MPRIS + multi-EPG
- De Fred: simplicidad y velocidad, gestión de límite de conexiones simultáneas
  (`handle_max_streams` mata el mpv más viejo vía CancellationToken), stream-record simultáneo
- Propias: telemetría de salud del stream (observar paused-for-cache/cache-buffering-state solo
  para métricas/UI, NUNCA para reconectar), perfiles por canal (UA/referer), quizá notificaciones

---

## 5. Entorno

### Máquinas
- **claudio** (esta): Linux Mint 22.3, i9-11900H, Python 3.12.3, donde se desarrolla
- **danko** (192.168.0.200, user `danko`): laptop conectada al TV — DONDE SE USA el IPTV
  - SSH con clave desde claudio (BatchMode OK): `ssh danko@192.168.0.200`
  - Python 3.12.3 sistema (`/usr/bin/python3`), pyenv 3.12.0 instalado pero yuki corre con
    python del sistema (pyenv local system en ~/yuki-iptv)
  - mpv 0.37.0, Qt 6.4.2 (xcb), pipewire
  - Yuki parcheado: `~/yuki-iptv/usr/lib/yuki-iptv/` (carpeta extraída de .deb, NO instalado como
    paquete). Lanzador: `/usr/bin/python3 ~/yuki-iptv/usr/lib/yuki-iptv/yuki-iptv.py`
  - Backup original del parche: `yuki-iptv.py.bak-20260823`

### Clones de referencia (en /tmp, pueden no existir — re-clonar si hace falta):
```bash
git clone --depth 1 https://github.com/itachi-re/yuki-iptv.git /tmp/opencode/yuki-iptv
git clone --depth 1 https://github.com/Fredolx/open-tv.git /tmp/opencode/open-tv
```
Archivos clave estudiados:
- yuki: `usr/lib/yuki-iptv/yuki-iptv.py` (doPlay ~1346, init_mpv_player ~1573, ready_handler_2
  ~1709, do_reconnect/end_file_error_callback ~4329-4408, check_connection ~5411),
  `yuki_iptv/requests_timeout.py`, `yuki_iptv/mpv_options.py`, `thirdparty/mpv.py`
- open-tv: `src-tauri/src/mpv.rs` (get_play_args 143-206), `src-tauri/src/restream.rs` (flags
  ffmpeg reconnect 59-83), `src-tauri/src/utils.rs` (handle_max_streams 186-204)

### Licencias
- yuki-iptv: GPL-3.0 → se puede fork/derivar (Dankoiptv sería GPL-3.0)
- open-tv: GPL-2.0 → tomar SOLO ideas/algoritmos, no copiar código (incompatible con GPL-3.0 sin
  cláusula "or later")

---

## 6. Estado del parche yuki (por si hay que tocarlo de nuevo)

Versiones del parche probadas en orden (todas en danko, la final es la vigente):
1. loop-playlist + prefetch + lavf-reconnect → rebobinados 10s (lavf) — DESCARTADO
2. loop-playlist + prefetch + no-force-seekable → rebobinados 10s (prefetch) — DESCARTADO
3. loop-playlist + no-force-seekable → bien (+5s adelante), pero cascadas sin control — OK parcial
4. **keep-open + eof-reached + cascade backoff + no-force-seekable → VIGENTE**

Logs de verificación (cómo saber qué versión corre):
- v4 actual: `Seamless reconnection enabled (keep-open + managed eof-reload + cascade backoff)`
- Cortes: `Stream EOF - seamless reload in Ns (cascade N)`

Comandos útiles danko:
```bash
# ver logs en vivo
/usr/bin/python3 ~/yuki-iptv/usr/lib/yuki-iptv/yuki-iptv.py
# rollback total
cp ~/yuki-iptv/usr/lib/yuki-iptv/yuki-iptv.py.bak-20260823 ~/yuki-iptv/usr/lib/yuki-iptv/yuki-iptv.py
# validar sintaxis remota
python3 -m py_compile ~/yuki-iptv/usr/lib/yuki-iptv/yuki-iptv.py
```
