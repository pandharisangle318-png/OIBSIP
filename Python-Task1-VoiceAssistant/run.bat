@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VYOM Voice Assistant
if not exist ".venv\Scripts\activate.bat" goto nosetup
call ".venv\Scripts\activate.bat"
python main.py
if errorlevel 1 goto failed
exit /b 0

:nosetup
echo [ERROR] The virtual environment was not found. Please run setup.bat first.
pause
exit /b 1

:failed
echo.
echo [ERROR] VYOM stopped with an error. Read the message above, check logs\vyom.log,
echo or run diagnose.bat to check your installation.
pause
exit /b 1
