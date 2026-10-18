"""One-off: self-host the Latin subset of Overpass and Overpass Mono (variable weight) for the demo UI."""
import re
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
OUT = Path(__file__).resolve().parents[1] / "tariff_trail" / "web" / "static" / "fonts"
OUT.mkdir(parents=True, exist_ok=True)
CSS = "https://fonts.googleapis.com/css2?family=Overpass:wght@300..900&family=Overpass+Mono:wght@400..700&display=swap"

css = urllib.request.urlopen(urllib.request.Request(CSS, headers={"User-Agent": UA}), timeout=30).read().decode()
for block in re.findall(r"@font-face\s*\{[^}]*\}", css):
    if "U+0000-00FF" not in block:
        continue
    family = re.search(r"font-family:\s*'([^']+)'", block).group(1)
    url = re.search(r"url\(([^)]+)\)", block).group(1)
    target = OUT / (family.lower().replace(" ", "-") + ".woff2")
    target.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read())
    print(family, target.name, target.stat().st_size)
