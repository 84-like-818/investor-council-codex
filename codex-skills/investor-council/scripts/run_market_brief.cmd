@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "SKILL_ROOT=%SCRIPT_DIR%.."
set "EMBEDDED_PY=%SKILL_ROOT%\.venv\Scripts\python.exe"

if exist "%EMBEDDED_PY%" (
    "%EMBEDDED_PY%" "%SCRIPT_DIR%build_market_brief.py" %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if not errorlevel 1 (
    python "%SCRIPT_DIR%build_market_brief.py" %*
    exit /b %errorlevel%
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%SCRIPT_DIR%build_market_brief.py" %*
    exit /b %errorlevel%
)

echo Python 3.11+ is required. Please run START_INVESTOR_COUNCIL.cmd first.
exit /b 1