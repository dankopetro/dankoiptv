# Dankoiptv

Reproductor IPTV para Linux (Mint 22.3+) construido con Python 3.12 + PyQt6 + libmpv embebido (ctypes).

## Características
- Reproducción con libmpv embebido (ventana integrada, control total de eventos)
- Reconexión seamless verificada en producción: keep-open + observador `eof-reached` + backoff en cascada
- Sin rebobinados: NO usa `prefetch-playlist` ni `stream-lavf-o=reconnect*` (verificado empíricamente)
- Soporte listas M3U masivas (timeout 120s) y Xtream API
- Búsqueda incremental de canales

## Requisitos (deb)
- python3-pyqt6
- libmpv2
- python3-requests

## Instalación (deb)
```bash
sudo apt install ./dankoiptv_1.0.0-1_all.deb
```

## AppImage
```bash
chmod +x dankoiptv-x86_64.AppImage
./dankoiptv-x86_64.AppImage
```
(Requiere del sistema: python3, PyQt6, libmpv2, requests)

## Build
```bash
# deb
dpkg-buildpackage -us -uc -b

# AppImage
./build-appimage.sh
```

## Licencia
GPL-3.0
