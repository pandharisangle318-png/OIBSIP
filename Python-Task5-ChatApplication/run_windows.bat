@echo off
REM One-click start for Windows: creates a virtual environment, installs packages, starts ChatSphere.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.9+ from https://www.python.org/downloads/ and tick "Add Python to PATH".
  pause
  exit /b 1
)

if not exist venv (
  echo Creating virtual environment...
  python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo Package installation failed. Check your internet connection.
  pause
  exit /b 1
)

start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
python run_server.py
pause
