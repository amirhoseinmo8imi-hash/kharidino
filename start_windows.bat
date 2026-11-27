@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Please run setup_windows.bat first. & pause & exit /b 1)
set FLASK_DEBUG=0
.venv\Scripts\python.exe app.py
pause
