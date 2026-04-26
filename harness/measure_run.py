from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from loc_counter import count_all_files, count_python_loc


def tail(text: str | bytes | None, max_chars: int = 4000) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and measure a benchmark submission.")
    parser.add_argument("--submission-dir", type=Path, required=True)
    parser.add_argument("--command", required=True, help="Command to run, e.g. 'python run_experiment.py'")
    parser.add_argument("--metrics-out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=2700)
    parser.add_argument("--shell", action="store_true", help="Run command through the shell.")
    args = parser.parse_args()

    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()

    try:
        cmd = args.command if args.shell else shlex.split(args.command)
        proc = subprocess.run(
            cmd,
            cwd=args.submission_dir,
            capture_output=True,
            text=True,
            timeout=args.timeout_seconds,
            shell=args.shell,
        )
        timed_out = False
        return_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        return_code = None
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

    end = time.perf_counter()
    ended_at = datetime.now(timezone.utc).isoformat()

    metrics = {
        "command": args.command,
        "submission_dir": str(args.submission_dir),
        "started_at": started_at,
        "ended_at": ended_at,
        "runtime_seconds": round(end - start, 6),
        "timed_out": timed_out,
        "return_code": return_code,
        "stdout_tail": tail(stdout),
        "stderr_tail": tail(stderr),
        "loc": count_python_loc(args.submission_dir),
        "files": count_all_files(args.submission_dir),
    }

    args.metrics_out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0 if return_code == 0 and not timed_out else 1


if __name__ == "__main__":
    raise SystemExit(main())

