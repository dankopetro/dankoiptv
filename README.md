# Danko TV

Reproductor IPTV propio para Linux (Mint 22.3+) con reconexión seamless
(sin pantallas negras ni rebobinados), 12 skins naranjas/dark y logo propio.

## Las tres superficies

1. **Danko TV** (`dankotv/`, versión 0.x): la app de escritorio — shell PyQt6
   modular con video libmpv embebido, pantalla Mis listas, pantalla completa,
   favoritos, menús contextuales. Reutiliza el motor base.
2. **Motor Dankoiptv** (`usr/lib/dankoiptv/`, versión 1.1g): librería y app
   completa con EPG, grabación, catchup, editor de listas, multi-EPG, MPRIS,
   i18n. El shell lo usa (M3UParser, XTream, binding mpv).
3. **Danko TV Web** (`index.html`, deploy Vercel): player IPTV en el navegador
   (HLS/DASH/mpegts + Cast). Hay copia de trabajo en `web/index.html`
   (mantener sincronizadas).

## Características
- **Motor seamless**: keep-open + observador `eof-reached` + backoff en
  cascada para live (congela en el último frame en vez de negro).
- **12 skins** naranjas/dark + fuentes (Ubuntu/Noto/Inter/Cantarell/DejaVu).
- **Pantalla completa**: doble clic, botón ⛶, F11 o Esc.
- **Favoritos** por lista, búsqueda y filtro por grupo.
- M3U (URL) y Xtream API (host/usuario/clave).

## Instalación (laptop con Mint 22.3+)
```bash
sudo apt install ./dankotv_0.1-<fecha>_all.deb
# o la AppImage (autocontenida):
./dankotv-0.1-<fecha>-x86_64.AppImage
# deps del sistema: python3-pyqt6 python3-requests libmpv2 mpv
```
El `.deb` es autocontenido (incluye el motor); no necesita otro paquete.
La AppImage también es autocontenida y no necesita instalación.

## Build (desarrolladores)
```bash
./build-dankotv.sh          # .deb + AppImage, versión auto por fecha (./version.sh)
python3 -m py_compile dankotv/*.py   # validar antes de build
python3 dankotv/app.py      # probar desde fuente
```
Detalle de arquitectura, lecciones empíricas y proceso: ver `AGENTS.md`.
Roadmap: ver `ROADMAP.md`.

## Licencia
GPL-3.0 (ver `COPYING`)
