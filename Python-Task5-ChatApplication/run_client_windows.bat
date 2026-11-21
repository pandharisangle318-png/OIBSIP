@echo off
REM Starts the command-line chat client (the server must already be running).
cd /d "%~dp0"
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python client.py
pause
