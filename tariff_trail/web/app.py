"""TariffTrail demo UI: watch Strands Decider walk the tariff tree, live or from recorded runs.

    uvicorn tariff_trail.web.app:app --port 8000      # needs a Decider at STRANDS_DECIDER_URL for live mode

Live mode streams each Decider fork over Server-Sent Events while TariffTrail classifies.
Replay mode plays back real recorded evaluation runs (eval/results/*/tariff_trail.jsonl) and says so.
Simulate mode runs the same search on any product with a local keyword stand-in for Decider
(tariff_trail/simulate.py), so new routes can be shown without a server; every result says simulated.
"""

from __future__ import annotations

import json
import queue
import random
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..classify import TariffTrail
from ..decider import Decider, DeciderUnavailable
from ..hts.tree import load
from ..simulate import Simulator
from ..tree_descent import NONE_KEY, SEED_KEY

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
RESULTS = ROOT / "eval" / "results"

app = FastAPI(title="TariffTrail")
tree = load()
simulator = Simulator(tree)
SIM_PACE_S = 0.45  # seconds between simulated forks, so the map can be watched


class ClassifyRequest(BaseModel):
    facts: str = Field(min_length=10, max_length=4000)


class SimulateRequest(ClassifyRequest):
    seed: int | None = None  # noise seed; omitted -> a fresh one, so repeat runs explore differently


def label(node_id: str) -> dict[str, str]:
    if node_id == NONE_KEY:
        return {"id": node_id, "code": "", "text": "None of these"}
    if node_id == SEED_KEY:
        return {"id": node_id, "code": "", "text": "Headings proposed from similar past rulings"}
    if node_id == tree.root_id:
        return {"id": node_id, "code": "", "text": "Harmonized Tariff Schedule (22 sections)"}
    node = tree[node_id]
    code = node.htsno or (node.id.split(":", 1)[1] if node.kind in ("section", "chapter") else "")
    prefix = {"section": "Section ", "chapter": "Chapter "}.get(node.kind, "")
    # Lines use the option wording ("Other" spelled out); sections and headings read best as printed.
    text = tree.option_text(node_id) if node.kind == "line" else node.text.rstrip(":")
    return {"id": node_id, "code": f"{prefix}{code}".strip(), "text": text[:220]}


def fork_event(event: dict[str, Any], *, simulated: bool = False) -> dict[str, Any]:
    ranked = sorted(event["probs"].items(), key=lambda kv: kv[1], reverse=True)[:6]
    return {
        "event": "fork",
        "simulated": simulated,
        "node": label(event["node"]),
        "p_path": round(event["p_path"], 4),
        "confidence": round(event["confidence"], 3),
        "latency_ms": None if simulated else round(event["latency_ms"]),  # simulated forks are paced, not timed
        "options": [{**label(c), "p": round(p, 4)} for c, p in ranked],
    }


def result_event(c) -> dict[str, Any]:
    leaf = tree.by_code.get(c.code)
    return {
        "event": "result",
        "code": c.htsno,
        "status": c.status,
        "route": c.route,
        "auto": c.auto,
        "fast_track": c.fast_track,
        "p": round(c.p, 4),
        "path": [label(n.id) for n in tree.path(leaf)] if leaf else [],
        "duty": c.duty,
        "candidates": c.candidates,
        "decider_code": c.decider_code,
        "precedent_code": c.precedent_code,
        "adjudications": c.adjudications,
        "decider_calls": c.decider_calls,
        "llm_calls": c.llm_calls,
        "llm_tokens": c.llm_input_tokens + c.llm_output_tokens,
        "wall_ms": round(c.wall_ms),
        "hts_release": tree.release.get("description"),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/static/{name:path}")
def static(name: str) -> FileResponse:
    path = (STATIC / name).resolve()
    if STATIC.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/api/health")
def health() -> dict[str, Any]:
    base = {"simulate": True, "samples": len(_cases()), "hts_release": tree.release.get("description")}
    try:
        return {**base, "live": True, "decider": Decider().health()}
    except DeciderUnavailable as exc:
        return {**base, "live": False, "error": str(exc)}


@app.post("/api/classify")
def classify(request: ClassifyRequest) -> StreamingResponse:
    events: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            trail = TariffTrail(tree=tree, decider=Decider())
            result = trail.classify(request.facts, observe=lambda e: events.put(fork_event(e)))
            events.put(result_event(result))
        except Exception as exc:  # surface the failure to the page instead of hanging the stream
            events.put({"event": "error", "message": str(exc)[:300]})
        events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


def sim_result_event(sim, seed: int) -> dict[str, Any]:
    result = sim.result
    leaf = result.leaf
    node = tree[leaf] if leaf else None
    return {
        "event": "result",
        "simulated": True,
        "seed": seed,
        "code": node.htsno if node and node.htsno else sim.code,
        "status": result.status,
        "route": "simulated",
        "auto": False,
        "fast_track": False,
        "p": round(result.p, 4),
        "path": [label(n.id) for n in tree.path(leaf)] if leaf else [],
        "duty": next((n.duty for n in reversed(tree.path(leaf)) if n.duty), "") if leaf else "",
        "decider_code": sim.code,
        "precedent_code": "",
        "adjudications": [],
        "decider_calls": sim.forks,
        "backtracks": result.off_path,
        "llm_calls": 0,
        "wall_ms": None,
        "hts_release": tree.release.get("description"),
    }


@app.post("/api/simulate")
def simulate(request: SimulateRequest) -> StreamingResponse:
    events: queue.Queue = queue.Queue()
    seed = request.seed if request.seed is not None else random.randrange(1, 1_000_000)

    def work() -> None:
        try:
            sim = simulator.run(request.facts, seed=seed, pace_s=SIM_PACE_S,
                                observe=lambda e: events.put(fork_event(e, simulated=True)))
            events.put(sim_result_event(sim, seed))
        except Exception as exc:
            events.put({"event": "error", "message": str(exc)[:300]})
        events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


_CASES: dict[str, dict[str, Any]] | None = None


def _cases() -> dict[str, dict[str, Any]]:
    """The labelled evaluation products (2026 CBP rulings, facts rewritten without the answer)."""
    global _CASES
    if _CASES is None:
        cases = {}
        for split in ("dev", "test"):
            path = ROOT / "data" / "eval" / f"{split}.jsonl"
            if path.exists():
                for line in path.open(encoding="utf-8"):
                    case = json.loads(line)
                    cases[case["id"]] = case
        _CASES = cases
    return _CASES


@app.get("/api/sample")
def sample(exclude: str = "") -> dict[str, Any]:
    """A random real product to try, with CBP's ruled code for comparison."""
    pool = [c for c in _cases().values() if c["id"] != exclude]
    if not pool:
        raise HTTPException(404, "no labelled products on this server")
    case = random.choice(pool)
    return {"id": case["id"], "title": case["title"], "facts": case["facts"], "gold": case["gold"]}


def _recorded() -> dict[str, dict[str, Any]]:
    cases = _cases()
    out = {}
    for path in sorted(RESULTS.glob("*/tariff_trail.jsonl")):
        for line in path.open(encoding="utf-8"):
            row = json.loads(line)
            if row["id"] in cases and row.get("steps"):
                out[row["id"]] = {"row": row, "case": cases[row["id"]], "split": path.parent.name}
    return out


@app.get("/api/replays")
def replays() -> list[dict[str, Any]]:
    return [
        {"id": rid, "title": item["case"]["title"], "split": item["split"],
         "correct": (item["row"].get("code") or item["row"].get("decider_code")) == item["row"]["gold"]}
        for rid, item in _recorded().items()
    ]


@app.get("/api/replay/{ruling_id}")
def replay(ruling_id: str) -> dict[str, Any]:
    item = _recorded().get(ruling_id)
    if not item:
        raise HTTPException(404, "no recorded run for that ruling")
    row, case = item["row"], item["case"]
    forks = []
    for step in row["steps"]:
        if step["route"] == "forced":
            continue
        options = [{**label(t["id"]), "p": t["p"]} for t in step["top"] if t["id"] in tree.nodes or t["id"] == NONE_KEY]
        node = step["node"] if step["node"] in tree.nodes or step["node"] == SEED_KEY else tree.root_id
        forks.append({"event": "fork", "node": label(node), "p_path": None, "confidence": step["confidence"],
                      "latency_ms": step.get("latency_ms"), "options": options, "chosen": step["chosen"]})
    final = row.get("code") or row["decider_code"]
    leaf = tree.by_code.get(final)
    precedent = row.get("precedent_code")
    fast = bool(row.get("fast_track")) or (final == row["decider_code"] == precedent)
    return {
        "recorded": True,
        "id": ruling_id,
        "title": case["title"],
        "facts": case["facts"],
        "gold": case["gold"],
        "forks": forks,
        "result": {
            "event": "result", "code": tree[leaf].htsno if leaf else final, "auto": False, "fast_track": fast,
            "route": row.get("route", "adjudicated"), "p": row.get("p_best", 0.0),
            "path": [label(n.id) for n in tree.path(leaf)] if leaf else [],
            "duty": next((n.duty for n in reversed(tree.path(leaf)) if n.duty), "") if leaf else "",
            "candidates": row.get("candidates", []), "adjudications": row.get("adjudications", []),
            "decider_code": row["decider_code"], "precedent_code": precedent,
            "decider_calls": row.get("decider_calls"), "llm_calls": row.get("llm_calls", 0),
            "wall_ms": round(row.get("wall_ms", 0)), "hts_release": tree.release.get("description"),
        },
    }
