@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VYOM Setup
echo ==========================================
echo   VYOM Voice Assistant - Setup
echo ==========================================

set "PYCMD="
py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PYCMD=py -3.12"
if defined PYCMD goto havepy
python -c "import sys" >nul 2>nul
if errorlevel 1 goto nopython
set "PYCMD=python"

:havepy
%PYCMD% -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)"
if errorlevel 1 goto badversion
echo Using Python:
%PYCMD% --version

if exist ".venv\Scripts\python.exe" goto venvready
echo.
echo Creating virtual environment in .venv ...
%PYCMD% -m venv .venv
if errorlevel 1 goto venvfail

:venvready
call ".venv\Scripts\activate.bat"
echo.
echo Upgrading pip ...
python -m pip install --upgrade pip
if errorlevel 1 goto pipfail
echo.
echo Installing requirements (this can take a few minutes) ...
python -m pip install -r requirements.txt
if errorlevel 1 goto pipfail

if exist ".env" goto envdone
copy ".env.example" ".env" >nul
echo.
echo Created .env from .env.example - open it in Notepad and add your own keys.
:envdone

echo.
echo ==========================================
echo   Setup finished successfully.
echo   Next: edit .env (optional), then run run.bat
echo   Check your system any time with diagnose.bat
echo ==========================================
pause
exit /b 0

:nopython
echo [ERROR] Python was not found.
echo Install Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run setup.bat again.
goto fail

:badversion
echo [ERROR] Unsupported Python version. VYOM needs Python 3.10 to 3.13 (3.12 recommended).
echo Install Python 3.12 from https://www.python.org/downloads/ then run setup.bat again.
goto fail

:venvfail
echo [ERROR] Could not create the virtual environment.
goto fail

:pipfail
echo [ERROR] Installing the packages failed. Check your internet connection and read the message above.
echo If PyAudio failed: make sure you use Python 3.12 (64-bit) because PyAudio 0.2.14 ships a ready-made wheel for it.
goto fail

:fail
echo.
echo Setup did not finish.
pause
exit /b 1
