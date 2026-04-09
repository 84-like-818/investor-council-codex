@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_investor_council_shell.ps1" -InstallOnly %*
if errorlevel 1 pause