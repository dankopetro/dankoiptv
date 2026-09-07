#!/usr/bin/env bash
# Build Danko TV .deb + AppImage. Versión auto: ./version.sh dankotv
set -e
cd "$(dirname "$0")"
VER=$(./version.sh dankotv)
echo "=== Danko TV $VER ==="
echo "$VER" > dankotv/VERSION.txt

# inyectar versión en copia de trabajo (no en fuente)
inject() { grep -rl "__DANKOTV_VERSION__" "$1" | xargs sed -i "s/__DANKOTV_VERSION__/$VER/g"; }

# ---------- .deb (autocontenido: shell + motor + assets, como la AppImage) ----------
PKGDIR="build/dankotv-deb"
rm -rf "$PKGDIR"
mkdir -p "$PKGDIR/DEBIAN" "$PKGDIR/usr/bin" "$PKGDIR/usr/lib/dankotv" "$PKGDIR/usr/share/applications" "$PKGDIR/usr/share/icons/hicolor/scalable/apps" "$PKGDIR/usr/share/pixmaps"
cp -r dankotv "$PKGDIR/usr/lib/dankotv/"
# motor base adentro (mismo layout que la AppImage: no depende del paquete dankoiptv)
cp -r usr/lib/dankoiptv "$PKGDIR/usr/lib/"
cp -r usr/share/dankoiptv "$PKGDIR/usr/share/"
mkdir -p "$PKGDIR/usr/share/locale"
for f in po/dankoiptv-*.po; do
  lang=$(basename "$f" .po | sed 's/dankoiptv-//')
  mkdir -p "$PKGDIR/usr/share/locale/$lang/LC_MESSAGES"
  msgfmt -o "$PKGDIR/usr/share/locale/$lang/LC_MESSAGES/dankoiptv.mo" "$f"
done
find "$PKGDIR" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
inject "$PKGDIR/usr/lib/dankotv"
cat > "$PKGDIR/usr/bin/dankotv" << 'EOF'
#!/bin/bash
export PYTHONPATH="/usr/lib/dankoiptv:${PYTHONPATH}"
exec python3 /usr/lib/dankotv/dankotv/app.py "$@"
EOF
chmod +x "$PKGDIR/usr/bin/dankotv"
cat > "$PKGDIR/usr/share/applications/dankotv.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Danko TV
Comment=Reproductor IPTV con reconexión seamless
Exec=dankotv
Icon=dankotv
Categories=AudioVideo;Video;Player;TV;
StartupNotify=true
EOF
cp dankotv/assets/dankotv.svg "$PKGDIR/usr/share/icons/hicolor/scalable/apps/dankotv.svg"
cp dankotv/assets/logo-256.png "$PKGDIR/usr/share/pixmaps/dankotv.png"
DEBSIZE=$(du -sk "$PKGDIR/usr" | cut -f1)
cat > "$PKGDIR/DEBIAN/control" << EOF
Package: dankotv
Version: $VER
Section: video
Priority: optional
Architecture: all
Depends: python3-pyqt6, python3-requests, libmpv2, mpv
Installed-Size: $DEBSIZE
Maintainer: Danko Petro <danko@example.com>
Description: Danko TV - reproductor IPTV con reconexión seamless
 Pantalla Mis listas, layouts declarativos, 12 skins, logo propio.
 Motor libmpv embebido con keep-open + eof-reached cascade (autocontenido).
EOF
DEB="../dankotv_${VER}_all.deb"
fakeroot dpkg-deb --build "$PKGDIR" "$DEB" 2>/dev/null || dpkg-deb --build "$PKGDIR" "$DEB"
cp -f "$DEB" "./dankotv_${VER}_all.deb"
ln -sf "dankotv_${VER}_all.deb" dankotv_all.deb
echo "DEB: $DEB y ./dankotv_${VER}_all.deb ($(du -h "$DEB" | cut -f1))"

# ---------- AppImage (autocontenido: shell + motor + assets) ----------
APPDIR="build/dankotv-AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/pixmaps"
cp -r dankotv "$APPDIR/usr/lib/"
cp -r usr/lib/dankoiptv "$APPDIR/usr/lib/"
cp -r usr/share/dankoiptv "$APPDIR/usr/share/"
mkdir -p "$APPDIR/usr/share/locale"
for f in po/dankoiptv-*.po; do
  lang=$(basename "$f" .po | sed 's/dankoiptv-//')
  mkdir -p "$APPDIR/usr/share/locale/$lang/LC_MESSAGES"
  msgfmt -o "$APPDIR/usr/share/locale/$lang/LC_MESSAGES/dankoiptv.mo" "$f"
done
inject "$APPDIR/usr/lib/dankotv"
cp dankotv/assets/logo-256.png "$APPDIR/dankotv.png"
cp dankotv/assets/logo-256.png "$APPDIR/.DirIcon"
cp dankotv/assets/logo-256.png "$APPDIR/usr/share/pixmaps/dankotv.png"
cp dankotv/assets/dankotv.svg "$APPDIR/usr/share/pixmaps/"
cp "$PKGDIR/usr/share/applications/dankotv.desktop" "$APPDIR/dankotv.desktop"
cat << 'EOF' > "$APPDIR/AppRun"
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export LC_NUMERIC=C
export PYTHONPATH="${HERE}/usr/lib:${HERE}/usr/lib/dankoiptv:${PYTHONPATH}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:/usr/lib/x86_64-linux-gnu:/usr/lib"
if ! ldconfig -p 2>/dev/null | grep -q libmpv; then
  echo "ADVERTENCIA: libmpv no encontrada. Instala: sudo apt install libmpv2 mpv" >&2
fi
exec python3 "${HERE}/usr/lib/dankotv/app.py" "$@"
EOF
chmod +x "$APPDIR/AppRun"
OUT="dankotv-${VER}-x86_64.AppImage"
if [ -x "./squashfs-root/AppRun" ]; then
  ARCH=x86_64 ./squashfs-root/AppRun "$APPDIR" "$OUT"
  ln -sf "$OUT" dankotv-x86_64.AppImage
  echo "AppImage: $OUT ($(du -h "$OUT" | cut -f1))"
elif [ -x "./appimagetool-x86_64.AppImage" ]; then
  ./appimagetool-x86_64.AppImage --appimage-extract >/dev/null 2>&1 || true
  ARCH=x86_64 ./squashfs-root/AppRun "$APPDIR" "$OUT"
  ln -sf "$OUT" dankotv-x86_64.AppImage
else
  echo "appimagetool no encontrado — AppDir en $APPDIR"
fi
