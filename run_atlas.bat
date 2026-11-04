@echo off
title ATLAS 2.0
cd /d "%~dp0"

:: Check for Administrative privileges and auto-elevate if not admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges for full system & keyboard automation...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: 1. Launch background server if not already responsive
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if errorlevel 1 (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
    timeout /t 2 /nobreak >nul
)

:: 2. Launch application window (Priority: Chrome App -> Edge App -> Default Browser)
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app="http://127.0.0.1:8000"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --app="http://127.0.0.1:8000"
) else if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app="http://127.0.0.1:8000"
) else if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files\Microsoft\Edge\Application\msedge.exe" --app="http://127.0.0.1:8000"
) else (
    start "" "http://127.0.0.1:8000"
)
