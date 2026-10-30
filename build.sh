#!/usr/bin/env bash
# Run/build Folder Icon Maker from source on a non-Windows machine.
#
# DEVELOPMENT / TESTING ONLY: the app itself is Windows-only (folder icons
# are a Windows shell feature). On Linux/macOS this lets a developer run
# and test the CODE (the window opens, applying icons is disabled) -- it
# is NOT a way to build a Linux/macOS app. The real exe is built on
# Windows with build.bat / build_dir.bat.
# Usage:  bash build.sh
# --noupx: UPX-packed exes can trigger antivirus false positives, so UPX stays off.
set -e
PY="${PYTHON:-python3}"
"$PY" -m PyInstaller --noconfirm --onefile --windowed --name "FolderIconMaker" \
  --icon "assets/icon.ico" \
  --add-data "rcfi_assets:rcfi_assets" \
  --add-data "assets:assets" \
  --add-data "LICENSE:." \
  --add-data "THIRD_PARTY_LICENSES.txt:." \
  --copy-metadata "pillow" \
  --exclude-module "arabic_reshaper" --exclude-module "bidi" \
  --hidden-import "tkinter" \
  --hidden-import "PIL" --hidden-import "PIL.ImageTk" --hidden-import "PIL.ImageDraw" \
  --hidden-import "PIL.ImageFont" --hidden-import "PIL.ImageChops" --hidden-import "PIL.ImageFilter" \
  --hidden-import "icon_engine" --hidden-import "rcfi_templates" \
  --hidden-import "windows_folder" --hidden-import "templates_lib" \
  --exclude-module "numpy" --exclude-module "matplotlib" --exclude-module "PyQt5" --exclude-module "PyQt6" \
  --exclude-module "pygame" --exclude-module "lxml" --exclude-module "requests" \
  --exclude-module "charset_normalizer" --exclude-module "PySide2" --exclude-module "PySide6" \
  --noupx \
  main.py
echo "Done -> dist/FolderIconMaker"
