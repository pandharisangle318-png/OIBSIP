@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VYOM Tests
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
python tests\run_qa.py
set "RESULT=%errorlevel%"
echo.
if "%RESULT%"=="0" (echo All automated tests passed.) else (echo Some tests FAILED. See the list above.)
echo A detailed report was written to docs\QA_REPORT.md
pause
exit /b %RESULT%
