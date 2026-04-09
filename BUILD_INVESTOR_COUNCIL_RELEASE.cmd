@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Local runtime not found. Please create .venv first.
    pause
    exit /b 1
)

echo Installing build dependencies...
call "%PYTHON_EXE%" -m pip install -r "%ROOT%requirements-build.txt"
if %errorlevel% neq 0 goto build_failed

echo Building ??????? release artifacts...
call "%PYTHON_EXE%" "%ROOT%scripts\build_investor_council_release.py" %*
if %errorlevel% neq 0 goto build_failed

echo Build complete.
start "" "%ROOT%dist\InvestorCouncilReleases"
exit /b 0

:build_failed
echo Build failed. Please review the log above.
pause
exit /b 1
