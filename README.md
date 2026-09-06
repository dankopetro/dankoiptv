# Dankoiptv

Reproductor IPTV para Linux (Mint 22.3+) con EPG, Xtream API, grabación,
catchup, multi-EPG y MPRIS.

## Diferencias propias
- **Motor seamless**: keep-open + observador `eof-reached` + backoff en
  cascada para live (sin pantallas negras ni rebobinados).
- **Skins**: 7 temas oscuros (naranja por defecto) en Ajustes → GUI.
- **Fuente**: Ubuntu Medium con fallback Noto Sans.
- **Doble clic** sobre el video alterna pantalla completa.

## Estructura
- `usr/lib/dankoiptv/dankoiptv.py` — entry point
- `usr/lib/dankoiptv/dankoiptv_lib/` — 33 módulos (playlist, EPG, GUI...)
- `usr/lib/dankoiptv/thirdparty/` — binding libmpv + cliente Xtream
- `usr/share/dankoiptv/` — iconos, `usr/share/locale/` — traducciones (.mo)
- `po/` — fuentes de traducción

## Versiones de prueba 1.x
Cada build test se versiona `1.1g`, `1.1h`... con fecha (`VERSION`):
- `.deb`: `../dankoiptv_1.1g-20260906-1610_all.deb`
- AppImage: `dankoiptv-1.1g-20260906-1610-x86_64.AppImage`

## Build local (sin subir a GitHub hasta probar)
```bash
dpkg-buildpackage -us -uc -b   # .deb
./build-appimage.sh            # AppImage
```

## Instalación
```bash
sudo apt install ./../dankoiptv_1.1g-20260906-1610_all.deb
# deps: ffmpeg libmpv2 mpv python3-gi python3-pyqt6 python3-chardet python3-requests
```

## Licencia
GPL-3.0 (ver `COPYING`)
