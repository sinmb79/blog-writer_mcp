@echo off
chcp 65001 > nul
title The 4th Path - Control Panel

echo ================================================
echo   The 4th Path · Control Panel
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

:: 프론트엔드 빌드
echo [*] 프론트엔드 빌드 중...
cd /d "%SCRIPT_DIR%frontend"
npm run build

if errorlevel 1 (
    echo [!] 프론트엔드 빌드 실패!
    pause
    exit /b 1
)

:: 백엔드 서버 시작
echo [*] 대시보드 서버 시작...
echo.
echo   접속 주소: http://localhost:8080
echo   종료하려면 이 창을 닫으세요.
echo.

cd /d "%PROJECT_ROOT%"
"%PYTHON%" blog_runtime.py server

pause
