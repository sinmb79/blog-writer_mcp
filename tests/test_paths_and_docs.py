from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_no_hardcoded_workspace_drive_paths():
    tracked = [
        ROOT / "blog.cmd",
        ROOT / "README.md",
        ROOT / "dashboard" / "README.md",
        ROOT / "blog_engine_cli.py",
    ]
    bad_tokens = ["D:\\workspace\\blog-writer", "D:/workspace/blog-writer"]

    for path in tracked:
        text = path.read_text(encoding="utf-8")
        for token in bad_tokens:
            assert token not in text, f"{path} still contains {token}"


def test_readme_does_not_mark_unfinished_distribution_as_complete():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "코드 완료 | Instagram, X 배포" not in text


def test_readme_contains_release_verification_commands():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python -m pytest tests -v" in text
    assert "python -m compileall blogwriter bots dashboard blog_engine_cli.py blog_runtime.py runtime_guard.py" in text
    assert "cd dashboard/frontend && npm run build" in text


def test_pyproject_uses_editable_compatible_build_backend():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"


def test_pyproject_includes_blogwriter_mcp_package_and_mcp_dependency():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    include_patterns = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert any(dep.startswith("mcp>=") for dep in dependencies)
    assert "blogwriter_mcp*" in include_patterns


def test_env_example_mentions_google_search_console_site():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "GOOGLE_SEARCH_CONSOLE_SITE=" in env_example


def test_readme_mentions_blog_writer_mcp_server():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python -m blogwriter_mcp.server" in text
    assert "http://127.0.0.1:8766/mcp" in text
