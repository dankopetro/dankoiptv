#!/usr/bin/env bash
set -e

APP=dankoiptv
BUILD_DIR="build/AppDir"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/usr/bin" "$BUILD_DIR/usr/lib" "$BUILD_DIR/usr/share/applications" "$BUILD_DIR/usr/share/pixmaps"

# Copy python files
cp -r dankoiptv "$BUILD_DIR/usr/bin/"
cp setup.py "$BUILD_DIR/"

# Generate simple app icon using python PIL
python3 -c '
from PIL import Image, ImageDraw
img = Image.new("RGB", (256, 256), color=(30, 30, 40))
d = ImageDraw.Draw(img)
d.rectangle([64, 64, 192, 192], fill=(0, 150, 255))
d.polygon([(110, 90), (110, 166), (160, 128)], fill=(255, 255, 255))
img.save("build/AppDir/dankoiptv.png")
img.save("build/AppDir/.DirIcon", format="PNG")
'

# Update desktop file icon to dankoiptv
sed -i 's/Icon=multimedia-player/Icon=dankoiptv/' debian/dankoiptv.desktop
cp debian/dankoiptv.desktop "$BUILD_DIR/dankoiptv.desktop"
cp debian/dankoiptv.desktop "$BUILD_DIR/usr/share/applications/"
cp "build/AppDir/dankoiptv.png" "$BUILD_DIR/usr/share/pixmaps/"

# Create launcher script inside AppDir
cat << 'EOF' > "$BUILD_DIR/AppRun"
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export PYTHONPATH="${HERE}/usr/bin:${PYTHONPATH}"
exec python3 -m dankoiptv.main "$@"
EOF
chmod +x "$BUILD_DIR/AppRun"

# Build AppImage using extracted appimagetool
ARCH=x86_64 ./squashfs-root/AppRun "$BUILD_DIR" dankoiptv-x86_64.AppImage
