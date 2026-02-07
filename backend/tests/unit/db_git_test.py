import subprocess
from pathlib import Path

from codex_graph import db


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_get_git_commit_info_returns_metadata(tmp_path: Path) -> None:
    _run_git(["init"], tmp_path)
    _run_git(["config", "user.name", "Test Author"], tmp_path)
    _run_git(["config", "user.email", "author@example.com"], tmp_path)

    file_path = tmp_path / "sample.py"
    file_path.write_text("print('hello')\n", encoding="utf-8")

    _run_git(["add", str(file_path)], tmp_path)
    _run_git(
        [
            "-c",
            "user.name=Test Author",
            "-c",
            "user.email=author@example.com",
            "commit",
            "-m",
            "feat: add sample",
        ],
        tmp_path,
    )

    info = db._get_git_commit_info(str(file_path))

    assert info is not None
    assert info.commit_id == _run_git(["rev-parse", "HEAD"], tmp_path)
    assert info.author == "Test Author"
    assert info.timestamp == _run_git(["log", "-1", "--format=%aI"], tmp_path)


def test_get_git_commit_info_returns_none_outside_repo(tmp_path: Path) -> None:
    file_path = tmp_path / "orphan.py"
    file_path.write_text("print('orphan')\n", encoding="utf-8")

    assert db._get_git_commit_info(str(file_path)) is None
