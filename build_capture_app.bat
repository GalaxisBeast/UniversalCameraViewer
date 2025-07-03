@echo off
REM Name of your Python file (adjust if needed)
set SCRIPT_NAME=capture_app.py

REM Change to the folder where the script is located
cd /d %~dp0

REM Use PyInstaller from PATH
pyinstaller --onefile --windowed "%SCRIPT_NAME%"

REM Notify user
echo.
echo ===============================
echo Build complete! Check /dist folder for .exe
echo ===============================
pause
