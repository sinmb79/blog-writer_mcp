#!/bin/bash
# The 4th Path — Control Panel 시작 스크립트
# 백엔드(FastAPI) + 프론트엔드(Vite dev) 동시 실행

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "================================================"
echo "  The 4th Path · Control Panel"
echo "  프로젝트 루트: $PROJECT_ROOT"
echo "================================================"

# Python 가상환경 확인
if [ -d "$PROJECT_ROOT/venv" ]; then
    echo "[*] 가상환경 활성화..."
    source "$PROJECT_ROOT/venv/bin/activate" 2>/dev/null || source "$PROJECT_ROOT/venv/Scripts/activate" 2>/dev/null
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate" 2>/dev/null || source "$PROJECT_ROOT/.venv/Scripts/activate" 2>/dev/null
fi

# 백엔드 의존성 확인
echo "[*] 백엔드 의존성 확인..."
cd "$PROJECT_ROOT"
pip install fastapi uvicorn python-dotenv 2>/dev/null || true

# 프론트엔드 의존성 확인
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "[*] 프론트엔드 의존성 설치 (npm install)..."
    cd "$FRONTEND_DIR"
    npm install
fi

# 프론트 빌드 여부 확인
if [ ! -d "$FRONTEND_DIR/dist" ]; then
    echo "[*] 프론트엔드 빌드..."
    cd "$FRONTEND_DIR"
    npm run build
fi

# 함수: 백엔드 실행
start_backend() {
    echo "[*] 백엔드 시작 (http://localhost:8080)..."
    cd "$PROJECT_ROOT"
    python -m uvicorn dashboard.backend.server:app --host 0.0.0.0 --port 8080 --reload &
    BACKEND_PID=$!
    echo "    PID: $BACKEND_PID"
}

# 함수: 프론트엔드 개발 서버 실행
start_frontend_dev() {
    echo "[*] 프론트엔드 개발 서버 시작 (http://localhost:5173)..."
    cd "$FRONTEND_DIR"
    npm run dev &
    FRONTEND_PID=$!
    echo "    PID: $FRONTEND_PID"
}

# 실행 모드 선택
MODE=${1:-"prod"}

if [ "$MODE" = "dev" ]; then
    start_backend
    start_frontend_dev
    echo ""
    echo "개발 모드 실행 중:"
    echo "  프론트엔드: http://localhost:5173"
    echo "  백엔드 API: http://localhost:8080"
    echo ""
    echo "종료: Ctrl+C"
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
    wait
else
    # 프로덕션 모드: 프론트 빌드 후 백엔드만 실행
    echo "[*] 프론트엔드 빌드..."
    cd "$FRONTEND_DIR"
    npm run build

    start_backend
    echo ""
    echo "프로덕션 모드 실행 중:"
    echo "  대시보드: http://localhost:8080"
    echo ""
    echo "종료: Ctrl+C"
    trap "kill $BACKEND_PID 2>/dev/null; exit" INT TERM
    wait $BACKEND_PID
fi
