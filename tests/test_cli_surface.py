import subprocess
import sys

from click.testing import CliRunner

from blogwriter.cli import app


def test_packaged_cli_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "blogwriter.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "write" in result.stdout


def test_distribute_command_is_not_present_until_implemented():
    result = CliRunner().invoke(app, ["distribute"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_help_does_not_advertise_distribute_command():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "distribute" not in result.output
