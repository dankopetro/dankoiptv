#!/usr/bin/env bash
set -e
BUILD_DIR="build/AppDir"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/usr/bin" "$BUILD_DIR/usr/lib" "$BUILD_DIR/usr/share/applications" "$BUILD_DIR/usr/share/pixmaps"

# Version desde dankoiptv/__init__.py
VER=$(python3 -c "import re; print(re.search(r'__version__\s*=\s*\"([^\"]+)\"', open('dankoiptv/__init__.py').read()).group(1))")
OUT="dankoiptv-${VER}-x86_64.AppImage"
echo "Building $OUT (ver $VER)..."

# Copy python package (solo fuentes, no __pycache__)
mkdir -p "$BUILD_DIR/usr/bin/dankoiptv"
cp dankoiptv/*.py "$BUILD_DIR/usr/bin/dankoiptv/"
cp setup.py "$BUILD_DIR/"

# Icon (idempotente, no muta debian/)
python3 -c '
from PIL import Image, ImageDraw
import os
os.makedirs("build/AppDir", exist_ok=True)
img = Image.new("RGB", (256, 256), color=(30, 30, 40))
d = ImageDraw.Draw(img)
d.rectangle([64, 64, 192, 192], fill=(0, 150, 255))
d.polygon([(110, 90), (110, 166), (160, 128)], fill=(255, 255, 255))
img.save("build/AppDir/dankoiptv.png")
img.save("build/AppDir/.DirIcon", format="PNG")
'

# Desktop file: copia sin mutar el original
DESK_SRC="debian/dankoiptv.desktop"
TMP_DESK="build/dankoiptv.desktop.tmp"
mkdir -p build
cp "$DESK_SRC" "$TMP_DESK"
if ! grep -q "^Icon=dankoiptv" "$TMP_DESK"; then
  sed -i "s/^Icon=.*/Icon=dankoiptv/" "$TMP_DESK"
fi
cp "$TMP_DESK" "$BUILD_DIR/dankoiptv.desktop"
cp "$TMP_DESK" "$BUILD_DIR/usr/share/applications/dankoiptv.desktop"
cp "build/AppDir/dankoiptv.png" "$BUILD_DIR/usr/share/pixmaps/dankoiptv.png" 2>/dev/null || true
cp "build/AppDir/dankoiptv.png" "$BUILD_DIR/dankoiptv.png" 2>/dev/null || true

cat << 'EOF' > "$BUILD_DIR/AppRun"
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export LC_NUMERIC=C
export PYTHONPATH="${HERE}/usr/bin:${PYTHONPATH}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:/usr/lib/x86_64-linux-gnu:/usr/lib"
if ! ldconfig -p 2>/dev/null | grep -q libmpv; then
  echo "ADVERTENCIA: libmpv no encontrada. Instala: sudo apt install libmpv2 mpv" >&2
fi
exec python3 -m dankoiptv.main "$@"
EOF
chmod +x "$BUILD_DIR/AppRun"

# Usa appimagetool extraído si existe
if [ -x "./squashfs-root/AppRun" ]; then
  ARCH=x86_64 ./squashfs-root/AppRun "$BUILD_DIR" "$OUT"
  ln -sf "$OUT" dankoiptv-x86_64.AppImage
  echo "Creado $OUT -> dankoiptv-x86_64.AppImage"
elif [ -x "./appimagetool-x86_64.AppImage" ]; then
  ARCH=x86_64 ./appimagetool-x86_64.AppImage --appimage-extract 2>/dev/null || true
  ARCH=x86_64 ./squashfs-root/AppRun "$BUILD_DIR" "$OUT"
  ln -sf "$OUT" dankoiptv-x86_64.AppImage
else
  echo "appimagetool no encontrado — AppDir lista en $BUILD_DIR"
fi
