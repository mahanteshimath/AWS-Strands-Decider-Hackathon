"""Download the prebuilt retrieval index (Titan embeddings of 7,024 pre-2026 CBP rulings).

Saves you `python data/fetch_cross.py` + `python -m tariff_trail.precedents build` (hours of CROSS
downloads and ~7,000 Titan calls). The rulings are US government works (public domain); the vectors
are Amazon Titan Text Embeddings V2 (512 dimensions, normalised), so queries must use the same model.
Outputs data/precedents/vectors.npy and data/precedents/meta.jsonl, checked against SHA-256 below.

    python data/fetch_precedents.py
"""

from __future__ import annotations

import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://github.com/mahanteshimath/AWS-Strands-Decider-Hackathon/releases/download/precedents-v1/precedents-v1.zip"
SHA256 = {
    "vectors.npy": "669ddb07bdff471355ed779eed047f8f75050d68215b647a5d045dd1c6876390",
    "meta.jsonl": "5283ffd19f34a39327391f16e0d14f5f30c5d8a26a3c2836dc88931bf9fb7faf",
}
OUT = Path(__file__).resolve().parent / "precedents"


def main() -> None:
    print(f"downloading {URL}")
    with urllib.request.urlopen(URL, timeout=120) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, digest in SHA256.items():
        data = archive.read(name)
        got = hashlib.sha256(data).hexdigest()
        if got != digest:
            raise SystemExit(f"{name}: sha256 {got} does not match {digest}")
        (OUT / name).write_bytes(data)
        print(f"  {name}: {len(data):,} bytes, sha256 ok")
    print(f"saved to {OUT}")


if __name__ == "__main__":
    main()
