# blog-writer-mcp

<p align="center">
  <img src="https://img.shields.io/badge/MCP-Streamable_HTTP-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/Python-3.11+-green?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" />
  <img src="https://img.shields.io/badge/Claude-Desktop-purple?style=flat-square" />
  <img src="https://img.shields.io/badge/ChatGPT-Developer_Mode-black?style=flat-square" />
</p>

<p align="center">
  <b>AI 블로그 자동화 MCP 서버</b><br/>
  <i>당신이 사랑한 것들에서 당신만의 목소리를 찾아드립니다</i>
</p>

<p align="center">
  <b>AI Blog Automation MCP Server</b><br/>
  <i>We find your voice in the things you love</i>
</p>

---

## 홍익인간(弘益人間) — 널리 인간을 이롭게 한다

이 프로젝트는 **글쓰는 능력이 없어도 자신의 목소리로 세상에 말을 걸 수 있도록** 만들어졌습니다.
파울로 코엘료를 좋아하고, 그리스인 조르바에 감동받고, 인터스텔라를 사랑한다면 -
그 감수성이 그대로 당신의 글이 됩니다.

*This project was built so that anyone - regardless of writing ability - can speak to the world in their own voice.
If you love Paulo Coelho, were moved by Zorba the Greek, and feel something watching Interstellar -
that sensibility becomes your writing.*

> **MIT 라이선스 · 완전 무료 · 누구든 사용·수정·배포 가능**
> MIT License · Completely free · Use, modify, distribute freely

---

## 목차 / Table of Contents

- [이게 뭔가요?](#이게-뭔가요--what-is-this)
- [창작 DNA란?](#창작-dna란--what-is-creative-dna)
- [주요 기능](#주요-기능--features)
- [설치 방법](#설치-방법--installation)
- [Claude Desktop 연결](#claude-desktop-연결--claude-desktop-setup)
- [ChatGPT 연결](#chatgpt-연결--chatgpt-setup)
- [사용 방법](#사용-방법--how-to-use)
- [도구 목록](#도구-목록--tools)
- [프로젝트 구조](#프로젝트-구조--project-structure)
- [FAQ](#faq)

---

## 이게 뭔가요? / What is this?

**blog-writer-mcp**는 Claude나 ChatGPT에 직접 연결해서 쓰는 블로그 자동화 도구입니다.

*blog-writer-mcp is a blog automation tool that connects directly to Claude or ChatGPT.*

### 기존 블로그 자동화 도구와 뭐가 다른가요?

| | 기존 도구 | blog-writer-mcp |
|---|---|---|
| **글쓰기 기반** | 당신이 쓴 글을 학습 | 당신이 **사랑한 것들**을 학습 |
| **대상** | 글을 쓸 수 있는 사람 | 글을 못 써도 OK |
| **인터페이스** | 별도 웹 UI 필요 | Claude / ChatGPT 대화창 |
| **개인화 방식** | 문체 모방 | 세계관·감수성 반영 |
| **가격** | 월정액 유료 | **완전 무료** |

### How is this different from other blog tools?

| | Other tools | blog-writer-mcp |
|---|---|---|
| **Writing basis** | Learns from your past writing | Learns from what you **love** |
| **Target users** | People who can write | Anyone, even non-writers |
| **Interface** | Separate web UI | Claude / ChatGPT chat |
| **Personalization** | Style mimicking | Worldview & sensibility |
| **Price** | Monthly subscription | **Completely free** |

---

## 창작 DNA란? / What is Creative DNA?

대부분의 AI 글쓰기 도구는 "당신이 쓴 글을 업로드하면 그 스타일로 써드립니다"라고 합니다.
그런데 **글을 못 쓰기 때문에 도움받으러 온 사람에게는 소용이 없습니다.**

*Most AI writing tools say "upload your past writing and we'll match your style."
But that's useless for people who came for help precisely because they can't write.*

창작 DNA는 다릅니다. 당신이 **감동받은 것들**에서 당신의 세계관을 추출합니다.

*Creative DNA is different. It extracts your worldview from the things that **moved you**.*

```text
좋아하는 작가  →  문체의 깊이와 호흡
좋아하는 책    →  주제의식과 인생관
좋아하는 영화  →  감정의 결과 스케일
좋아하는 애니  →  가치관과 전달 방식

Favorite authors  →  Depth and rhythm of writing
Favorite books    →  Themes and life philosophy
Favorite films    →  Emotional register and scale
Favorite anime    →  Values and how they're conveyed
```

예를 들어 / For example:

> 파울로 코엘료 + 그리스인 조르바 + 인터스텔라 + 지브리
>
> Paulo Coelho + Zorba the Greek + Interstellar + Ghibli

이 조합에서 시스템은 다음을 추출합니다:

*From this combination, the system extracts:*

- **테마**: 자유, 여정, 우주적 연결, 삶의 긍정
- **문체**: 단순한 문장 안에 깊은 진리 / Simple sentences carrying deep truths
- **금지 톤**: 설교적, 냉소적, 기계적 / Preachy, cynical, mechanical

그 결과, AI가 쓴 글인데 당신이 쓴 것처럼 느껴집니다.

*The result: AI-written content that feels like *you* wrote it.*

---

## 주요 기능 / Features

### 창작 DNA 시스템 / Creative DNA System
- 좋아하는 작가·책·영화에서 글쓰기 세계관 자동 추출
- Automatically extracts writing worldview from favorite authors, books, films
- 한 번 설정하면 이후 모든 글에 자동 적용
- Set once, applied to all future writing

### AI 글쓰기 / AI Writing
- 트렌드 수집 → 주제 선정 → 글 작성 → 발행 전 과정 자동화
- Full pipeline: trend collection → topic selection → writing → publishing
- Google Blogger 자동 발행 / Auto-publish to Google Blogger
- 이미지 자동 생성 첨부 / Auto-generate and attach images

### SEO + GEO 최적화 / SEO + GEO Optimization
- 메타 태그, 헤딩 구조, 키워드 밀도 자동 최적화
- Auto-optimize meta tags, heading structure, keyword density
- GEO (Generative Engine Optimization): ChatGPT·Claude·Perplexity 인용 최적화
- GEO: Optimize for citations in AI search engines

### 성과 피드백 루프 / Performance Feedback Loop
- Google Search Console 연동으로 실제 트래픽 분석
- Analyze real traffic via Google Search Console
- 성과 좋은 글 패턴 → 다음 주제 추천 자동화
- High-performing patterns → automated next topic recommendations

### 쿠팡 파트너스 자동 링크 / Auto Affiliate Links
- 글 내용에 맞는 쿠팡 링크 자동 삽입
- Automatically insert relevant Coupang affiliate links

---

## 설치 방법 / Installation

### 사전 요구사항 / Prerequisites

- Python 3.11 이상 / Python 3.11 or higher
- Node.js 18 이상 (프론트엔드 빌드용) / Node.js 18+ (for frontend build)
- Claude Desktop 또는 ChatGPT Plus/Pro 계정
- Claude Desktop or ChatGPT Plus/Pro account
- Google Blogger 블로그 / Google Blogger blog

### 1단계 — 코드 다운로드 / Step 1 — Download

```bash
git clone https://github.com/sinmb79/blog-writer_mcp.git
cd blog-writer_mcp
```

### 2단계 — 환경 설정 / Step 2 — Environment Setup

```bash
# Windows
scripts\setup.bat

# Mac/Linux
pip install -e .
```

`setup.bat`이 자동으로 / `setup.bat` automatically:
- Python 가상환경 생성 / Creates Python virtual environment
- 패키지 설치 / Installs packages
- 필요한 디렉토리 생성 / Creates required directories
- 한글 폰트 다운로드 / Downloads Korean fonts

### 3단계 — API 키 설정 / Step 3 — API Keys

```bash
copy .env.example .env
```

`.env` 파일을 열어서 아래 값을 입력합니다 / Open `.env` and fill in:

```env
# Google Blogger 인증 / Google Blogger Auth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
# 아래 명령어 실행 후 자동 입력됨
# Run the command below and this will be auto-filled:
# python scripts/get_token.py
GOOGLE_REFRESH_TOKEN=

# 블로그 ID (Blogger URL에서 확인) / Blog ID (found in Blogger URL)
BLOG_MAIN_ID=your_18_digit_blog_id

# Telegram 알림 (선택) / Telegram notifications (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# 쿠팡 파트너스 (선택) / Coupang Partners (optional)
COUPANG_ACCESS_KEY=
COUPANG_SECRET_KEY=
```

### 4단계 — Google 인증 / Step 4 — Google Authentication

```bash
python scripts/get_token.py
```

브라우저가 열리면 Google 계정으로 로그인 → 자동으로 `token.json` 저장됩니다.

*A browser will open. Log in with your Google account → `token.json` is saved automatically.*

### 5단계 — MCP 서버 실행 / Step 5 — Start MCP Server

```bash
python -m blogwriter_mcp.server
```

`http://127.0.0.1:8766/mcp` 에서 서버가 실행됩니다.

*Server runs at `http://127.0.0.1:8766/mcp`.*

---

## Claude Desktop 연결 / Claude Desktop Setup

### Claude Desktop이란? / What is Claude Desktop?

Anthropic이 만든 AI 앱입니다. [claude.ai/download](https://claude.ai/download)에서 무료로 다운로드할 수 있습니다.
MCP 서버를 연결하면 Claude가 직접 블로그 도구를 사용할 수 있습니다.

*Claude Desktop is an AI app by Anthropic. Download free at [claude.ai/download](https://claude.ai/download).
Connect an MCP server and Claude can directly use blog tools.*

### 설정 방법 / Setup

**설정 파일 위치 / Config file location:**
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

파일을 열어 아래 내용을 추가합니다 / Open the file and add:

```json
{
  "mcpServers": {
    "blog_writer": {
      "command": "mcp-remote",
      "args": ["http://127.0.0.1:8766/mcp"]
    }
  }
}
```

**Claude Desktop을 재시작합니다 / Restart Claude Desktop.**

입력창 하단에 도구 아이콘이 생기면 연결 성공입니다.

*If you see a tools icon at the bottom of the input box, the connection is successful.*

---

## ChatGPT 연결 / ChatGPT Setup

> **필요 조건 / Requirements**: ChatGPT Plus, Pro, Team, 또는 Enterprise 구독
> ChatGPT Plus, Pro, Team, or Enterprise subscription required

ChatGPT는 `localhost`에 직접 접속할 수 없어서 터널링이 필요합니다.

*ChatGPT cannot access `localhost` directly, so tunneling is required.*

### 1단계 — ngrok 설치 / Step 1 — Install ngrok

[ngrok.com](https://ngrok.com)에서 무료 계정 생성 후 설치합니다.

*Create a free account at [ngrok.com](https://ngrok.com) and install.*

```bash
ngrok http 8766
```

`https://abc123.ngrok.app` 같은 주소가 생성됩니다.

*A URL like `https://abc123.ngrok.app` will be generated.*

### 2단계 — ChatGPT Connector 등록 / Step 2 — Register ChatGPT Connector

1. ChatGPT 설정 열기 / Open ChatGPT Settings
2. **Connectors → Developer Mode 활성화 / Enable Developer Mode**
3. **Create** 클릭 / Click Create
4. 아래와 같이 입력 / Fill in:

```text
Connector name:  blog-writer-mcp
Description:     AI 블로그 자동화. 창작 DNA로 당신만의 목소리로 씁니다.
                 AI blog automation. Write in your own voice with Creative DNA.
Connector URL:   https://abc123.ngrok.app/mcp
```

> URL이 바뀌면 Connector를 업데이트해야 합니다.
> Update the Connector when the tunnel URL changes.

---

## 사용 방법 / How to Use

### 처음 시작하기 — 창작 DNA 설정 / Getting Started — Set Your Creative DNA

Claude Desktop이나 ChatGPT에서 이렇게 말하세요 / Say this in Claude Desktop or ChatGPT:

```text
내 창작 DNA를 설정해줘.

좋아하는 작가: 파울로 코엘료
좋아하는 책: 그리스인 조르바
좋아하는 영화: 인터스텔라
좋아하는 애니: 지브리 스타일 (자연, 교훈, 경이로움)
나의 키워드: 자유, 여정, 인간과 기술의 공존

---

Set my creative DNA.

Favorite author: Paulo Coelho
Favorite book: Zorba the Greek
Favorite film: Interstellar
Favorite anime style: Ghibli (nature, lessons, wonder)
My keywords: freedom, journey, human-technology coexistence
```

시스템이 취향을 분석해서 당신만의 글쓰기 세계관을 추출합니다. 한 번 설정하면 끝입니다.

*The system analyzes your preferences and extracts your unique writing worldview. Set it once and you're done.*

---

### 글 쓰기 / Write an Article

```text
오늘 AI 관련 트렌드 하나 골라서 블로그 글 써줘.
내 DNA 스타일로.

---

Pick one AI trend today and write a blog post.
Apply my DNA style.
```

Claude가 알아서 다음 흐름을 수행할 수 있습니다:

1. 트렌드 수집 (`blog_get_trending`)
2. 주제 선정 및 글 작성 (`blog_write_article`)
3. SEO 최적화 (`blog_optimize_seo`)
4. 이미지 생성 (`blog_generate_image`)
5. 쿠팡 링크 삽입 (`blog_insert_affiliate_links`)
6. 발행 (`blog_publish`)

---

### 성과 확인 / Check Performance

```text
최근 한 달 블로그 성과 보여줘. 다음에 뭘 쓰면 좋을지 추천도 해줘.

---

Show me last month's blog performance. Recommend what to write next.
```

---

### 전체 파이프라인 한 번에 / Full Pipeline at Once

```text
"AI와 인간의 미래" 주제로 전체 파이프라인 돌려줘.

---

Run the full pipeline on the topic "The future of AI and humanity."
```

---

## 도구 목록 / Tools

| 도구 이름 / Tool Name | 설명 / Description | 기반 / Based on |
|---|---|---|
| `blog_get_trending` | 트렌드 수집 / Collect trends | `collector_bot.py` |
| `blog_write_article` | 글 작성 (DNA 적용) / Write article (with DNA) | `writer_bot.py` |
| `blog_generate_image` | 이미지 생성 / Generate image | `image_bot.py` |
| `blog_optimize_seo` | SEO + GEO 최적화 / SEO + GEO optimization | `article_parser.py` + `seo_optimizer.py` |
| `blog_insert_affiliate_links` | 쿠팡 링크 삽입 / Insert affiliate links | `linker_bot.py` |
| `blog_publish` | Blogger 발행 / Publish to Blogger | `publisher_bot.py` |
| `blog_get_analytics` | 성과 분석 / Performance analytics | `analytics_bot.py` |
| `blog_full_pipeline` | 전체 자동화 / Full automation | `assist_bot.py` + `server.py` |
| `blog_set_creative_dna` | 창작 DNA 설정 / Set Creative DNA | `creative_dna.py` |
| `blog_get_performance_feedback` | 성과 피드백 / Performance feedback | `performance_feedback.py` |

---

## 프로젝트 구조 / Project Structure

```text
blog-writer-mcp/
├── bots/                      # 핵심 로직 / Core logic
│   ├── collector_bot.py       # 트렌드 수집 / Trend collection
│   ├── writer_bot.py          # AI 글쓰기 / AI writing
│   ├── publisher_bot.py       # Blogger 발행 / Blogger publishing
│   ├── image_bot.py           # 이미지 생성 / Image generation
│   ├── analytics_bot.py       # 성과 분석 / Analytics
│   ├── linker_bot.py          # 쿠팡 링크 / Coupang links
│   └── engine_loader.py       # AI 엔진 팩토리 / AI engine factory
│
├── blogwriter_mcp/            # MCP 서버 / MCP server
│   ├── server.py              # FastMCP HTTP, :8766
│   └── tools/
│       ├── creative_dna.py    # 창작 DNA / Creative DNA
│       ├── seo_optimizer.py   # SEO + GEO
│       └── performance_feedback.py
│
├── config/
│   ├── engine.json            # AI 엔진 설정 / AI engine config
│   └── creative_dna.json      # DNA 설정 / DNA config
│
├── templates/                 # 프롬프트 템플릿 / Prompt templates
├── tests/                     # 테스트 (pytest 22 passed)
├── .env.example               # 환경변수 예시 / Env template
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## FAQ

**Q: 글쓰기 경험이 전혀 없어도 되나요?**

됩니다. 오히려 이 도구가 더 필요한 분입니다. 당신이 감동받은 것들만 있으면 됩니다.

*Yes. In fact, this tool is made for you. All you need is the things that moved you.*

---

**Q: 창작 DNA를 설정하지 않으면 어떻게 되나요?**

일반적인 AI 글쓰기로 작동합니다. 언제든지 DNA를 설정하면 즉시 적용됩니다.

*It works as a regular AI writer. Set your DNA anytime and it applies immediately.*

---

**Q: Blogger 외에 다른 플랫폼도 지원하나요?**

현재 버전은 Google Blogger 기준입니다. WordPress, 네이버 블로그 지원은 이후 버전에서 확장할 수 있습니다.

*Current version supports Google Blogger. WordPress and Naver Blog support can be added in a future version.*

---

**Q: Claude Desktop이 없으면 쓸 수 없나요?**

Claude Desktop 또는 ChatGPT Plus/Pro 중 하나만 있으면 됩니다.

*You need either Claude Desktop or ChatGPT Plus/Pro - just one of them.*

---

**Q: API 키가 많이 필요한가요?**

기본 기능은 Google 계정만 있으면 됩니다. Telegram, 쿠팡, Search Console은 모두 선택 사항입니다.

*Basic features only require a Google account. Telegram, Coupang, and Search Console are all optional.*

---

**Q: 상업적으로 사용해도 되나요?**

MIT 라이선스입니다. 상업적 사용 포함 제한 없이 자유롭게 사용하실 수 있습니다.

*MIT License. You can use it commercially and without restrictions.*

---

## 기여 / Contributing

버그 리포트, 기능 제안, PR 모두 환영합니다.

*Bug reports, feature suggestions, and PRs are all welcome.*

```bash
# 로컬 개발 / Local development
git clone https://github.com/sinmb79/blog-writer_mcp.git
cd blog-writer_mcp
pip install -e ".[dev]"
pytest tests/ -v
```

---

## 관련 프로젝트 / Related Projects

- [sinmb79/blog-writer](https://github.com/sinmb79/blog-writer) - 원본 블로그 자동화 / Original blog automation

---

## 만든 사람 / Author

**22B Labs** (sinmb79)

*The 4th Path: `P4 := ⟨H⊕A⟩ ↦ Ω`*

인간(H)과 AI(A)가 결합하여 더 나은 세상(Ω)을 향해.

*Human (H) and AI (A) together, moving toward a better world (Ω).*

---

<p align="center">
  <i>홍익인간(弘益人間) - 널리 인간을 이롭게 한다</i><br/>
  <i>Broadly benefit humanity</i>
</p>
