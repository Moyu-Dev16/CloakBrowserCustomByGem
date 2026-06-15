@echo off
title CloakBrowser Registration Tool
echo ========================================
echo   CloakBrowser Registration Tool
echo ========================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [INFO] Checking dependencies...
python -c "import customtkinter; import requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] First run detected. Installing dependencies...
    pip install -r "%~dp0requirements.txt"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo [SUCCESS] Dependencies installed.
    echo.
)

echo [INFO] Starting application...
echo.
python "%~dp0main.py"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with code: %errorlevel%
    pause
)
