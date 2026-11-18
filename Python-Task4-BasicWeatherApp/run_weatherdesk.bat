@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 was not found. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 ( pause & exit /b 1 )
)

call ".venv\Scripts\activate.bat"
python -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 ( echo Dependency installation failed. & pause & exit /b 1 )

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env - open it and paste your OpenWeatherMap API key, then run this script again.
  notepad ".env"
  pause
  exit /b 0
)

python main.py
if errorlevel 1 pause
