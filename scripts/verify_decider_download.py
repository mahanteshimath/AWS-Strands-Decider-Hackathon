"""Verify the locally downloaded Decider + base model against ModelScope's published sha256s
and the Decider repo's own MANIFEST.sha256.  python scripts/verify_decider_download.py"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path.home() / ".cache" / "strands-decider"
REPOS = {
    "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610": ROOT / "strands-decider-2B-qwen3.5-v1-2610",
    "Qwen/Qwen3.5-2B-Base": ROOT / "Qwen3.5-2B-Base",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


bad = 0
for repo, dest in REPOS.items():
    url = f"https://modelscope.cn/api/v1/models/{repo}/repo/files?Revision=master&Recursive=true"
    files = [f for f in json.load(urllib.request.urlopen(url, timeout=60))["Data"]["Files"] if f["Type"] == "blob"]
    for f in files:
        path = dest / f["Path"]
        if not path.exists() or path.stat().st_size != f["Size"]:
            print(f"MISSING/SIZE {repo} {f['Path']}")
            bad += 1
        elif f.get("Sha256") and sha256(path) != f["Sha256"].lower():
            print(f"SHA MISMATCH {repo} {f['Path']}")
            bad += 1
    print(f"{repo}: {len(files)} files checked")

decider = REPOS["StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"]
for line in (decider / "MANIFEST.sha256").read_text().splitlines():
    want, rel = line.split(maxsplit=1)
    if sha256(decider / rel) != want:
        print(f"MANIFEST MISMATCH {rel}")
        bad += 1
print("ALL OK" if not bad else f"{bad} problems")
sys.exit(1 if bad else 0)
