"""
dashboard/backend/server.py
미디어 엔진 컨트롤 패널 — FastAPI 메인 서버

실행: uvicorn dashboard.backend.server:app --port 8080
또는: python -m uvicorn dashboard.backend.server:app --port 8080 --reload
"""
import os
from pathlib import Path

from runtime_guard import ensure_project_runtime

ensure_project_runtime(
    "dashboard server",
    ["fastapi", "uvicorn", "python-dotenv"],
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from dashboard.backend import (
    api_overview,
    api_content,
    api_analytics,
    api_novels,
    api_settings,
    api_connections,
    api_tools,
    api_cost,
    api_logs,
    api_assist,
)

app = FastAPI(title="The 4th Path — Control Panel", version="1.0.0")

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API 라우터 등록 ────────────────────────────────────────────────────────────
app.include_router(api_overview.router, prefix="/api")
app.include_router(api_content.router, prefix="/api")
app.include_router(api_analytics.router, prefix="/api")
app.include_router(api_novels.router, prefix="/api")
app.include_router(api_settings.router, prefix="/api")
app.include_router(api_connections.router, prefix="/api")
app.include_router(api_tools.router, prefix="/api")
app.include_router(api_cost.router, prefix="/api")
app.include_router(api_logs.router, prefix="/api")
app.include_router(api_assist.router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "The 4th Path Control Panel"}


# ── 정적 파일 서빙 (프론트엔드 빌드 결과) — API 라우터보다 나중에 등록 ──────────
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str = ""):
        # API 경로는 위 라우터가 처리 — 여기는 SPA 라우팅용
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"status": "frontend not built — run: npm run build"}
