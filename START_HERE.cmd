@echo off
cd /d "%~dp0"
start "" README.md
start "" projects\livermore\manifests\seeds_master.csv
echo 已打开 README 和 Livermore 种子清单。
echo 真正开始采集请双击 RUN_WINDOWS.cmd
pause
