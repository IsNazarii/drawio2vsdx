#!/usr/bin/env bash
# Install development renderers into ~/tools without root (Ubuntu).
#   - draw.io Desktop (current) : fallback render, round-trip tests
#   - draw.io Desktop v26.0.16  : oracle (its own VSDX export)
#   - LibreOffice (AppImage)    : independent .vsdx -> PNG render
# AppImages are extracted, so FUSE is not required.
set -euo pipefail
T="${TOOLS_DIR:-$HOME/tools}"
mkdir -p "$T"
cd "$T"

fetch_appimage() {  # url dir
  local url="$1" dir="$2"
  if [ -x "$dir/squashfs-root/AppRun" ]; then echo "$dir: already installed"; return; fi
  mkdir -p "$dir"
  curl -fL --retry 3 -o "$dir/app.AppImage" "$url"
  chmod +x "$dir/app.AppImage"
  (cd "$dir" && ./app.AppImage --appimage-extract >/dev/null)
  rm -f "$dir/app.AppImage"
  echo "$dir: installed"
}

DRAWIO_VER="${DRAWIO_VER:-$(curl -fsSL https://api.github.com/repos/jgraph/drawio-desktop/releases/latest | python3 -c 'import json,sys;print(json.load(sys.stdin)["tag_name"][1:])')}"
fetch_appimage "https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VER}/drawio-x86_64-${DRAWIO_VER}.AppImage" drawio-current
fetch_appimage "https://github.com/jgraph/drawio-desktop/releases/download/v26.0.16/drawio-x86_64-26.0.16.AppImage" drawio-26.0.16

# LibreOffice: official AppImage builds (https://www.libreoffice.org/download/appimage/)
LO_URL="${LO_URL:-https://appimages.libreitalia.org/LibreOffice-fresh.basic-x86_64.AppImage}"
fetch_appimage "$LO_URL" libreoffice

echo
echo "Done. Tests find tools in $T automatically, or set DRAWIO_PATH / DRAWIO_ORACLE_PATH / SOFFICE_PATH."
