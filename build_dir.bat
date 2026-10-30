@echo off
REM Alternative, MORE STABLE build: a folder (onedir) instead of a single
REM executable. Files are extracted once next to the .exe (no per-run temp
REM extraction), which avoids the intermittent "failed to start" issues some
REM antivirus/cleanup tools cause with single-file (.exe) builds.
REM
REM Usage:  build_dir.bat   ->  dist\FolderIconMaker\FolderIconMaker.exe  (+ supporting files)
REM Zip the whole dist\FolderIconMaker folder to distribute it as a portable app.
REM --noupx: UPX-packed exes can trigger antivirus false positives, so UPX stays off.
setlocal
python -m PyInstaller --noconfirm --onedir --windowed --name "FolderIconMaker" ^
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
echo Done -^> dist\FolderIconMaker\FolderIconMaker.exe  (portable folder)
pause
