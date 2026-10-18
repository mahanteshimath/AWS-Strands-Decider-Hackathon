"""Recover an evaluation results file that was replaced while a run was still appending to it.

The running process keeps the original (now unlinked) file open, so its full contents are still
readable through /proc/<pid>/fd. This copies them back, keeps only complete JSON lines, and,
with --stop, ends the run so it can be restarted (run_eval.py resumes and skips finished cases).

    python scripts/recover_results.py eval/results/dev/tariff_trail.jsonl --stop
"""

from __future__ import annotations

import argparse
import json
import os
import signal
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    target = Path(args.path).resolve()

    best: tuple[int, int, bytes] | None = None  # (rows, pid, data)
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmdline = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if "run_eval.py" not in cmdline:
            continue
        for fd in (proc / "fd").iterdir():
            try:
                link = os.readlink(fd)
            except OSError:
                continue
            if link.startswith(str(target)):
                data = fd.read_bytes()
                rows = data.count(b"\n")
                print(f"pid {proc.name}: {link} ({rows} lines)")
                if best is None or rows > best[0]:
                    best = (rows, int(proc.name), data)

    if best is None:
        print("no running evaluation holds that file")
        return
    rows, pid, data = best
    good = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        try:
            json.loads(line)
            good.append(line)
        except json.JSONDecodeError:
            pass
    current = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    if len(good) <= len(current):
        print(f"on-disk file already has {len(current)} rows; nothing to recover")
    else:
        target.write_text("\n".join(good) + "\n", encoding="utf-8")
        print(f"recovered {len(good)} rows into {target} (was {len(current)})")
    if args.stop:
        os.kill(pid, signal.SIGTERM)
        print(f"stopped pid {pid}")


if __name__ == "__main__":
    main()
