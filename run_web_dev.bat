@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
".venv\Scripts\python.exe" -m uvicorn web_app:app --host 127.0.0.1 --port 8001 --reload
