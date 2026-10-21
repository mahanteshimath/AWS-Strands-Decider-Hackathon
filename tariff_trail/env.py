"""Read single settings from the process environment or the repo's `.env`, without exporting any of it.

`.env` may also hold AWS credentials; loading the whole file into `os.environ` would let them
override the AWS profile Bedrock uses. So callers ask for the names they need, nothing else leaks.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _from_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "[")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lower()] = value.split(" #", 1)[0].strip().strip('"').strip("'")
    return values


def env_value(*names: str, default: str = "", path: Path | None = None) -> str:
    """First non-empty value among `names`: the process environment wins, then `.env`. Case-insensitive."""
    for name in names:
        for variant in (name, name.upper()):
            if os.environ.get(variant):
                return os.environ[variant]
    file_values = _from_file(path or ENV_FILE)
    for name in names:
        if file_values.get(name.lower()):
            return file_values[name.lower()]
    return default
