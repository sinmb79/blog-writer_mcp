@echo off
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] Missing project virtualenv Python: %PYTHON%
    echo Create the venv and install requirements first.
    exit /b 1
)
"%PYTHON%" "%PROJECT_ROOT%\blog_runtime.py" %*
