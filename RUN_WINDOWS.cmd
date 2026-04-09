@echo off
setlocal
cd /d "%~dp0"

set "BOOTSTRAP_PY=python"
where py >nul 2>nul
if %errorlevel%==0 (
  set "BOOTSTRAP_PY=py -3"
)

where python >nul 2>nul
if %errorlevel% neq 0 if "%BOOTSTRAP_PY%"=="python" (
  echo Python was not found on PATH.
  echo Install Python 3 and run this script again.
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  call %BOOTSTRAP_PY% -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to upgrade pip.
  pause
  exit /b 1
)

.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies.
  pause
  exit /b 1
)

.venv\Scripts\python.exe scripts\pipeline.py --project livermore
pause
