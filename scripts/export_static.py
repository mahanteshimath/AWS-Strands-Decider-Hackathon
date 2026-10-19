"""Export the demo UI as a static site (recorded replays only) for Amplify Hosting.

    python scripts/export_static.py            # writes site/

The live endpoint needs a Strands Decider host, so the static site is replay-only and says so.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tariff_trail.web import app as web  # noqa: E402

OUT = ROOT / "site"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "api" / "replay").mkdir(parents=True)

    html = (web.STATIC / "index.html").read_text(encoding="utf-8")
    (OUT / "index.html").write_text(html.replace('"/static/', '"'), encoding="utf-8")

    js = (web.STATIC / "app.js").read_text(encoding="utf-8")
    js = js.replace("`/api/replay/${encodeURIComponent(id)}`", "`api/replay/${encodeURIComponent(id)}.json`")
    js = js.replace('"/api/health"', '"api/health.json"').replace('"/api/replays"', '"api/replays.json"')
    (OUT / "app.js").write_text(js, encoding="utf-8")
    css = (web.STATIC / "style.css").read_text(encoding="utf-8")
    (OUT / "style.css").write_text(css.replace("url(/static/", "url("), encoding="utf-8")
    shutil.copytree(web.STATIC / "fonts", OUT / "fonts")

    release = web.tree.release.get("description")
    (OUT / "api" / "health.json").write_text(json.dumps({"live": False, "hts_release": release}), encoding="utf-8")

    listing = web.replays()
    (OUT / "api" / "replays.json").write_text(json.dumps(listing), encoding="utf-8")
    for item in listing:
        data = web.replay(item["id"])
        (OUT / "api" / "replay" / f"{item['id']}.json").write_text(json.dumps(data), encoding="utf-8")

    (OUT / "404.html").write_text("<!doctype html><meta charset=utf-8><a href=\"/\">TariffTrail</a>", encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"exported {len(listing)} replays, {size / 1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
