@echo off
title Fiverr Scraper
cd /d "%~dp0"

echo.
echo  ============================================
echo    Fiverr Scraper - Starting...
echo  ============================================
echo.

REM Detect Python from virtual environment
if exist "env\Scripts\python.exe" (
    set PYTHON="%~dp0env\Scripts\python.exe"
    echo  [OK] Using virtual environment: env\
) else if exist "venv\Scripts\python.exe" (
    set PYTHON="%~dp0venv\Scripts\python.exe"
    echo  [OK] Using virtual environment: venv\
) else (
    set PYTHON=python
    echo  [!] No virtual environment found. Using system Python.
)

REM Always use "python -m pip" to avoid broken pip.exe launchers in relocated venvs
set PIP=%PYTHON% -m pip

echo.

REM Check that Python is available
%PYTHON% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found. Please install Python or set up a virtual environment.
    pause
    exit /b 1
)

REM Install Flask if not present
%PIP% show flask >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installing Flask...
    %PIP% install flask -q
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to install Flask.
        pause
        exit /b 1
    )
    echo  [OK] Flask installed.
)

REM Install all requirements
echo  Checking requirements...
%PIP% install -r requirements.txt -q
echo  [OK] Requirements ready.
echo.
echo  Starting server at http://localhost:5000
echo  Your browser will open automatically.
echo  Press Ctrl+C to stop the server.
echo.
echo  ============================================
echo.

%PYTHON% server.py

echo.
echo  Server stopped.
pause
