"""Download the current US Harmonized Tariff Schedule (HTS) from USITC.

The HTS is a US government work (public domain). Outputs:
  data/raw/hts_full.json    every HTS row: htsno, indent, description, duty columns
  data/hts_release.json     which HTS revision the rows came from
  data/hts_sections.json    the 22 sections with their chapter titles

    python data/fetch_hts.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from _http import get, get_json

API = "https://hts.usitc.gov/reststop/"
SITE = "https://hts.usitc.gov/"
DATA = Path(__file__).resolve().parent
RAW = DATA / "raw"

_STR = r'"((?:[^"\\]|\\.)*)"'
SECTION_RE = re.compile(
    r'\{"title":"Section ([IVXL]+):","section_num":\d+,"section_type":"chapter","label":'
    + _STR
    + r',"chapter_range":'
    + _STR
    + r',"chapters":\[(.*?)\]\}'
)
CHAPTER_RE = re.compile(r'\{"title":"Chapter (\d+)","label":' + _STR + r"\}")


_JS_ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)", re.DOTALL)
_SIMPLE = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def _js_string(body: str) -> str:
    """Decode the body of a JavaScript string literal (\\xNN, \\uNNNN, \\', \\", \\\\ ...)."""

    def unescape(match: re.Match) -> str:
        token = match.group(1)
        if token[0] in "xu" and len(token) > 1:
            return chr(int(token[1:], 16))
        return _SIMPLE.get(token, token)

    return _JS_ESCAPE.sub(unescape, body)


def fetch_sections() -> list[dict]:
    """Section and chapter titles are not in the REST API; the HTS web app ships them in its bundle."""
    index = get(SITE).decode("utf-8", "replace")
    bundles = re.findall(r'src="(main\.[0-9a-f]+\.js)"', index)
    if not bundles:
        raise RuntimeError("HTS web app bundle not found on the home page")
    js = get(SITE + bundles[0]).decode("utf-8", "replace")

    sections = []
    for roman, label, chapter_range, body in SECTION_RE.findall(js):
        chapters = [{"chapter": int(num), "title": _js_string(title)} for num, title in CHAPTER_RE.findall(body)]
        sections.append(
            {"section": roman, "title": _js_string(label), "chapter_range": _js_string(chapter_range), "chapters": chapters}
        )

    numbers = sorted(c["chapter"] for s in sections for c in s["chapters"])
    if len(sections) != 22 or numbers[0] != 1 or numbers[-1] < 97:
        raise RuntimeError(f"unexpected section parse: {len(sections)} sections, chapters {numbers[:3]}..{numbers[-3:]}")
    return sections


def fetch_release() -> dict:
    releases = get_json(API + "releaseList")
    current = next((r for r in releases if r.get("status") == "current"), releases[0])
    return {key: current.get(key) for key in ("name", "description", "title", "date", "releaseStartDate")}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)

    release = fetch_release()
    print(f"current release: {release['name']} ({release['description']}), start {release['releaseStartDate']}")

    rows = get_json(API + "exportList?from=0101&to=9999&format=JSON&styles=false", timeout=300)
    (RAW / "hts_full.json").write_text(json.dumps(rows), encoding="utf-8")
    ten_digit = sum(1 for r in rows if len((r.get("htsno") or "").replace(".", "")) == 10)
    chapters = sorted({(r.get("htsno") or "")[:2] for r in rows if r.get("htsno")})
    print(f"rows: {len(rows)}  10-digit lines: {ten_digit}  chapters: {chapters[0]}..{chapters[-1]} ({len(chapters)})")

    sections = fetch_sections()
    (DATA / "hts_sections.json").write_text(json.dumps(sections, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"sections: {len(sections)}  chapters listed: {sum(len(s['chapters']) for s in sections)}")

    (DATA / "hts_release.json").write_text(json.dumps(release, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
