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

echo Installing build dependencies...
call "%PYTHON_EXE%" -m pip install -r "%ROOT%requirements-build.txt" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
if %errorlevel% neq 0 goto build_failed

echo Building distributable package. Please wait...
call "%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --onedir --windowed --name LivermoreAssistantCN --collect-all akshare --collect-all pandas --collect-all curl_cffi --collect-all lxml --collect-all py_mini_racer --collect-all jsonpath --add-data "%ROOT%livermore_assistant\web;livermore_assistant\web" --add-data "%ROOT%jesse-livermore;jesse-livermore" "%ROOT%livermore_assistant\launcher.py"
if %errorlevel% neq 0 goto build_failed

(
    echo @echo off
    echo start "" "%%~dp0LivermoreAssistantCN.exe"
) > "%ROOT%dist\LivermoreAssistantCN\START_LIVERMORE_ASSISTANT.cmd"

echo Build complete. Share the whole dist\LivermoreAssistantCN folder. The recipient can double-click START_LIVERMORE_ASSISTANT.cmd or LivermoreAssistantCN.exe.
start "" "%ROOT%dist\LivermoreAssistantCN"
exit /b 0

:build_failed
echo Build failed. Please review the log above.
pause
exit /b 1