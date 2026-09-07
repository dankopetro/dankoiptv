# Dankoiptv / Danko TV — Contexto del Proyecto (para cualquier IA)

**Regla de oro:** leer este archivo COMPLETO antes de tocar nada. Todo lo documentado acá
fue verificado empíricamente (probado en vivo contra IPTV real) o aprendido por errores
propios durante el desarrollo. NO repetir errores ya probados.

Última actualización: 06/09/2026 (web Vercel en raíz + copia `web/`)

---

## 0. Estado ACTUAL del proyecto

- **Danko TV 0.1** (`0.1-20260906-1914`): shell nuevo PyQt6 funcional, en pruebas del usuario.
- **GitHub**: `https://github.com/dankopetro/dankoiptv.git` (rama `main`). Push solo cuando
  el usuario lo pida. El sitio Vercel sirve el `index.html` de la **raíz** del repo:
  no moverlo ni reemplazarlo por otra app; hay una copia de trabajo en `web/index.html`.
- **Últimos builds válidos** (en la raíz del repo, generados por `./build-dankotv.sh`):
  - `dankotv-0.1-20260906-1914-x86_64.AppImage` (864K) ← **el bueno para probar**
  - `../dankotv_0.1-20260906-1914_all.deb` (52K)
  - Symlink estable: `./dankotv-x86_64.AppImage` → siempre apunta al último build
- **Pendiente de prueba por el usuario** (build 1914): que el cartel "Cargando lista..."
  se cierre solo al terminar la descarga (ver §6.2 para el detalle del bug corregido).

### Qué es cada cosa (tres superficies en el mismo repo)
1. **Dankoiptv** (`usr/lib/dankoiptv/`, builds `1.1g-*`): el MOTOR base — proyecto propio
   (Python/PyQt6 + libmpv embebido). Monolito completo con EPG, grabación, catchup, editor
   de listas, multi-EPG, MPRIS, i18n. Es una app completa por sí misma y TAMBIÉN es la
   librería que usa Danko TV (M3UParser, XTream, binding mpv).
2. **Danko TV** (`dankotv/`, builds `0.1-*`): el SHELL nuevo, modular, la app del futuro.
   Ventana integrada con libmpv, sin ventanas separadas. Reutiliza el motor base.
3. **Web (Vercel)** (`index.html` en la raíz + copia `web/index.html`): player IPTV en el
   navegador (HLS/DASH/mpegts + Cast). El deploy de Vercel espera el HTML en la raíz;
   `web/` es la copia para no perderla si se reorganiza el repo. No borrar `./index.html`.

---

## 1. Historia y decisiones (por qué es así)

### Origen (sesión 23/08/2026)
- Se investigaron a fondo dos arquitecturas: **reproductor Python/PyQt6 + libmpv embebido**
  vs **open-tv** (Fredolx, Rust/Tauri + mpv externo). Se probó en producción (laptop danko,
  TV) hasta lograr reconexión seamless real. Todas las lecciones empíricas en §4 y §5.
- Decisión de stack: **Python 3.12 + PyQt6 + libmpv embebido** (ventana integrada, control
  total de eventos) — NO mpv externo como Fred (ventana separada, sin control).

### Nombres y versiones
- Proyecto 100% propio bajo nombre "Dankoiptv": `grep -ri yuki` en código/UI = 0
  resultados. Licencia GPL-3.0.
- Esquema de versiones (`./version.sh`): `0.<minor>-AAAAMMDD-HHMM`.
  - minor = meses desde sep-2026 + 1 (sep-2026 → 0.1, oct-2026 → 0.2, ...)
  - major = años desde 2026 (2027 → 1.0)
  - Modo legacy: `./version.sh dankoiptv` → `1.1g-fecha` (línea 1.x del motor)
- Inyección de versión: placeholder `__DANKOTV_VERSION__` en `dankotv/__init__.py`; el build
  lo reemplaza por sed SOLO en la copia empaquetada (`build-dankotv.sh`, función `inject`).

### Llaves del shell Danko TV (sesión 06/09/2026)
- Shell nuevo creado en `dankotv/` (commit `2c2267b`): pantalla Mis listas, layout declarativo,
  12 skins naranjas/dark, logo propio (TV+carita+antenas, `dankotv/assets/`).
- Flujo decidido por el usuario: la app abre DIRECTO en la ventana principal (sin Home
  intermedio); si no hay listas guardadas, lanza mini menú "Nueva lista" automático
  (`QTimer.singleShot(400, main.add_list)` en `app.py:74`).
- Modo **pantalla completa**: doble clic sobre el video, botón ⛶, F11 o Esc
  llaman `QMainWindow.showFullScreen()` (cubre el monitor, no solo la ventana). Lista y
  barra de controles se reparentan a shells frameless (`X11BypassWindowManagerHint`,
  opacidad 0.75) porque libmpv pinta encima de widgets Qt hermanos. La lista en FS usa
  además `Popup` y foco en el buscador: sin eso el teclado no llega (X11 Bypass). Un
  QTimer 100 ms lee
  `QCursor.pos()`: solo si el cursor está en el borde izquierdo aparece la lista; solo si
  está sobre el rectángulo de la barra (centrada abajo) aparecen los controles. Fuera de
  esas zonas no se muestra nada. Cursor en blanco tras ~1 s quieto. OSC de mpv se apaga en FS.

---

## 2. Estructura del repo

```
Dankoiptv/
├── AGENTS.md              ← este archivo
├── README.md, ROADMAP.md, COPYING (GPL-3.0)
├── index.html             ← web app Vercel (NO mover: el deploy apunta a la raíz)
├── web/index.html         ← copia de la misma web (editar las dos o sincronizar)
├── version.sh             ← generador de versión (ver §1)
├── build-dankotv.sh       ← builder .deb + AppImage de Danko TV (ver §3)
├── build-appimage.sh      ← builder legacy del motor 1.x
├── appimagetool-x86_64.AppImage  ← empaquetador (NO extraer a la raíz: ver §6.3)
├── dankotv/               ← SHELL Danko TV 0.1 (la app nueva, ~1200 líneas)
│   ├── app.py             ← entry point: QApplication, wiring home↔main, flujo inicial
│   ├── home.py            ← HomeWindow (Mis listas) + NewListDialog + load_spec() + _Bridge
│   ├── mainview.py        ← MainWindow: video embebido + lista canales + menús + toolbar
│   ├── player.py          ← SeamlessPlayer: libmpv embebido + motor seamless (§5)
│   ├── engine.py          ← load_m3u()/load_xtream() sobre el motor base; ensure_engine_path()
│   ├── config.py          ← ~/.config/dankotv/ (lists.json + settings.json)
│   ├── layout.py          ← MENUS/TOOLBAR declarativos (labels + slots por nombre)
│   ├── skins.py           ← 12 skins + fuentes (apply_look)
│   └── assets/            ← logo-256.png, logo-512.png, dankotv.svg, main.png
├── usr/lib/dankoiptv/     ← MOTOR base (app 1.x Y librería del shell)
│   ├── dankoiptv.py       ← entry del motor (~6300 líneas, monolito)
│   ├── dankoiptv_lib/     ← 33 módulos: playlist, EPG, gui, record, xtream, mpris...
│   └── thirdparty/        ← mpv.py (binding libmpv ctypes) + xtream.py
├── usr/share/dankoiptv/   ← iconos del motor (icons/ + icons_dark/)
├── po/                    ← fuentes de traducción (dankoiptv-*.po)
└── debian/                ← empaquetado legacy del motor
```

### Config del usuario
- Shell Danko TV: `~/.config/dankotv/` (lists.json, settings.json)
  - settings: `skin`, `font_family`, `last_list`, `last_group`, `cache_secs` (default 45),
    `favorites` (`{nombre_lista: [urls]}`)
- Motor 1.x: `~/.config/dankoiptv/`

---

## 3. Build (cómo se construye)

```bash
./build-dankotv.sh          # construye TODO: .deb + AppImage, versión auto por fecha
./version.sh                # versión actual del shell (0.x) — ./version.sh dankoiptv = 1.1g
python3 -m py_compile dankotv/*.py   # validar sintaxis antes de build (HACERLO SIEMPRE)
```
- Salidas: `.deb` en la raíz del repo (`dankotv_<ver>_all.deb` + symlink `dankotv_all.deb`)
  y copia en `../dankotv_<ver>_all.deb`. El .deb depende del paquete `dankoiptv` + python3-pyqt6 +
  libmpv2 + mpv. AppImage: `dankotv-<ver>-x86_64.AppImage` (autocontenido: motor + shell +
  traducciones + iconos). Symlink `dankotv-x86_64.AppImage` → último build.
- `dankotv/VERSION.txt` se actualiza en cada build (es un artefacto, no editar a mano).
- Probar desde fuente sin build: `python3 dankotv/app.py` (necesita deps PyQt6/requests/
  libmpv2 instaladas y resuelve el motor desde `usr/lib/dankoiptv/` del repo).
- AppImage en esta máquina: FUSE a veces falla ("mount failed: Operation not permitted") →
  extraer con `--appimage-extract` y correr `squashfs-root/AppRun` (PERO ver §6.3 si el
  squashfs-root extraído era el appimagetool).

### Dependencias runtime
`python3-pyqt6 python3-requests libmpv2 mpv` (el motor 1.x además: python3-gi, python3-chardet,
ffmpeg). En la laptop danko todo está ya instalado.

---

## 4. Lecciones EMPÍRICAS del motor de reproducción (¡NO ignorar!)

Probadas en vivo contra el proveedor IPTV real del usuario (Xtream, playlist M3U de 88 MB,
347.171 canales, 310 grupos; descarga ~26s; algunos canales con encoders rotos que cortan
cada 18-30s y mandan PTS de audio hacia atrás).

### Opciones mpv — PROHIBIDAS vs OBLIGATORIAS en live
| Opción | Veredicto | Motivo |
|---|---|---|
| `stream-lavf-o=reconnect*` | ❌ PROHIBIDA | ffmpeg reconecta y el servidor retoma desde un punto anterior → **rebobina 10-15s** |
| `prefetch-playlist=yes` | ❌ PROHIBIDA | pre-abre 2ª conexión vieja → **rebobina ~10s**; duplica conexiones |
| `force_seekable=True` en live | ❌ PROHIBIDA | con PTS rotos, mpv hace seeks hacia atrás visibles |
| `keep_open=yes` + `keep_open_pause=no` | ✅ | al EOF congela en último frame (cero negro) |
| `loop_playlist="no"` + manejo propio del EOF | ✅ | loop sin control causaba cascadas |
| `cache_secs=45` (configurable) | ⚠️ útil | absorbe micro-cortes de red, NO cortes de origen |

Retraso de ~1–3 min respecto a la TV de aire/cable: casi siempre es el live edge del
proveedor (transcodificador Xtream / ventana HLS). Nuestro cache (45 s) no explica 3 min.
No se puede "adelantar" un `.ts` Xtream más allá de lo que el servidor está emitiendo.

### Algoritmo seamless vigente (implementado en `dankotv/player.py`)
1. Observador de propiedad `eof-reached` (con keep-open, `end-file` ya NO se dispara en EOF)
2. EOF → si el anterior fue hace <20s: `cascade += 1`, si no `cascade = 0`; delay = `min(cascade*2, 8)`s;
   recarga con `mpv.play(url)` (loadfile replace, MISMA instancia/ventana) tras el delay
3. `file-loaded` resetea `_err_retries` y `_cascade`
4. Errores reales (`end-file` reason `error`): backoff exponencial 2^n cap 30s, máx 10 reintentos
5. Al parar (`stop()`): restaurar `keep_open=False` (si no, el logo en pausa loopea)
6. VOD/catchup: `keep_open=False`, `force_seekable=True` (seek normal)

### Flujo de eventos Qt/libmpv (CRÍTICO)
- Los callbacks de libmpv llegan en el hilo del event handler de mpv (NO el hilo Qt).
- Cualquier cosa que toque la GUI debe reenviarse al hilo Qt. En el shell: `QTimer.singleShot(0, cb)`.
- La instancia mpv se crea UNA sola vez y se reutiliza; la reconexión NUNCA recrea la instancia.

---

## 5. Motor base: datos útiles

- `usr/lib/dankoiptv/thirdparty/mpv.py` — binding libmpv via ctypes (fork del python-mpv):
  maneja el hilo de eventos, property_observer, event_callback, on_key_press, overlays.
- `usr/lib/dankoiptv/thirdparty/xtream.py` — cliente Xtream (login player_api.php, catchup).
- `dankoiptv_lib/playlist_m3u.py` M3UParser, `requests_timeout.py` (timeout TOTAL de descarga
  vía sys.settrace — el timeout nativo de requests NO cubre tiempo total; para playlists
  gigantes usar ≥120s), `record.py` (ffmpeg con -reconnect* — en grabación SÍ sirve).
- Historial del motor 1.x: versiones de prueba `1.1g-*`, muchos fixes de mpv en AppImage
  (LD_LIBRARY_PATH, rutas absolutas antes que find_library, LC_NUMERIC=C antes de importar
  mpv para silenciar warnings). Ver `git log --oneline` para detalle.

---

## 6. Errores YA COMETIDOS y lecciones de desarrollo (no repetir)

### 6.1 Bug de hilos Qt — el cartel "Cargando lista" que no se cerraba (06/09/2026)
**Síntoma:** la lista terminaba de cargar y se veían los canales, pero el QMessageBox
"Cargando lista" quedaba clavado encima, bloqueando toda la app.
**Causa raíz:** el callback que hacía `box.close()` corría en el **hilo de descarga**
(threading.Thread), no en el hilo principal de Qt. Qt ignora silenciosamente las
operaciones de widgets desde hilos secundarios.
**Fix (vigente):** clase `_Bridge` en `dankotv/home.py` — el QObject vive en el hilo
principal, conecta su señal `done` a SU PROPIO slot `_handle`; al emitirse desde el hilo
worker, Qt usa conexión encolada automáticamente y `_handle` → callback SIEMPRE corre en
el hilo principal. Patrón a usar para TODO trabajo en background con UI:
```python
bridge = _Bridge(on_done, self)          # on_done corre en hilo Qt principal
def work(): ... bridge.done.emit((ok, ch, gr, err))   # en threading.Thread
```
Aplicado en: `load_spec()`, `test_connection()`, `load_and_store()` (home.py) y
`reload_list()` (mainview.py). Verificado con test: callback corre en hilo principal.
**Nunca conectar señales a closures libres si se emiten desde otro hilo.**

### 6.2 Fixes de UI triviales pero importantes
- QMessageBox de error de carga: usar `setStandardButtons(Ok)` + auto-cierre con
  `QTimer.singleShot(5000, msg.close)` — nunca `NoButton` solos, ni modales bloqueantes.
- El timer de 5s de fallback sobre el cartel de carga fue REMOVIDO: habría cortado
  descargas largas (la playlist del usuario tarda ~26s+).
- Al editar imports de un archivo PyQt, verificar con `py_compile` Y con un import real:
  una vez rompí `mainview.py` quitando `pyqtSignal` de más → `NameError` al arrancar la
  AppImage (build 1910, corregido en 1914).

### 6.3 appimagetool y squashfs-root — TRAMPA conocida
- `build-dankotv.sh` usa `./squashfs-root/AppRun` como appimagetool (extraído una vez de
  `appimagetool-x86_64.AppImage`, está en .gitignore).
- **PERO** extraer la AppImage de DANKO TV con `--appimage-extract` en la raíz del repo
  SOBREESCRIBE ese squashfs-root con la app (AppRun = Danko TV) → el build siguiente
  LARBZA LA APP en vez de empaquetar ("The X11 connection broke", ventanas que se abren).
- Síntoma: `./build-dankotv.sh` termina en "The X11 connection broke (error 1)".
- Solución: `rm -rf squashfs-root && ./appimagetool-x86_64.AppImage --appimage-extract`
  (restaura el tool). Verificar: `./squashfs-root/AppRun --version` debe decir
  "appimagetool, continuous build...".
- Si se quiere extraer una AppImage de la app para debug, hacerlo en /tmp, NUNCA en la raíz.

### 6.4 Cosas verificadas sobre AppImage/deb del shell
- PYTHONPATH del AppRun: `${HERE}/usr/lib:${HERE}/usr/lib/dankoiptv` — el shell importa el
  motor desde ahí (`ensure_engine_path()` en engine.py también lo resuelve solo).
- El .deb del shell DEPENDE del paquete `dankoiptv` (el motor) — instalar ambos para probar deb.
- AppImage necesita libmpv del sistema (no la bundlea): `sudo apt install libmpv2 mpv`.

---

## 7. Entorno (máquinas)

- **claudio** (donde se desarrolla): Linux Mint 22.3, i9-11900H, Python 3.12.3. Repositorio
  en `~/Projects/Dankoiptv`. AppImages de prueba NO se pueden lanzar con GUI desde la
  terminal de opencode en esta máquina de forma confiable (FUSE/X11); probar desde el
  gestor de archivos o `./dankotv-x86_64.AppImage` en una terminal del usuario.
- **danko** (192.168.0.200, user `danko`, SSH con clave BatchMode OK): laptop conectada al
  TV, donde SE USA el IPTV. Python 3.12.3 sistema, mpv 0.37.0, Qt 6.4.2 (xcb), pipewire.
  Corre el reproductor parcheado en `~/yuki-iptv/` (referencia del motor seamless que FUNCIONA;
  backup `yuki-iptv.py.bak-20260823`).

### Clones de referencia (en /tmp, re-clonar si no existen)
```bash
git clone --depth 1 https://github.com/itachi-re/yuki-iptv.git /tmp/opencode/yuki-iptv
git clone --depth 1 https://github.com/Fredolx/open-tv.git /tmp/opencode/open-tv
```
- reproductor base: `usr/lib/yuki-iptv/yuki-iptv.py` (doPlay ~1346, init_mpv_player ~1573,
  do_reconnect/end_file_error_callback ~4329-4408, check_connection ~5411)
- open-tv: `src-tauri/src/mpv.rs` (get_play_args 143-206), `restream.rs`, `utils.rs`
  (handle_max_streams). Licencia GPL-2.0: SOLO ideas, NO copiar código (incompatible).

---

## 8. Proceso de trabajo acordado con el usuario

1. **El usuario prueba SIEMPRE los builds** (AppImage/deb) en su máquina — no esperar que
   la IA "abra la app" para validar: la app es GUI y el usuario la valida en su escritorio.
   Reconstruir .deb + AppImage tras CADA cambio que el usuario deba probar.
2. Antes de entregar un build: `python3 -m py_compile dankotv/*.py` + import real de los
   módulos (una vez un build llegó roto por un import — §6.2).
3. El usuario prefiere respuestas en **español**, directas y cortas.
4. Sin push a GitHub hasta que el usuario lo pida (todo es commit local hasta ahora).
5. Tras cada fix funcional verificado, commit con mensaje estilo git log existente.
6. Ante cambios de comportamiento de reproducción, actualizar AGENTS.md (este archivo) —
   es la memoria del proyecto para futuras sesiones/IA.

---

## 9. Roadmap (lo acordado)

- **0.1 (actual)**: shell nuevo funcional + motor seamless + skins + pantalla completa +
  fix del cartel de carga (pendiente de validación del usuario).
- **0.2+**: migrar a mpv externo + IPC JSON (mismo wid, mismos observers, crash-aislado);
  grabación en el shell (ffmpeg con -reconnect*); EPG + catchup en el shell; gestión de
  límite de conexiones simultáneas (idea de open-tv handle_max_streams); telemetría de
  salud del stream (solo métricas/UI, NUNCA reconectar por paused-for-cache).
- **Investigación pendiente**: salidas de video modernas post-Qt (render API
  OpenGL/Vulkan, compositor propio, overlays GPU) sin perder keep-open + eof-reached +
  cascade.
