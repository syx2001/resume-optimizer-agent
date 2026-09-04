"""Read-only local repository tools used for current code facts."""

from pathlib import Path
import subprocess

from langchain_core.tools import tool


def _safe_path(repo_path: str, relative_path: str = ".") -> Path:
    root = Path(repo_path).resolve()
    target = (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Path is outside the repository")
    return target


@tool
def get_repository_tree(repo_path: str, max_depth: int = 3) -> list[str]:
    """List files in a local repository without leaving its root."""
    root = _safe_path(repo_path)
    result = []
    for path in root.rglob("*"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if len(path.relative_to(root).parts) <= max_depth:
            result.append(str(path.relative_to(root)))
    return sorted(result)


@tool
def read_repository_file(repo_path: str, path: str, max_chars: int = 30000) -> str:
    """Read a UTF-8 text file inside a repository."""
    target = _safe_path(repo_path, path)
    if not target.is_file():
        raise FileNotFoundError(path)
    return target.read_text(encoding="utf-8")[:max_chars]


@tool
def search_repository_code(repo_path: str, query: str, path: str = ".") -> list[dict]:
    """Search repository text files and return bounded line-based matches."""
    root = _safe_path(repo_path, path)
    results = []
    for file in root.rglob("*"):
        if not file.is_file() or ".git" in file.parts or "__pycache__" in file.parts:
            continue
        try:
            lines = file.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(lines, 1):
            if query.lower() in line.lower():
                results.append({"path": str(file.relative_to(Path(repo_path).resolve())), "line": number, "text": line[:500]})
                if len(results) >= 200:
                    return results
    return results


@tool
def get_git_diff(repo_path: str, base: str = "HEAD") -> dict:
    """Return read-only git diff information for a local repository."""
    root = _safe_path(repo_path)
    completed = subprocess.run(["git", "diff", base], cwd=root, capture_output=True, text=True, timeout=30, check=False)
    return {"ok": completed.returncode == 0, "returncode": completed.returncode, "diff": completed.stdout[-50000:], "stderr": completed.stderr[-5000:]}


REPOSITORY_READ_TOOLS = [get_repository_tree, read_repository_file, search_repository_code, get_git_diff]
