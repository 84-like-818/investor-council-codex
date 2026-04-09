@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"

if "%~1"=="" (
    echo Usage: BUILD_CUSTOMER_DELIVERY.cmd v0.1.0
    echo.
    echo This helper builds an internal support bundle only.
    echo Public releases should still be distributed from GitHub Releases.
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo Local runtime not found. Please create .venv first.
    pause
    exit /b 1
)

call "%PYTHON_EXE%" "%ROOT%scripts\prepare_customer_delivery.py" --version %1
if %errorlevel% neq 0 (
    echo Failed to prepare the internal helper delivery bundle.
    pause
    exit /b 1
)

echo Internal helper bundle ready at %ROOT%dist\InvestorCouncilCustomerDrop\%~1
exit /b 0
