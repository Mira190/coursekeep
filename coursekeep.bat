@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p URL=Paste a course or blog URL:
python -X utf8 scripts\coursekeep.py "%URL%" -o downloads
start "" "downloads"
pause
