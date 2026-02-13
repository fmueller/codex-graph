import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitCommitInfo:
    commit_id: str
    author: str
    timestamp: str


def get_git_repo_root(start_dir: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(start_dir), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    root = result.stdout.strip()
    if not root:
        return None
    return Path(root)


def get_git_commit_info(file_path: str) -> GitCommitInfo | None:
    resolved = Path(file_path).resolve()
    repo_root = get_git_repo_root(resolved.parent)
    if repo_root is None:
        return None
    try:
        rel_path = resolved.relative_to(repo_root)
    except ValueError:
        return None
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "log",
            "-1",
            "--format=%H%x1f%an%x1f%aI",
            "--",
            str(rel_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    parts = output.split("\x1f")
    if len(parts) != 3:
        return None
    commit_id, author, timestamp = parts
    return GitCommitInfo(commit_id=commit_id, author=author, timestamp=timestamp)
