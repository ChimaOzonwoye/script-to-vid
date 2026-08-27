@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo The app is not installed yet. Run install-windows.ps1 first:
  echo   right-click it and choose "Run with PowerShell".
  pause
  exit /b 1
)
if exist ffmpeg\bin\ffmpeg.exe set "PATH=%cd%\ffmpeg\bin;%PATH%"
.venv\Scripts\python.exe tools\serve.py
pause
