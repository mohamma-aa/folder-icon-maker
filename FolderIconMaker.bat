@echo off
REM Launcher for Folder Icon Maker (Windows). Double-click to run.
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Run failed / اجرای ناموفق. Make sure Python + Pillow are installed /
    echo مطمئن شوید Python نصب است و کتابخانه‌ها نصب شده‌اند:
    echo     pip install Pillow
    pause
)
