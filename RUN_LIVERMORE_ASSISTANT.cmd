@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo Local runtime not found. Please run INSTALL_LIVERMORE_ASSISTANT.cmd first.
    pause
    exit /b 1
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":8766 .*LISTENING"') do (
    taskkill /PID %%P /F >nul 2>&1
)

echo Starting Livermore Assistant...
start "Livermore Assistant Server" "%PYTHON_EXE%" -m livermore_assistant.app --open-browser

endlocal