"""Package the TariffTrail API for AWS Lambda (zip + Lambda Web Adapter), without Docker.

    python infra/build_lambda.py            # writes build/lambda/tarifftrail-api.zip

The zip holds the FastAPI app (`tariff_trail/`), Linux wheels for its few dependencies (boto3 comes with the
Lambda runtime), and only the data the API reads: the HTS tree, the precedent index and the labelled products.
`run.sh` is the handler; the Lambda Web Adapter layer runs it and streams its Server-Sent Events.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "lambda"
PKG = BUILD / "pkg"
ZIP = BUILD / "tarifftrail-api.zip"

REQUIREMENTS = ["fastapi", "uvicorn", "numpy", "pydantic"]
DATA = [
    "data/raw/hts_full.json",
    "data/hts_sections.json",
    "data/hts_release.json",
    "data/precedents/vectors.npy",
    "data/precedents/meta.jsonl",
    "data/eval/dev.jsonl",
    "data/eval/test.jsonl",
]
RUN_SH = "#!/bin/bash\nexec python -m uvicorn tariff_trail.web.app:app --host 0.0.0.0 --port ${PORT:-8080}\n"


def main() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    PKG.mkdir(parents=True)

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--no-warn-conflicts", "--target", str(PKG), "--platform", "manylinux2014_x86_64",
         "--implementation", "cp", "--python-version", "3.12", "--only-binary=:all:", *REQUIREMENTS],
        check=True)
    for path in list(PKG.rglob("__pycache__")) + [p for p in PKG.rglob("tests") if p.is_dir()]:
        shutil.rmtree(path, ignore_errors=True)
    for path in PKG.glob("bin"):
        shutil.rmtree(path, ignore_errors=True)

    shutil.copytree(ROOT / "tariff_trail", PKG / "tariff_trail", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for rel in DATA:
        src = ROOT / rel
        if not src.exists():
            raise SystemExit(f"missing {rel}: run the data steps in the README first")
        (PKG / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, PKG / rel)
    (PKG / "run.sh").write_bytes(RUN_SH.encode())  # LF endings: it runs on Linux

    unzipped = 0
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(PKG.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(PKG).as_posix()
            info = zipfile.ZipInfo.from_file(path, rel)
            mode = 0o755 if rel == "run.sh" or path.suffix == ".so" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
            unzipped += path.stat().st_size
    print(f"{ZIP.relative_to(ROOT)}: {ZIP.stat().st_size / 1e6:.1f} MB zipped, {unzipped / 1e6:.1f} MB unzipped")
    if unzipped > 250_000_000:
        raise SystemExit("over Lambda's 250 MB unzipped limit")


if __name__ == "__main__":
    main()
