@echo off
REM Sora 2 영상 워터마크 제거 런처
REM 사용법: remove_watermark.bat [입력파일/폴더] [옵션]
REM 예시:
REM   remove_watermark.bat video.mp4
REM   remove_watermark.bat D:\sora_videos\ -o D:\cleaned\
REM   remove_watermark.bat video.mp4 --model e2fgvi_hq

set "PROJECT_ROOT=%~dp0.."
set "PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [오류] venv가 없습니다. scripts\setup.bat을 먼저 실행하세요.
    pause
    exit /b 1
)

"%PYTHON%" "%PROJECT_ROOT%\scripts\remove_watermark.py" %*
