@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (echo Python launcher not found. Install Python 3.11+ and enable Add to PATH. & pause & exit /b 1)
py -3 -m venv .venv
if errorlevel 1 goto fail
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto fail
pip install -r requirements.txt
if errorlevel 1 goto fail
echo.
echo Setup complete. Run start_windows.bat to launch Kharidino.
pause
exit /b 0
:fail
echo Setup failed. Review the error above.
pause
exit /b 1
