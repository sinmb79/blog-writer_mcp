@echo off
chcp 65001 > nul
title The 4th Path - Control Panel (개발 모드)

echo ================================================
echo   The 4th Path · Control Panel (개발 모드)
echo ================================================

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

set "PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [ERROR] Missing project virtualenv Python: %PYTHON%
    echo Run scripts\setup.bat or create venv and install requirements first.
    pause
    exit /b 1
)

:: 프론트엔드 의존성 설치
if not exist "%SCRIPT_DIR%frontend\node_modules" (
    echo [*] npm 패키지 설치 중...
    cd /d "%SCRIPT_DIR%frontend"
    npm install
)

echo [*] 백엔드 시작 중...
start "FastAPI Backend" cmd /k "cd /d %PROJECT_ROOT% && %PYTHON% blog_runtime.py server --reload"

echo [*] 프론트엔드 개발 서버 시작 중...
start "Vite Frontend" cmd /k "cd /d %SCRIPT_DIR%frontend && npm run dev"

echo.
echo   백엔드: http://localhost:8080
echo   프론트: http://localhost:5173 (개발 서버)
echo.
echo 두 창이 열렸습니다. 각 창을 닫으면 서버가 종료됩니다.
pause
