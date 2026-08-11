@echo off
setlocal
cd /d "%~dp0"
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" "main.py"
endlocal
