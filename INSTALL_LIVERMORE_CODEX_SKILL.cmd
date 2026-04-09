@echo off
setlocal

echo This installer will not delete anything outside the repository.
echo.

set "ROOT=%~dp0"
set "SRC=%ROOT%codex-skills\livermore-market-assistant"
set "DEST=%USERPROFILE%\.codex\skills\livermore-market-assistant"

if not exist "%SRC%\SKILL.md" (
    echo Source skill folder not found: %SRC%
    pause
    exit /b 1
)

if exist "%DEST%" (
    echo Skill already exists: %DEST%
    echo To avoid changing files outside this repository unexpectedly, this installer will not overwrite it.
    echo If you want to refresh the installed copy, please rename that folder manually and run this script again.
    pause
    exit /b 0
)

if not exist "%USERPROFILE%\.codex\skills" mkdir "%USERPROFILE%\.codex\skills"
mkdir "%DEST%"
robocopy "%SRC%" "%DEST%" /E >nul

echo Installed livermore-market-assistant to %DEST%
echo In Codex, invoke it with: $livermore-market-assistant
pause
exit /b 0
