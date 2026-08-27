@echo off
REM Windows blocks .ps1 files by default, so the installer is launched from
REM here with the policy bypassed for this one process only.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1"
if errorlevel 1 (
  echo.
  echo The installer did not finish. The message above says what went wrong.
  pause
)
