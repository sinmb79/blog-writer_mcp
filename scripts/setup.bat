@echo off
echo ========================================
echo  Blog Engine Setup
echo ========================================

REM Create Python venv
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create Python venv. Please install Python 3.11+
    pause
    exit /b 1
)

REM Install packages
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package installation failed.
    pause
    exit /b 1
)

REM Copy .env file if not exists
if not exist .env (
    copy .env.example .env
    echo [OK] .env file created. Please fill in your API keys: .env
)

REM Create data directories
if not exist data\topics mkdir data\topics
if not exist data\collected mkdir data\collected
if not exist data\discarded mkdir data\discarded
if not exist data\pending_review mkdir data\pending_review
if not exist data\published mkdir data\published
if not exist data\analytics mkdir data\analytics
if not exist data\images mkdir data\images
if not exist data\drafts mkdir data\drafts
if not exist data\originals mkdir data\originals
if not exist data\outputs mkdir data\outputs
if not exist data\assist mkdir data\assist
if not exist data\assist\sessions mkdir data\assist\sessions
if not exist data\assist\inbox mkdir data\assist\inbox
if not exist data\novels mkdir data\novels
if not exist logs mkdir logs
if not exist config\novels mkdir config\novels
if not exist data\shorts mkdir data\shorts
if not exist data\shorts\scripts mkdir data\shorts\scripts
if not exist data\shorts\clips mkdir data\shorts\clips
if not exist data\shorts\tts mkdir data\shorts\tts
if not exist data\shorts\captions mkdir data\shorts\captions
if not exist data\shorts\rendered mkdir data\shorts\rendered
if not exist data\shorts\published mkdir data\shorts\published
if not exist assets\characters\zero\expressions mkdir assets\characters\zero\expressions
if not exist assets\characters\zero\poses mkdir assets\characters\zero\poses
if not exist assets\characters\bao\expressions mkdir assets\characters\bao\expressions
if not exist assets\characters\bao\poses mkdir assets\characters\bao\poses
if not exist assets\characters\bao\scarves mkdir assets\characters\bao\scarves
if not exist assets\backgrounds\fourth_path mkdir assets\backgrounds\fourth_path
if not exist assets\backgrounds\tech_blog mkdir assets\backgrounds\tech_blog
if not exist assets\bgm mkdir assets\bgm
if not exist input\images mkdir input\images
if not exist input\videos mkdir input\videos
if not exist input\scripts mkdir input\scripts
if not exist input\audio mkdir input\audio
if not exist input\_processed mkdir input\_processed
if not exist templates\shorts mkdir templates\shorts

REM Download fonts (Noto Sans KR for card/shorts converter)
echo [INFO] Downloading fonts...
venv\Scripts\python.exe scripts\download_fonts.py

REM Register scheduler.py in Windows Task Scheduler (blog.cmd 경유)
set BLOG_CMD=%~dp0blog.cmd
set PYTHON_PATH=%~dp0venv\Scripts\pythonw.exe

schtasks /query /tn "BlogEngine" >nul 2>&1
if errorlevel 1 (
    schtasks /create /tn "BlogEngine" /tr "\"%BLOG_CMD%\" scheduler" /sc onlogon /rl highest /f
    echo [OK] BlogEngine registered in Windows Task Scheduler (blog scheduler)
) else (
    echo [INFO] BlogEngine task already registered.
)

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Open .env and fill in all API keys
echo 2. Run scripts\get_token.py to get Google OAuth token
echo    (Blogger + Search Console + YouTube OAuth)
echo 3. Update BLOG_MAIN_ID in .env with your Blogger blog ID
echo 4. Start scheduler:  blog scheduler
echo 5. Start dashboard:  blog server  (http://localhost:8080)
echo 6. CLI status check: blog status
echo.
pause
