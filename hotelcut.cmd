@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0hotelcut.ps1" %*
exit /b %ERRORLEVEL%
