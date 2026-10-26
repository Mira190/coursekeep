@echo off
chcp 65001 >nul
cd /d "%~dp0"
title CourseKeep

rem Python 3.9+ present? (The Microsoft Store "python" stub fails this check too.)
python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>nul
if errorlevel 1 (
  echo CourseKeep needs Python 3.9 or newer.
  echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then run this again.
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)

rem First run: install what CourseKeep uses.
python -c "import requests, bs4, lxml, trafilatura" >nul 2>nul
if errorlevel 1 (
  echo First run: installing what CourseKeep needs. This takes a minute...
  python -m pip install --disable-pip-version-check -q -r requirements.txt
  if errorlevel 1 (
    echo Installing failed. Try running this in a terminal: python -m pip install -r requirements.txt
    pause
    exit /b 1
  )
)

python -X utf8 scripts\app.py
if errorlevel 1 pause
