#!/usr/bin/env bash
# Dankoiptv AppImage builder — versionado 1.x (1.1g, 1.1h...) hasta 2.0
set -e
cd "$(dirname "$0")"

VER=$(cat VERSION | tr -d ' \n')
OUT="dankoiptv-${VER}-x86_64.AppImage"
BUILD_DIR="build/AppDir"
echo "Building $OUT (ver $VER)..."

# 1) compilar locales
for f in po/dankoiptv-*.po; do
  lang=$(basename "$f" .po | sed 's/dankoiptv-//')
  mkdir -p "usr/share/locale/$lang/LC_MESSAGES"
  msgfmt -o "usr/share/locale/$lang/LC_MESSAGES/dankoiptv.mo" "$f"
done

# 2) armar AppDir con el árbol usr/
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cp -r usr "$BUILD_DIR/"

# icono
python3 -c '
from PIL import Image, ImageDraw
import os
os.makedirs("build", exist_ok=True)
img = Image.new("RGB", (256, 256), color=(18, 18, 18))
d = ImageDraw.Draw(img)
d.rectangle([48, 48, 208, 208], fill=(255, 106, 0))
d.polygon([(100, 80), (100, 176), (165, 128)], fill=(255, 255, 255))
img.save("build/dankoiptv.png")
img.save("build/AppDir/.DirIcon", format="PNG")
'
cp build/dankoiptv.png "$BUILD_DIR/dankoiptv.png"
mkdir -p "$BUILD_DIR/usr/share/pixmaps"
cp usr/share/icons/hicolor/scalable/apps/dankoiptv.svg "$BUILD_DIR/usr/share/pixmaps/" 2>/dev/null || true
cp usr/share/applications/dankoiptv.desktop "$BUILD_DIR/dankoiptv.desktop"

# inyectar versión en la copia del AppDir
grep -rl "__DEB_VERSION__" "$BUILD_DIR" | xargs sed -i "s/__DEB_VERSION__/$VER/g"

# 3) AppRun
cat << 'EOF' > "$BUILD_DIR/AppRun"
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export LC_NUMERIC=C
export PYTHONPATH="${HERE}/usr/lib/dankoiptv:${PYTHONPATH}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:/usr/lib/x86_64-linux-gnu:/usr/lib"
if ! ldconfig -p 2>/dev/null | grep -q libmpv; then
  echo "ADVERTENCIA: libmpv no encontrada. Instala: sudo apt install libmpv2 mpv" >&2
fi
exec python3 "${HERE}/usr/lib/dankoiptv/dankoiptv.py" "$@"
EOF
chmod +x "$BUILD_DIR/AppRun"

# 4) empaquetar
if [ -x "./squashfs-root/AppRun" ]; then
  ARCH=x86_64 ./squashfs-root/AppRun "$BUILD_DIR" "$OUT"
  ln -sf "$OUT" dankoiptv-x86_64.AppImage
  echo "Creado $OUT -> dankoiptv-x86_64.AppImage"
elif [ -x "./appimagetool-x86_64.AppImage" ]; then
  ./appimagetool-x86_64.AppImage --appimage-extract >/dev/null 2>&1 || true
  ARCH=x86_64 ./squashfs-root/AppRun "$BUILD_DIR" "$OUT"
  ln -sf "$OUT" dankoiptv-x86_64.AppImage
else
  echo "appimagetool no encontrado — AppDir lista en $BUILD_DIR"
fi
