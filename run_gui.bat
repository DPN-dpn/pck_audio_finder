@echo off
REM Run the local Flask GUI using the bundled runtime if available
SETLOCAL ENABLEDELAYEDEXPANSION
set ROOT=%~dp0
set RPY=%ROOT%runtime\python.exe

if exist "%RPY%" (
    echo Using runtime python: "%RPY%"
    "%RPY%" -m pip install --quiet Flask || echo "Flask already installed or install failed"
    echo Running lib_installer.py to ensure native helper libs are present...
    "%RPY%" "%ROOT%lib_installer.py" || echo "lib_installer failed or returned non-zero; continuing"
    start "" "%RPY%" "%ROOT%app\main.py"
    timeout /t 2 /nobreak >nul
    start "" "http://127.0.0.1:5000"
) else (
    echo runtime python not found, using system python
    python -m pip install --quiet Flask || echo "Flask already installed or install failed"
    echo Running lib_installer.py to ensure native helper libs are present...
    python "%ROOT%lib_installer.py" || echo "lib_installer failed or returned non-zero; continuing"
    start "" python "%ROOT%app\main.py"
    timeout /t 2 /nobreak >nul
    start "" "http://127.0.0.1:5000"
)

ENDLOCAL
