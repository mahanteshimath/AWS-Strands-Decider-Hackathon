"""Zip the code and data the Decider host needs (forward-slash paths, unlike PowerShell 5.1's zip).

    python scripts/bundle.py OUT.zip
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = ["tariff_trail", "eval", "scripts", "tests", "examples", "data/eval", "data/precedents"]
FILES = ["pyproject.toml", "data/hts_sections.json", "data/hts_release.json", "data/raw/hts_full.json"]
SKIP_PARTS = {"__pycache__", "results"}


def main() -> None:
    out = Path(sys.argv[1])
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as bundle:
        paths = [ROOT / f for f in FILES] + sorted((ROOT / "data").glob("*.py"))
        for directory in DIRS:
            paths += [p for p in sorted((ROOT / directory).rglob("*")) if p.is_file()]
        for path in paths:
            relative = path.relative_to(ROOT)
            if SKIP_PARTS.intersection(relative.parts):
                continue
            bundle.write(path, relative.as_posix())
            count += 1
    print(f"{count} files, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
