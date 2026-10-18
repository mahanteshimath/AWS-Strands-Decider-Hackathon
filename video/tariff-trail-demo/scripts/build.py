"""Build index.html for the TariffTrail demo video from SCRIPT.md and the narration WAVs.

    python scripts/build.py            # after scripts/voice.py has written assets/voice/L01..L17.wav

Timing comes from the real clip lengths: each line starts after the previous one plus a short gap,
each scene spans its lines, and every caption, chart value and the demo trail come from measured
data (eval/RESULTS.md, eval/results/test/tariff_trail.jsonl for ruling N357194).
"""

from __future__ import annotations

import html
import json
import re
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
GAP = 0.35  # seconds of silence between lines
LEAD = 0.6  # silence before the first line
TAIL = 1.6  # hold on the close card

# scene id -> the script lines it covers
SCENES = [
    ("s01-hook", ["L01"]),
    ("s02-invented", ["L02"]),
    ("s03-loop", ["L03"]),
    ("s04-reframe", ["L04"]),
    ("s05-decider", ["L05"]),
    ("s06-tree", ["L06", "L07"]),
    ("s07-pipeline", ["L08", "L09"]),
    ("s08-demo", ["L10", "L11"]),
    ("s09-gate", ["L12"]),
    ("s10-results", ["L13", "L14"]),
    ("s11-honest", ["L15"]),
    ("s12-reuse", ["L16", "L17"]),
]


def script_lines() -> dict[str, str]:
    out, cur = {}, None
    for raw in (HERE / "SCRIPT.md").read_text(encoding="utf-8").splitlines():
        h = re.match(r"^##\s+(L\d+)", raw)
        if h:
            cur = h.group(1)
            continue
        m = re.match(r"^say:\s*(.*)$", raw)
        if cur and m:
            out[cur] = m.group(1).strip()
    return out


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def demo_case() -> dict:
    row = next(json.loads(l) for l in (REPO / "eval/results/test/tariff_trail.jsonl").open(encoding="utf-8")
               if json.loads(l)["id"] == "N357194")
    case = next(json.loads(l) for l in (REPO / "data/eval/test.jsonl").open(encoding="utf-8")
                if json.loads(l)["id"] == "N357194")
    forks = []
    for step in row["steps"]:
        if step["route"] == "forced":
            continue
        title = "Headings proposed from 20 similar past rulings" if step["node"] == "seeded" else step["node_label"]
        options = [{"label": t["label"], "p": t["p"], "chosen": t["id"] == step["chosen"], "none": t["id"] == "none_of_these"}
                   for t in step["top"][:3]]
        forks.append({"title": title, "options": options})
    return {"facts": case["facts"], "forks": forks, "code": "9505.90.60.00", "gold": case["gold"]}


def invented_codes(n: int = 12) -> list[str]:
    """Real answers from the plain-LLM baseline on the test split that are not lines of the HTS."""
    out = []
    for line in (REPO / "eval/results/test/llm_direct.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        code = r.get("code") or ""
        if not r.get("valid") and len(code) == 10 and code not in out:
            out.append(code)
        if len(out) == n:
            break
    return [f"{c[:4]}.{c[4:6]}.{c[6:8]}{c[8:]}" for c in out]


def invented_codes(n: int = 12) -> list[str]:
    """Real answers from the plain-LLM baseline on the test split that are not lines of the HTS."""
    out = []
    for line in (REPO / "eval/results/test/llm_direct.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        code = r.get("code") or ""
        if not r.get("valid") and len(code) == 10 and code not in out:
            out.append(code)
        if len(out) == n:
            break
    return [f"{c[:4]}.{c[4:6]}.{c[6:8]}{c[8:]}" for c in out]


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def main() -> None:
    lines = script_lines()
    t = LEAD
    timing: dict[str, tuple[float, float]] = {}
    for lid in sorted(lines, key=lambda x: int(x[1:])):
        wav = HERE / "assets" / "voice" / f"{lid}.wav"
        dur = wav_seconds(wav)
        timing[lid] = (round(t, 3), round(dur, 3))
        t += dur + GAP
    total = round(t - GAP + TAIL, 2)

    scene_t = {}
    for i, (sid, ids) in enumerate(SCENES):
        start = timing[ids[0]][0] - (LEAD if i == 0 else 0.2)
        nxt = SCENES[i + 1][1][0] if i + 1 < len(SCENES) else None
        end = (timing[nxt][0] - 0.2) if nxt else total
        scene_t[sid] = (round(max(0, start), 3), round(end - max(0, start), 3))

    audio = "\n".join(
        f'      <audio id="vo-{lid.lower()}" src="assets/voice/{lid}.wav" data-start="{s}" data-duration="{d}" data-track-index="20" data-volume="1"></audio>'
        for lid, (s, d) in timing.items()
    )
    captions = "\n".join(
        f'      <div id="cap-{lid.lower()}" class="clip caption" data-start="{s}" data-duration="{d}" data-track-index="30"><span>{esc(lines[lid])}</span></div>'
        for lid, (s, d) in timing.items()
    )
    demo = demo_case()
    demo_json = json.dumps(demo)
    tickets = "\n".join(
        f'          <div class="ticket" id="tk{i}"><span class="tk-code">{esc(c)}</span><span class="tk-stamp" id="tks{i}" data-layout-allow-overlap>DOES NOT EXIST</span></div>'
        for i, c in enumerate(invented_codes())
    )
    # local times (seconds from scene start) of each line's start, for cueing animation to the voice
    cues = {sid: {lid: round(timing[lid][0] - scene_t[sid][0], 3) for lid in ids} for sid, ids in SCENES}
    template = (HERE / "scripts" / "index.template.html").read_text(encoding="utf-8")
    page = (template
            .replace("__TOTAL__", str(total))
            .replace("__AUDIO__", audio)
            .replace("__CAPTIONS__", captions)
            .replace("__DEMO__", demo_json)
            .replace("__TICKETS__", tickets)
            .replace("__TICKETS__", tickets)
            .replace("__CUES__", json.dumps(cues))
            .replace("__FACTS__", esc(demo["facts"])))
    for sid, (s, d) in scene_t.items():
        page = page.replace(f"__{sid}_START__", str(s)).replace(f"__{sid}_DUR__", str(d))
    (HERE / "index.html").write_text(page, encoding="utf-8")
    print(f"index.html: {total:.1f} s, {len(timing)} lines, {len(SCENES)} scenes")
    for sid, (s, d) in scene_t.items():
        print(f"  {sid:14} {s:6.1f} +{d:5.1f}")


if __name__ == "__main__":
    main()
