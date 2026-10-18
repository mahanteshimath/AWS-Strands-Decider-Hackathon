"""voice.py - generate assets/voice/Lnn.wav for every SCRIPT.md line (FAST path).

  python scripts/voice.py --silent     silent, length-estimated clips (caption-timed preview)
  python scripts/voice.py              cloned voice. Engine order: Chatterbox TURBO (fast, ~real-time on CPU)
                                       -> Chatterbox v1 (slow, ~1 min/line) if Turbo weights are missing
  options: --force  --only L03,L04  --engine turbo|v1  --no-cache

Speed rules (this machine: CPU only, every ffmpeg/ffprobe spawn costs ~3 s):
  * NO subprocess per line - edge trimming + pause capping are done in numpy, WAVs written with `wave`.
  * Global line cache ~/.cache/cloudbytes/voice-cache : a line with the same text/engine/reference is never
    synthesised twice (CTA lines, re-runs after a script edit only redo the changed lines).
  * Model is loaded once per run; run voice.py right after gate 1, in the background, while scenes.mjs is written.

Model files (download from modelscope.cn/models/ResembleAI/<repo>/resolve/master/<file>, HF is blocked):
  Turbo -> ~/.cache/cloudbytes/chatterbox-turbo : ve.safetensors t3_turbo_v1.safetensors s3gen_meanflow.safetensors
           conds.pt vocab.json merges.txt tokenizer_config.json added_tokens.json special_tokens_map.json
  v1    -> ~/.cache/cloudbytes/chatterbox       : ve.safetensors t3_cfg.safetensors s3gen.safetensors tokenizer.json
Reference sample: <repo>/voice/MY  English Voice Sample.m4a (best 12 s window -> ~/.cache/cloudbytes/ref_clean.wav,
built once by scripts/voice_ref.py).
"""
import argparse, hashlib, re, shutil, subprocess, sys, wave
from pathlib import Path

try:
    import numpy as np
except ImportError:  # system python without numpy -> use the Chatterbox venv
    _v = Path.home() / ".cache" / "cloudbytes" / "venv" / "Scripts" / "python.exe"
    if _v.exists() and Path(sys.executable).resolve() != _v.resolve():
        sys.exit(subprocess.call([str(_v), __file__, *sys.argv[1:]]))
    raise

HOME = Path.home()
BASE = HOME / ".cache" / "cloudbytes"
CKPT_V1 = BASE / "chatterbox"
CKPT_TURBO = BASE / "chatterbox-turbo"
CACHE = BASE / "voice-cache"
VENV_PY = BASE / "venv" / "Scripts" / "python.exe"
NEED_V1 = ["ve.safetensors", "t3_cfg.safetensors", "s3gen.safetensors", "tokenizer.json"]
NEED_TURBO = ["ve.safetensors", "t3_turbo_v1.safetensors", "s3gen_meanflow.safetensors", "vocab.json", "merges.txt", "tokenizer_config.json"]
OUT = Path("assets/voice")
WPS = 2.75  # spoken words per second used for silent previews (~165 wpm)
SR = 24000


def parse_say(path="SCRIPT.md"):
    lines, cur = [], None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        h = re.match(r"^##\s+(L\d+)\s*[·\-:]", raw)
        if h:
            cur = {"id": h.group(1), "say": ""}
            lines.append(cur)
            continue
        if raw.startswith("## "):
            cur = None
            continue
        m = re.match(r"^say:\s*(.*)$", raw)
        if cur is not None and m:
            cur["say"] = m.group(1).strip()
    return lines


def write_wav(path, x, sr=SR):
    x = np.clip(np.asarray(x, dtype=np.float32), -1.0, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def tidy(x, sr=SR, edge_db=-45.0, gap_db=-38.0, pad=0.06, max_gap=0.3, keep_gap=0.2):
    """trim edge silence (60 ms pad) and cap mid-line pauses at ~0.2 s - same result as the old ffmpeg chain."""
    hop = int(sr * 0.01)
    n = len(x) // hop
    if n == 0:
        return x
    fr = x[: n * hop].reshape(n, hop)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-9)
    loud = np.where(db > edge_db)[0]
    if len(loud) == 0:
        return x
    a = max(0, loud[0] - int(pad / 0.01))
    b = min(n, loud[-1] + 1 + int(pad / 0.01))
    db, fr = db[a:b], fr[a:b]
    quiet = db < gap_db
    keep = np.ones(len(db), dtype=bool)
    i = 0
    while i < len(db):
        if quiet[i]:
            j = i
            while j < len(db) and quiet[j]:
                j += 1
            if (j - i) * 0.01 > max_gap:
                keep[i + int(keep_gap / 0.01): j] = False
            i = j
        else:
            i += 1
    return fr[keep].reshape(-1)


def silent(lines, force):
    OUT.mkdir(parents=True, exist_ok=True)
    for ln in lines:
        p = OUT / f"{ln['id']}.wav"
        if p.exists() and not force:
            continue
        words = len(ln["say"].split())
        dur = max(1.0, words / WPS + 0.25)
        write_wav(p, np.zeros(int(dur * SR), dtype=np.float32))
        print(f"{ln['id']}: silent {dur:.2f}s ({words} words)")
    (OUT / ".silent").write_text("silent preview clips - regenerate with voice.py once the clone is ready\n")


def reference():
    sample = Path(__file__).resolve()
    while sample.name != "Ready-For-AWS-Certified-Solutions-Architect-Professional" and sample.parent != sample:
        sample = sample.parent
    src = sample / "voice" / "MY  English Voice Sample.m4a"
    if not src.exists():
        src = sample / "voice" / "My Voice Sample.m4a"
    ref = BASE / "ref_clean.wav"
    if not ref.exists():
        tmp = ref.with_name("ref_clean_full.wav")
        base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        subprocess.run(base + ["-i", str(src), "-ac", "1", "-ar", "24000", "-af",
                               "highpass=f=70,afftdn=nf=-28,silenceremove=stop_periods=-1:stop_duration=0.2:stop_threshold=-38dB:stop_silence=0.12,loudnorm=I=-20:TP=-2",
                               str(tmp)], check=True)
        subprocess.run(base + ["-t", "12", "-i", str(tmp), str(ref)], check=True)
    return ref


def have(ckpt, need):
    return all((ckpt / f).exists() for f in need)


def pick_device(torch, want):
    """cuda if present, else cpu. DirectML (AMD/Intel iGPU) only when asked for with --device dml: untested with Chatterbox."""
    if want in ("auto", "cuda") and torch.cuda.is_available():
        return "cuda"
    if want == "dml":
        try:
            import torch_directml
            return torch_directml.device()
        except ImportError:
            print("torch-directml not installed; using CPU")
    return "cpu"


def clone(lines, force, only, engine, exaggeration, cfg, use_cache, device="auto"):
    import json
    if engine == "auto":
        engine = "turbo" if have(CKPT_TURBO, NEED_TURBO) else "v1"
    ckpt, need = (CKPT_TURBO, NEED_TURBO) if engine == "turbo" else (CKPT_V1, NEED_V1)
    ref = reference()
    ref_id = f"{ref.stat().st_size}-{int(ref.stat().st_mtime)}"
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    regen_all = force or (OUT / ".silent").exists()
    mf = OUT / ".manifest.json"
    manifest = json.loads(mf.read_text()) if mf.exists() else {}

    def key(say):
        return hashlib.sha1(f"{engine}|{say}|{exaggeration}|{cfg}|{ref_id}".encode()).hexdigest()[:20]

    todo = []
    for ln in lines:
        if only and ln["id"] not in only:
            continue
        p = OUT / f"{ln['id']}.wav"
        k = key(ln["say"])
        # an existing clip is kept unless forced, or the manifest says the line text/engine/voice changed since it was made
        if p.exists() and not regen_all and manifest.get(ln["id"], k) == k:
            continue
        c = CACHE / f"{k}.wav"
        if use_cache and c.exists():
            shutil.copyfile(c, p)
            manifest[ln["id"]] = k
            print(f"{ln['id']}: cache hit", flush=True)
            continue
        todo.append((ln, p, c, k))
    if todo:
        miss = [f for f in need if not (ckpt / f).exists()]
        if miss:
            print("Cloned voice unavailable. Missing in", ckpt, ":", ", ".join(miss))
            print("Use --silent for a caption-timed preview in the meantime.")
            sys.exit(2)
        try:  # heavy imports only when something must be synthesised (torch import alone is ~1-2 min under Defender)
            import torch
            if engine == "turbo":
                from chatterbox.tts_turbo import ChatterboxTurboTTS as TTS
            else:
                from chatterbox.tts import ChatterboxTTS as TTS
        except ImportError:
            if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
                sys.exit(subprocess.call([str(VENV_PY), __file__, *sys.argv[1:]]))
            raise
        dev = pick_device(torch, device)
        print(f"loading Chatterbox {engine} ({dev}) for {len(todo)} line(s)...", flush=True)
        model = TTS.from_local(ckpt, device=dev)
        # conditionals (speaker embedding, ref mel/tokens) cost ~12 s - compute ONCE, not per line
        model.prepare_conditionals(str(ref), exaggeration=exaggeration)
        for ln, p, c, k in todo:
            kw = {}
            if engine == "v1":
                kw.update(exaggeration=exaggeration, cfg_weight=cfg)
            wav = model.generate(ln["say"], **kw)
            x = wav.squeeze().detach().cpu().numpy()
            if getattr(model, "sr", SR) != SR:
                import torchaudio.functional as F
                x = F.resample(torch.from_numpy(x), model.sr, SR).numpy()
            write_wav(p, tidy(x))
            shutil.copyfile(p, c)
            manifest[ln["id"]] = k
            mf.write_text(json.dumps(manifest, indent=1))
            print(f"{ln['id']}: ok", flush=True)
    mf.write_text(json.dumps(manifest, indent=1))
    s = OUT / ".silent"
    if s.exists():
        s.unlink()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--silent", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--engine", default="auto", choices=["auto", "turbo", "v1"])
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "dml"])
    ap.add_argument("--exaggeration", type=float, default=0.6)
    ap.add_argument("--cfg", type=float, default=0.3)
    a = ap.parse_args()
    lines = parse_say()
    if not lines:
        sys.exit("no lines found in SCRIPT.md")
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    if a.silent:
        silent(lines, a.force)
    else:
        clone(lines, a.force, only, a.engine, a.exaggeration, a.cfg, not a.no_cache, a.device)
