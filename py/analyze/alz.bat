@echo off
setlocal EnableExtensions
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0alz.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo alz.ps1 failed with exit code %EXIT_CODE%.
)
pause
exit /b %EXIT_CODE%
