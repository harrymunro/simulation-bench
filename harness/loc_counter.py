from __future__ import annotations

from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "outputs",
    "results",
}


def iter_files(root: Path, suffixes: Iterable[str] = (".py",), exclude_dirs=None):
    exclude_dirs = set(exclude_dirs or DEFAULT_EXCLUDE_DIRS)
    root = Path(root)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        if path.suffix in suffixes:
            yield path


def count_file_lines(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    code_lines = 0
    comment_lines = 0
    blank_lines = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank_lines += 1
        elif stripped.startswith("#"):
            comment_lines += 1
        else:
            code_lines += 1

    return {
        "path": str(path),
        "total_lines": len(lines),
        "code_lines": code_lines,
        "comment_lines": comment_lines,
        "blank_lines": blank_lines,
    }


def count_python_loc(root: Path) -> dict:
    files = [count_file_lines(p) for p in iter_files(root, suffixes=(".py",))]
    return {
        "python_file_count": len(files),
        "total_lines": sum(f["total_lines"] for f in files),
        "code_lines": sum(f["code_lines"] for f in files),
        "comment_lines": sum(f["comment_lines"] for f in files),
        "blank_lines": sum(f["blank_lines"] for f in files),
        "files": files,
    }


def count_all_files(root: Path) -> dict:
    root = Path(root)
    all_files = [
        p for p in root.rglob("*")
        if p.is_file() and not any(part in DEFAULT_EXCLUDE_DIRS for part in p.parts)
    ]
    by_suffix = {}
    for p in all_files:
        suffix = p.suffix or "[no_suffix]"
        by_suffix[suffix] = by_suffix.get(suffix, 0) + 1

    return {
        "file_count": len(all_files),
        "by_suffix": dict(sorted(by_suffix.items())),
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()

    print(json.dumps({
        "loc": count_python_loc(args.root),
        "files": count_all_files(args.root),
    }, indent=2))

