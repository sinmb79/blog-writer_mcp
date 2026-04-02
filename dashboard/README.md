# The 4th Path — Control Panel

미디어 엔진 컨트롤 패널 (React + FastAPI)

## 구조

```
dashboard/
├── backend/
│   ├── server.py         # FastAPI 메인
│   ├── api_overview.py   # 개요 탭 API
│   ├── api_content.py    # 콘텐츠 탭 API
│   ├── api_analytics.py  # 분석 탭 API
│   ├── api_novels.py     # 소설 탭 API
│   ├── api_settings.py   # 설정 API
│   ├── api_connections.py# 연결 상태 API
│   ├── api_tools.py      # 도구 선택 API
│   ├── api_cost.py       # 비용 모니터 API
│   └── api_logs.py       # 로그 API
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── pages/
    │   │   ├── Overview.jsx
    │   │   ├── Content.jsx
    │   │   ├── Analytics.jsx
    │   │   ├── Novel.jsx
    │   │   ├── Settings.jsx
    │   │   ├── Logs.jsx
    │   │   └── settings/
    │   │       ├── Connections.jsx
    │   │       ├── ToolSelect.jsx
    │   │       ├── Distribution.jsx
    │   │       ├── Quality.jsx
    │   │       └── CostMonitor.jsx
    │   └── styles/
    │       └── theme.css
    ├── package.json
    ├── vite.config.js
    └── tailwind.config.js
```

## 설치 및 실행

### 필수 요건

- Python 3.9+
- Node.js 18+
- npm 9+

### 백엔드 의존성 설치

```bash
cd <project-root>
venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 프론트엔드 의존성 설치

```bash
cd <project-root>/dashboard/frontend
npm install
```

## 실행 방법

### Windows (더블클릭)

- **프로덕션**: `start.bat` 더블클릭
- **개발 모드**: `start_dev.bat` 더블클릭

두 스크립트 모두 프로젝트 `venv\Scripts\python.exe`가 없으면 즉시 중단합니다.

### Linux/Mac

```bash
# 프로덕션 (프론트 빌드 후 백엔드만)
bash dashboard/start.sh

# 개발 모드 (Vite 핫리로드 + 백엔드 reload)
bash dashboard/start.sh dev
```

### 수동 실행

```bash
# 터미널 1 — 백엔드
cd <project-root>
venv\Scripts\python.exe blog_runtime.py server --reload

# 터미널 2 — 프론트엔드 (개발)
cd <project-root>/dashboard/frontend
npm run dev

# 또는 프론트 빌드 (프로덕션)
npm run build
```

## 접속

| 모드 | URL |
|------|-----|
| 프로덕션 | http://localhost:8080 |
| 개발(프론트) | http://localhost:5173 |
| API 문서 | http://localhost:8080/docs |

## 탭 구성

| 탭 | 기능 |
|----|------|
| 개요 | KPI 카드 · 파이프라인 상태 · 코너별 비율 · 활동 로그 |
| 콘텐츠 | 칸반 보드 · 승인/거부 |
| 분석 | 방문자 추이 · 코너별 성과 · 인기글 |
| 소설 | 연재 관리 · 에피소드 생성 |
| 설정 | AI 연결 · 도구 선택 · 배포채널 · 품질 · 비용 |
| 로그 | 시스템 로그 필터/검색 |

## Tailscale 외부 접속

```bash
# 백엔드를 0.0.0.0으로 바인딩하면 Tailscale IP로 접속 가능
venv\Scripts\python.exe blog_runtime.py server
# 접속: http://<tailscale-ip>:8080
```
