@echo off
REM Build Folder Icon Maker as a single Windows executable
REM (FolderIconMaker.exe).
REM 1) pip install pyinstaller
REM 2) run this file:  build.bat
REM The result is dist\FolderIconMaker.exe  (double-click to run, no console
REM window).
REM --noupx: UPX-packed exes can trigger antivirus false positives, so UPX stays off.
setlocal
python -m PyInstaller --noconfirm --onefile --windowed --name "FolderIconMaker" ^
  --icon "assets\icon.ico" ^
  --add-data "rcfi_assets;rcfi_assets" ^
  --add-data "assets;assets" ^
  --add-data "LICENSE;." ^
  --add-data "THIRD_PARTY_LICENSES.txt;." ^
  --copy-metadata "pillow" ^
  --exclude-module "arabic_reshaper" --exclude-module "bidi" ^
  --hidden-import "tkinter" ^
  --hidden-import "PIL" --hidden-import "PIL.ImageTk" --hidden-import "PIL.ImageDraw" ^
  --hidden-import "PIL.ImageFont" --hidden-import "PIL.ImageChops" --hidden-import "PIL.ImageFilter" ^
  --hidden-import "icon_engine" --hidden-import "rcfi_templates" ^
  --hidden-import "windows_folder" --hidden-import "templates_lib" ^
  --exclude-module "numpy" --exclude-module "matplotlib" --exclude-module "PyQt5" --exclude-module "PyQt6" ^
  --exclude-module "pygame" --exclude-module "lxml" --exclude-module "requests" ^
  --exclude-module "charset_normalizer" --exclude-module "PySide2" --exclude-module "PySide6" ^
  --noupx ^
  main.py
echo.
echo Done -^> dist\FolderIconMaker.exe
pause
