@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%.venv\Scripts\python.exe" goto install_deps

where py >nul 2>nul
if %errorlevel%==0 (
    echo Creating local runtime...
    py -3 -m venv ".venv"
    if %errorlevel% neq 0 goto no_python
    goto install_deps
)

where python >nul 2>nul
if %errorlevel%==0 (
    echo Creating local runtime...
    python -m venv ".venv"
    if %errorlevel% neq 0 goto no_python
    goto install_deps
)

goto no_python

:install_deps
set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
echo Installing runtime dependencies. This may take a few minutes on first run...
call "%PYTHON_EXE%" -m pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
if %errorlevel% neq 0 goto install_failed
call "%PYTHON_EXE%" -m pip install -r "%ROOT%requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
if %errorlevel% neq 0 goto install_failed

echo Install complete. Launching Livermore Assistant...
call "%ROOT%RUN_LIVERMORE_ASSISTANT.cmd"
exit /b 0

:no_python
echo Python 3.11+ was not found. Please install Python first, then run this script again.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:install_failed
echo Dependency installation failed. Please check your network connection and try again.
pause
exit /b 1