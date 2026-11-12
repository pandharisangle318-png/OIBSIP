@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VYOM Diagnostics
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
python tools\diagnose.py
echo.
pause
