import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "blog_engine_cli.py"


def load_blog_engine_cli():
    sys.modules.pop("blog_engine_cli", None)
    previous_runtime_guard = sys.modules.get("runtime_guard")

    stub = types.ModuleType("runtime_guard")
    stub.ensure_project_runtime = lambda *args, **kwargs: None
    sys.modules["runtime_guard"] = stub

    try:
        spec = importlib.util.spec_from_file_location("blog_engine_cli", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules["blog_engine_cli"] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop("blog_engine_cli", None)
        if previous_runtime_guard is None:
            sys.modules.pop("runtime_guard", None)
        else:
            sys.modules["runtime_guard"] = previous_runtime_guard


def test_content_command_reads_column_cards(monkeypatch, capsys):
    module = load_blog_engine_cli()
    monkeypatch.setattr(
        module,
        "_get",
        lambda _path: {
            "columns": {
                "queue": {"label": "글감큐", "cards": [{"title": "A"}]},
                "writing": {"label": "작성중", "cards": []},
                "review": {"label": "검수대기", "cards": []},
                "published": {"label": "발행완료", "cards": []},
            }
        },
    )

    module.cmd_content([])

    assert "A" in capsys.readouterr().out


def test_analytics_command_reads_nested_kpi(monkeypatch, capsys):
    module = load_blog_engine_cli()
    monkeypatch.setattr(
        module,
        "_get",
        lambda _path: {
            "kpi": {"visitors": 12, "pageviews": 34, "avg_duration_sec": 56, "ctr": 1.2},
            "top_posts": [{"title": "Top", "visitors": 99}],
        },
    )

    module.cmd_analytics([])

    out = capsys.readouterr().out
    assert "12" in out
    assert "34" in out
    assert "Top" in out
    assert "99" in out


def test_approve_command_accepts_success_flag(monkeypatch, capsys):
    module = load_blog_engine_cli()
    monkeypatch.setattr(module, "_post", lambda _path, data=None: {"success": True})

    module.cmd_approve(["article-1"])

    out = capsys.readouterr().out
    assert "article-1" in out
    assert "오류" not in out
