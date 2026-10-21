"""Export the demo UI as a static site for Amplify Hosting.

    python scripts/export_static.py                                   # replay-only copy -> site/
    python scripts/export_static.py --api https://xxxx.lambda-url.us-east-1.on.aws

The page, the 392 recorded replays and a fallback health file are plain static files. With `--api`
(or TT_API_URL) the page also talks to the cloud copy of the server for Classify hosted, Simulate and
New product. There is never a local Decider on the static site, so "Classify local" is hidden there.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tariff_trail.web import app as web  # noqa: E402

OUT = ROOT / "site"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default=os.environ.get("TT_API_URL", ""), help="base URL of the cloud API (optional)")
    api = parser.parse_args().api.strip().rstrip("/")

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "api" / "replay").mkdir(parents=True)

    html = (web.STATIC / "index.html").read_text(encoding="utf-8")
    (OUT / "index.html").write_text(html.replace('"/static/', '"'), encoding="utf-8")
    shutil.copy(web.STATIC / "app.js", OUT / "app.js")
    css = (web.STATIC / "style.css").read_text(encoding="utf-8")
    (OUT / "style.css").write_text(css.replace("url(/static/", "url("), encoding="utf-8")
    shutil.copytree(web.STATIC / "fonts", OUT / "fonts")

    config = {"staticReplays": True, "local": False, **({"api": api} if api else {})}
    (OUT / "config.js").write_text(
        "// Written by scripts/export_static.py.\nwindow.TARIFFTRAIL = " + json.dumps(config) + ";\n", encoding="utf-8")

    release = web.tree.release.get("description")
    (OUT / "api" / "health.json").write_text(json.dumps({"live": False, "local": False, "hts_release": release}), encoding="utf-8")

    listing = web.replays()
    (OUT / "api" / "replays.json").write_text(json.dumps(listing), encoding="utf-8")
    for item in listing:
        data = web.replay(item["id"])
        (OUT / "api" / "replay" / f"{item['id']}.json").write_text(json.dumps(data), encoding="utf-8")

    (OUT / "404.html").write_text("<!doctype html><meta charset=utf-8><a href=\"/\">TariffTrail</a>", encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"exported {len(listing)} replays, {size / 1e6:.1f} MB -> {OUT} ({'API ' + api if api else 'replay-only'})")


if __name__ == "__main__":
    main()
