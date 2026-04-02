"""
Legacy runtime CLI used by blog.cmd.
"""
from __future__ import annotations

import sys
import textwrap

import requests

from runtime_guard import ensure_project_runtime

ensure_project_runtime("blog CLI", ["requests"])

API = "http://localhost:8080/api"
TIMEOUT = 10


def _get(path: str) -> dict | list:
    response = requests.get(f"{API}{path}", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _post(path: str, data: dict | None = None) -> dict:
    response = requests.post(f"{API}{path}", json=data or {}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _content_items(data: dict, key: str) -> list:
    columns = data.get("columns", {})
    if key in columns:
        return columns.get(key, {}).get("cards", [])
    return data.get(key, [])


def _sep(char: str = "-", width: int = 60) -> None:
    print(char * width)


def cmd_status(_args: list[str]) -> None:
    try:
        overview = _get("/overview")
        pipeline = _get("/pipeline")
    except Exception as exc:
        print(f"[오류] 대시보드 연결 실패: {exc}")
        print("  먼저 '.\\blog.cmd server'로 서버를 실행하세요.")
        return

    kpi = overview.get("kpi", {})
    revenue = kpi.get("revenue", {})

    _sep()
    print("  The 4th Path 상태")
    _sep()
    print(f"  오늘 발행: {kpi.get('today', 0)}건")
    print(f"  이번 주:   {kpi.get('this_week', 0)}건")
    print(f"  누적 발행: {kpi.get('total', 0)}건")
    print(f"  수익 상태: {revenue.get('status', '-')}")
    _sep()

    print("  파이프라인")
    for step in pipeline.get("steps", []):
        label = step.get("label", step.get("name", step.get("id", "")))
        status = step.get("status", "waiting")
        last_run = step.get("last_run") or step.get("done_at") or "-"
        print(f"  - {label}: {status} ({last_run})")
    _sep()


def cmd_pipeline(_args: list[str]) -> None:
    pipeline = _get("/pipeline")
    _sep()
    print("  파이프라인 단계")
    _sep()
    for step in pipeline.get("steps", []):
        label = step.get("label", step.get("name", step.get("id", "")))
        print(f"  - {label}: {step.get('status', 'waiting')}")
        if step.get("last_run"):
            print(f"    마지막 실행: {step['last_run']}")
        if step.get("error"):
            print(f"    오류: {step['error']}")
    _sep()


def cmd_content(_args: list[str]) -> None:
    data = _get("/content")
    columns = [
        ("queue", "글감 큐"),
        ("writing", "작성 중"),
        ("review", "검수 대기"),
        ("published", "발행 완료"),
    ]

    _sep()
    print("  콘텐츠 큐 현황")
    _sep()
    for key, label in columns:
        items = _content_items(data, key)
        print(f"  {label}: {len(items)}개")
        for item in items[:3]:
            score = item.get("quality_score", item.get("score", ""))
            suffix = f" [점수:{score}]" if score else ""
            print(f"    - {item.get('title', '제목 없음')[:45]}{suffix}")
        if len(items) > 3:
            print(f"    ... 외 {len(items) - 3}개")
    _sep()


def cmd_review(_args: list[str]) -> None:
    items = _content_items(_get("/content"), "review")
    if not items:
        print("  검수 대기 콘텐츠가 없습니다.")
        return

    _sep()
    print(f"  검수 대기 {len(items)}개")
    _sep()
    for item in items:
        print(f"  ID: {item.get('id', '-')}")
        print(f"  제목: {item.get('title', '-')}")
        print(f"  코너: {item.get('corner', '-')}  점수: {item.get('quality_score', '-')}")
        if item.get("summary"):
            wrapped = textwrap.fill(
                item["summary"][:200],
                width=55,
                initial_indent="  ",
                subsequent_indent="  ",
            )
            print(f"  요약:\n{wrapped}")
        print(f"  승인: blog approve {item.get('id')} | 반려: blog reject {item.get('id')}")
        _sep("-")


def cmd_approve(args: list[str]) -> None:
    if not args:
        print("사용법: blog approve <id>")
        return

    content_id = args[0]
    result = _post(f"/content/{content_id}/approve")
    if result.get("ok") or result.get("success") or result.get("status") == "approved":
        print(f"승인 완료: {content_id}")
    else:
        print(f"오류: {result}")


def cmd_reject(args: list[str]) -> None:
    if not args:
        print("사용법: blog reject <id>")
        return

    content_id = args[0]
    result = _post(f"/content/{content_id}/reject")
    if result.get("ok") or result.get("success") or result.get("status") == "rejected":
        print(f"반려 완료: {content_id}")
    else:
        print(f"오류: {result}")


def cmd_sessions(_args: list[str]) -> None:
    sessions = _get("/assist/sessions")
    if not sessions:
        print("  수동 어시스트 세션이 없습니다.")
        return

    _sep()
    print(f"  수동 어시스트 세션 {len(sessions)}개")
    _sep()
    for session in sessions:
        assets = len(session.get("assets", []))
        print(f"  - {session['session_id']}")
        print(f"    제목: {(session.get('title') or session.get('url', ''))[:50]}")
        print(f"    상태: {session.get('status_label', session.get('status', '-'))}")
        print(f"    자산: {assets}개")
        _sep("-")


def cmd_session(args: list[str]) -> None:
    if not args:
        print("사용법: blog session <session_id>")
        return

    session_id = args[0]
    session = _get(f"/assist/session/{session_id}")

    _sep()
    print(f"  세션: {session_id}")
    print(f"  제목: {session.get('title', '-')}")
    print(f"  URL:  {session.get('url', '-')}")
    print(f"  상태: {session.get('status_label', session.get('status', '-'))}")
    _sep()

    prompts = session.get("prompts", {})
    if prompts.get("image_prompts"):
        print("  이미지 프롬프트")
        for prompt in prompts["image_prompts"]:
            print(f"  - {prompt.get('purpose', '')}")
            print(f"    KO: {prompt.get('ko', '')}")
            print(f"    EN: {prompt.get('en', '')}")
        _sep("-")

    if prompts.get("video_prompt"):
        video_prompt = prompts["video_prompt"]
        print("  영상 프롬프트")
        print(f"    KO: {video_prompt.get('ko', '')}")
        print(f"    EN: {video_prompt.get('en', '')}")
        _sep("-")

    narration = prompts.get("narration_script", "")
    if narration:
        print("  내레이션 스크립트")
        for line in textwrap.wrap(narration, 55):
            print(f"    {line}")
        _sep("-")


def cmd_assist(args: list[str]) -> None:
    if not args:
        print("사용법: blog assist <url>")
        return

    url = args[0]
    result = _post("/assist/session", {"url": url})
    session_id = result.get("session_id", "")
    print(f"세션 생성: {session_id}")
    print(f"URL: {url}")
    print(f"상태: {result.get('status_label', result.get('status', '-'))}")


def cmd_logs(args: list[str]) -> None:
    limit = int(args[0]) if args else 15
    data = _get(f"/logs?limit={limit}")
    logs = data if isinstance(data, list) else data.get("logs", [])

    _sep()
    print(f"  최근 로그 (최대 {limit}줄)")
    _sep()
    for log in logs[-limit:]:
        timestamp = log.get("time", log.get("timestamp", ""))[:16]
        print(f"  [{timestamp}] {log.get('module', '')}: {log.get('message', '')[:70]}")
    _sep()


def cmd_analytics(_args: list[str]) -> None:
    data = _get("/analytics")
    kpi = data.get("kpi", data)

    _sep()
    print("  분석 데이터")
    _sep()
    print(f"  방문자:    {kpi.get('visitors', 0):,}")
    print(f"  페이지뷰:  {kpi.get('pageviews', 0):,}")
    print(f"  평균 체류: {kpi.get('avg_duration_sec', kpi.get('avg_duration', '-'))}")
    print(f"  CTR:       {kpi.get('ctr', '-')}")

    top_posts = data.get("top_posts", [])
    if top_posts:
        _sep("-")
        print("  인기 글 TOP 5")
        for index, post in enumerate(top_posts[:5], 1):
            views = post.get("views", post.get("visitors", 0))
            print(f"  {index}. {post.get('title', '')[:45]} ({views}뷰)")
    _sep()


COMMANDS = {
    "status": cmd_status,
    "pipeline": cmd_pipeline,
    "content": cmd_content,
    "review": cmd_review,
    "approve": cmd_approve,
    "reject": cmd_reject,
    "sessions": cmd_sessions,
    "session": cmd_session,
    "assist": cmd_assist,
    "logs": cmd_logs,
    "analytics": cmd_analytics,
}

HELP = """
blog <command> [args]

  status              전체 상태 요약
  pipeline            파이프라인 단계별 상태
  content             콘텐츠 큐 현황
  review              검수 대기 목록
  approve <id>        콘텐츠 승인
  reject <id>         콘텐츠 반려
  sessions            수동 어시스트 세션 목록
  session <id>        특정 세션 상세 확인
  assist <url>        수동 어시스트 세션 시작
  logs [n]            최근 로그 확인
  analytics           분석 요약
"""


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP)
        return

    command = args[0].lower()
    rest = args[1:]

    if command not in COMMANDS:
        print(f"알 수 없는 명령: {command}")
        print(HELP)
        sys.exit(1)

    try:
        COMMANDS[command](rest)
    except requests.exceptions.ConnectionError:
        print("[오류] 대시보드에 연결할 수 없습니다.")
        print("  먼저 아래 명령으로 서버를 시작하세요.")
        print("    .\\blog.cmd server")
        print("    또는")
        print("    python blog_runtime.py server")
    except Exception as exc:
        print(f"[오류] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
