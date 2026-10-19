// TariffTrail demo UI. Every Decider fork becomes an interchange on a route map; every option is a
// branch drawn as long as it is likely. All data is inserted with textContent / setAttribute (never
// innerHTML), so product descriptions and tariff wording cannot inject markup.
"use strict";

const $ = (id) => document.getElementById(id);
const SVG = "http://www.w3.org/2000/svg";
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const SAMPLES = [
  ["Sweater", "Women's knitted V-neck pullover. 44% polyamide, 21% alpaca, 21% wool, 14% metallic yarn by weight. Raglan sleeves, rib-knit cuffs and hem."],
  ["Cable", "Aviation headset cable with four individually insulated copper conductors, a 5-pin connector on one end, rated for 12 volts, used to connect a headset to a cockpit audio panel."],
  ["Stone slab", "Polished granite slabs from Brazil, 2 m by 3 m, 2 cm and 3 cm thick, cut and polished on one face, for kitchen countertops."],
  ["Toy", "Plush stuffed toy shaped like a dinosaur, 30 cm tall, polyester outer shell and polyester fibre stuffing, for children over 3."],
];

// map geometry (px at zoom 1)
const ROW = 56, COL = 470, ORIGIN_COL = 480, PAD = 44, GAP = 28, RING = 13, PLAQUE_W = 240;

const state = {
  forks: [], origin: null, facts: "", pathIds: null, follow: true, fit: false,
  token: 0, running: false, t0: 0, timer: null, sweepDone: false, replay: false,
  live: false, sample: null,
};

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}
function svg(tag, attrs, parent) {
  const node = document.createElementNS(SVG, tag);
  for (const k in attrs) node.setAttribute(k, attrs[k]);
  if (parent) parent.append(node);
  return node;
}
const r1 = (n) => Math.round(n * 10) / 10;
const pct = (p) => (p === null || p === undefined ? "" : `${(100 * p).toFixed(p < 0.1 ? 1 : 0)}%`);
const digitsOf = (c) => (c || "").replace(/\D/g, "");
function fmt(c) {
  const d = digitsOf(c);
  if (d.length === 10) return `${d.slice(0, 4)}.${d.slice(4, 6)}.${d.slice(6, 8)}.${d.slice(8)}`;
  if (d.length === 8) return `${d.slice(0, 4)}.${d.slice(4, 6)}.${d.slice(6)}`;
  return c || "";
}
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/* ---------------- tree model ---------------- */

function newOrigin() {
  return { origin: true, idx: 0, id: "origin", node: { id: "origin", code: "", text: "" }, options: [{ id: "_", p: 1 }], kids: [], parent: null, x: PAD, y: 0, drawn: false };
}

function resetState() {
  state.token += 1;
  clearInterval(state.timer);
  state.forks = [];
  state.origin = newOrigin();
  state.pathIds = null;
  state.sweepDone = false;
  state.follow = true;
  state.running = false;
  setBusy(null);  // a run cut short by a new one must not leave the controls disabled
  $("sr-trail").replaceChildren();
  $("canvas").classList.remove("done");
  $("recorded").hidden = true;
  resetBoard();
  render();
}

function addFork(ev) {
  const fork = {
    idx: state.forks.length + 1, id: `f${state.forks.length + 1}`, node: ev.node, options: ev.options,
    chosen: ev.chosen || null, latency: ev.latency_ms, kids: [], parent: null, x: 0, y: 0, drawn: false,
  };
  let parent = null;
  for (let i = state.forks.length - 1; i >= 0; i--) {
    const cand = state.forks[i];
    if (cand.options.some((o) => o.id === fork.node.id) && !cand.kids.some((k) => k.node.id === fork.node.id)) { parent = cand; break; }
  }
  fork.parent = parent || state.origin;
  fork.parent.kids.push(fork);
  state.forks.push(fork);

  const li = el("li", null, `Fork ${fork.idx}. ${fork.node.code} ${fork.node.text}. ` +
    fork.options.map((o) => `${o.code} ${o.text} ${pct(o.p)}`).join("; ") + ".");
  $("sr-trail").append(li);
  render();
}

/* ---------------- layout ---------------- */

const optIndex = (f, kid) => Math.max(0, f.options.findIndex((o) => o.id === kid.node.id));

function shift(f, d) { f.y += d; f.kids.forEach((k) => shift(k, d)); }

function place(f, top) {
  const own = Math.max(f.options.length * ROW, 56);
  const kids = f.kids.slice().sort((a, b) => optIndex(f, a) - optIndex(f, b));
  let cursor = top;
  for (const k of kids) cursor += place(k, cursor);
  if (!kids.length) { f.y = top + own / 2; return own + GAP; }
  let y = f.kids[0].y;
  if (y - own / 2 < top) { const d = top - (y - own / 2); kids.forEach((k) => shift(k, d)); y += d; cursor += d; }
  f.y = y;
  return Math.max(cursor - top, y + own / 2 + GAP - top);
}

function setX(f, x) {
  f.x = x;
  f.kids.forEach((k) => setX(k, x + (f.origin ? ORIGIN_COL : COL)));
}

function layout(viewW, viewH, zoom) {
  const o = state.origin;
  setX(o, PAD);
  const h = place(o, PAD);
  const maxX = Math.max(o.x, ...state.forks.map((f) => f.x));
  const W = Math.max(viewW / zoom, maxX + 470);
  const H = Math.max(viewH / zoom, h + PAD);
  shift(o, Math.max(0, (H - h - PAD) / 2));
  return { W, H };
}

/* ---------------- render ---------------- */

function connector(startX, rowY, kid) {
  const xr = kid.x - RING - 2;
  const delta = kid.y - rowY;
  let d = `H${r1(xr - Math.abs(delta) - 8)}`;
  if (Math.abs(delta) < 1) d = `H${r1(xr)}`;
  else d += ` L${r1(xr - 8)} ${r1(kid.y)} H${r1(xr)}`;
  return { d, bendX: xr - Math.abs(delta) - 8 };
}

function render() {
  const map = $("map");
  const canvas = $("canvas");
  const wires = $("wires");
  const marks = $("marks");
  const zoom = state.fit ? fitZoom() : 1;
  canvas.style.zoom = zoom;
  const stableH = window.matchMedia("(max-width: 920px)").matches ? map.clientHeight : Math.min(map.clientHeight, Math.max(300, window.innerHeight - 52 - 350));
  const { W, H } = layout(map.clientWidth, stableH, zoom);
  canvas.style.width = `${W}px`;
  canvas.style.height = `${H}px`;
  for (const node of [wires, marks]) { node.style.width = `${W}px`; node.style.height = `${H}px`; }
  wires.setAttribute("viewBox", `0 0 ${W} ${H}`);
  wires.replaceChildren();
  marks.replaceChildren();

  const o = state.origin;
  const started = state.running || state.forks.length > 0 || !!state.facts;
  $("empty").classList.toggle("gone", started);
  $("fit").disabled = state.forks.length === 0;
  if (!started) return;

  const ids = state.pathIds ? new Set(state.pathIds) : null;
  const sweep = !!ids && !state.sweepDone && !REDUCED;
  const litLayer = svg("g", {}, wires);
  const baseLayer = svg("g", {});
  wires.insertBefore(baseLayer, litLayer);
  const ringLayer = svg("g", {}, wires);

  // origin plaque
  const plaque = el("div", "plaque");
  plaque.style.left = `${PAD}px`;
  plaque.style.top = `${r1(o.y)}px`;
  plaque.append(el("span", null, state.facts || "Describing the product"));
  plaque.title = state.facts;
  marks.append(plaque);

  const routeForks = state.forks.filter((f) => ids && f.options.some((x) => ids.has(x.id)));
  routeForks.sort((a, b) => a.x - b.x || a.y - b.y);
  const order = new Map(routeForks.map((f, i) => [f.id, i]));

  const drawBranch = (startX, startY, rowY, fanD, label, opts) => {
    // opts: {kid, p, none, pick, fresh, delay, lit, litDelay, showPct}
    const x3 = startX;
    let d = fanD;
    let endX;
    let labelMax = 300;
    if (opts.kid) {
      const c = connector(x3, rowY, opts.kid);
      d += ` ${c.d}`;
      labelMax = Math.max(130, Math.min(300, c.bendX - x3 - 8));
      endX = opts.kid.x;
    } else {
      endX = x3 + 22 + 150 * opts.p;
      d += ` H${r1(endX)}`;
    }
    const cls = "w" + (opts.none ? " none" : opts.kid ? "" : " spur") + (opts.fresh ? " draw" : "");
    const path = svg("path", opts.none ? { d, class: cls } : { d, class: cls, pathLength: 1 }, baseLayer);
    if (opts.fresh) path.style.setProperty("--d", `${opts.delay}ms`);
    if (opts.lit) {
      const lp = svg("path", { d, class: "w lit" + (sweep ? " sweep" : ""), pathLength: 1 }, litLayer);
      if (sweep) lp.style.setProperty("--d", `${opts.litDelay}ms`);
    }
    if (!opts.kid) {
      const cap = opts.none
        ? svg("path", { d: `M${r1(endX + 6)} ${r1(rowY - 6)}l12 12M${r1(endX + 18)} ${r1(rowY - 6)}l-12 12`, class: "cap none" + (opts.fresh ? " draw" : "") }, baseLayer)
        : svg("path", { d: `M${r1(endX + 5)} ${r1(rowY - 7)}v14`, class: "cap" + (opts.fresh ? " draw" : "") }, baseLayer);
      if (opts.fresh) cap.style.setProperty("--d", `${opts.delay + 260}ms`);
    }
    const lbl = el("div", "lbl" + (opts.none ? " none" : opts.pick ? " pick" : "") + (opts.lit ? " onroute" : "") + (opts.fresh ? " draw" : ""));
    lbl.style.left = `${r1(x3 + 2)}px`;
    lbl.style.top = `${r1(rowY - 8)}px`;
    lbl.style.maxWidth = `${labelMax}px`;
    if (opts.fresh) lbl.style.setProperty("--d", `${opts.delay + 120}ms`);
    if (opts.showPct) lbl.append(el("b", "pct", pct(opts.p)));
    if (label.code) lbl.append(el("span", "code", label.code));
    lbl.append(el("span", "txt", label.text));
    lbl.title = `${label.code ? label.code + " " : ""}${label.text}`;
    marks.append(lbl);
  };

  // origin -> first-level forks
  const startX = PAD + PLAQUE_W + 2;
  o.kids.forEach((kid, i) => {
    const lit = ids && kid.options.some((x) => ids.has(x.id));
    drawBranch(startX, o.y, o.y, `M${startX} ${r1(o.y)}`,
      kid.node.id === "seeded" ? { ...kid.node, text: "Past rulings propose headings" } : kid.node, { kid, p: 1, pick: true, fresh: !kid.drawn, delay: 0, lit, litDelay: (order.get(kid.id) || 0) * 240 - 120, showPct: false });
  });

  for (const f of state.forks) {
    const n = f.options.length;
    const litFork = !!ids && f.options.some((x) => ids.has(x.id));
    const stemX1 = f.x + RING;
    const stemX2 = f.x + RING + 18;
    const stemD = `M${r1(stemX1)} ${r1(f.y)} H${r1(stemX2)}`;
    const stem = svg("path", { d: stemD, class: "w" + (!f.drawn ? " draw" : ""), pathLength: 1 }, baseLayer);
    if (!f.drawn) stem.style.setProperty("--d", "100ms");
    if (litFork) {
      const ls = svg("path", { d: stemD, class: "w lit" + (sweep ? " sweep" : ""), pathLength: 1 }, litLayer);
      if (sweep) ls.style.setProperty("--d", `${(order.get(f.id) || 0) * 240}ms`);
    }
    f.options.forEach((opt, i) => {
      const rowY = f.y + (i - (n - 1) / 2) * ROW;
      const dy = rowY - f.y;
      const ad = Math.abs(dy);
      const x3 = stemX2 + ad;
      const fan = `M${r1(stemX2)} ${r1(f.y)}` + (ad ? ` L${r1(x3)} ${r1(rowY)}` : "");
      const kid = f.kids.find((k) => k.node.id === opt.id) || null;
      const isNone = opt.id === "none_of_these";
      drawBranch(x3, f.y, rowY, fan, opt, {
        kid, p: opt.p, none: isNone, pick: !!kid || opt.id === f.chosen,
        fresh: !f.drawn, delay: 140 + i * 55, lit: !!ids && ids.has(opt.id),
        litDelay: (order.get(f.id) || 0) * 240, showPct: true,
      });
    });

    const lit = litFork;
    const g = svg("g", { class: "stn" + (lit ? " lit" : "") + (!f.drawn ? " draw" : "") }, ringLayer);
    svg("circle", { cx: r1(f.x), cy: r1(f.y), r: RING, class: "ring" }, g);
    const t = svg("text", { x: r1(f.x), y: r1(f.y + 0.5), class: "ring-n" }, g);
    t.textContent = String(f.idx);
    if (f.latency) {
      const lt = svg("text", { x: r1(f.x), y: r1(f.y + 32), class: "lat" }, g);
      lt.textContent = `${(f.latency / 1000).toFixed(1)} s`;
    }
  }

  if (state.running && state.forks.length === 0) {
    const g = svg("g", { class: "stn pending" }, ringLayer);
    const px = o.x + ORIGIN_COL;
    svg("path", { d: `M${startX} ${r1(o.y)} H${px - RING}`, class: "w spur", "stroke-dasharray": "2 9" }, baseLayer);
    svg("circle", { cx: px, cy: r1(o.y), r: RING, class: "ring" }, g);
  }

  state.forks.forEach((f) => { f.drawn = true; });
  o.drawn = true;
  if (ids) { state.sweepDone = true; canvas.classList.add("done"); }

  if (state.follow && !state.fit && !sweep) followLatest();
  if (sweep && state.follow && !state.fit) panAlong(routeForks);
}

function panAlong(forks) {
  const map = $("map");
  forks.forEach((f, i) => {
    setTimeout(() => {
      if (!state.follow) return;
      map.scrollTo({ left: Math.max(0, f.x - map.clientWidth * 0.4), top: Math.max(0, f.y - map.clientHeight / 2), behavior: "smooth" });
    }, i * 240);
  });
}

function fitZoom() {
  const map = $("map");
  const forks = state.forks;
  if (!forks.length) return 1;
  const maxX = Math.max(...forks.map((f) => f.x)) + 470;
  const rows = Math.max(...forks.map((f) => f.options.length));
  const approxH = Math.max(rows * ROW, forks.length * 30) + PAD * 2 + 140;
  return Math.max(0.3, Math.min(1, (map.clientWidth - 12) / maxX, (map.clientHeight - 12) / Math.max(approxH, 300)));
}

function followLatest() {
  const map = $("map");
  const target = state.pathIds && state.forks.length
    ? state.forks.filter((f) => f.options.some((o) => state.pathIds.includes(o.id))).sort((a, b) => b.x - a.x)[0] || state.forks[state.forks.length - 1]
    : state.forks[state.forks.length - 1];
  if (!target) return;
  const left = Math.max(0, target.x - map.clientWidth * 0.42);
  const top = Math.max(0, target.y - map.clientHeight / 2);
  map.scrollTo({ left, top, behavior: REDUCED ? "auto" : "smooth" });
}

/* ---------------- destination board ---------------- */

function setCode(code, animate) {
  const box = $("code");
  box.replaceChildren();
  box.className = "digits set";
  const cells = [];
  for (const ch of code) {
    if (/\d/.test(ch)) { const c = el("span", "dg", ch); c.setAttribute("aria-hidden", "true"); box.append(c); cells.push(c); }
    else box.append(el("span", "sep", ch));
  }
  box.setAttribute("aria-label", `Tariff code ${code}`);
  if (!animate || REDUCED) return;
  box.classList.add("landed");
  cells.forEach((c, i) => {
    const final = c.textContent;
    c.classList.add("roll");
    const start = performance.now() + i * 80;
    let n = 0;
    const timer = setInterval(() => {
      if (performance.now() < start) { c.textContent = String((i * 7 + n) % 10); return; }
      n += 1;
      if (n > 6) { c.textContent = final; c.classList.remove("roll"); clearInterval(timer); }
      else c.textContent = String((Number(final) + n * 3) % 10);
    }, 55);
  });
}

function resetBoard() {
  const box = $("code");
  box.className = "digits idle";
  box.replaceChildren();
  "----.--.--.--".split("").forEach((ch) => box.append(el("span", ch === "." ? "sep" : "dg", ch)));
  box.setAttribute("aria-label", "No tariff code yet");
  $("gold").hidden = true;
  const sign = $("sign");
  sign.className = "sign idle";
  sign.textContent = "Awaiting a run";
  $("tier-note").textContent = "TariffTrail never auto-files a tariff code. Every result goes to a licensed broker.";
  $("tier-note").classList.remove("err");
  for (const id of ["sources", "metrics", "detail"]) $(id).hidden = true;
}

function renderResult(r, gold) {
  clearInterval(state.timer);
  state.running = false;
  setBusy(null);
  const sign = $("sign");

  if (r.event === "error") {
    $("ticker").textContent = "Run failed";
    sign.className = "sign err pop";
    sign.textContent = "Could not classify";
    const note = $("tier-note");
    note.textContent = r.message;
    note.classList.add("err");
    render();
    return;
  }

  state.pathIds = (r.path || []).map((s) => s.id);
  render();
  const lead = REDUCED ? 0 : Math.min(2200, 520 + state.forks.filter((f) => f.options.some((o) => state.pathIds.includes(o.id))).length * 240);

  const secs = r.wall_ms ? `${(r.wall_ms / 1000).toFixed(1)} s` : "";
  $("ticker").textContent = r.simulated
    ? `${r.decider_calls ?? state.forks.length} simulated forks · ${r.backtracks || 0} wrong turns explored`
    : `${r.decider_calls ?? state.forks.length} Decider calls${secs ? " · " + secs : ""}`;

  setTimeout(() => {
    if (r.code) setCode(r.code, true);
    else { $("code").className = "digits none"; $("code").textContent = "No code reached"; }

    const tier = r.simulated ? ["sim", "Simulated", "A keyword stand-in answered each fork, not Strands Decider. It shows how the search moves and backtracks; it is not a tariff answer."]
      : r.fast_track ? ["fast", "Fast-track review", "Decider, Bedrock and past rulings agree. A licensed broker still confirms before filing."]
      : ["review", "Broker review", "The sources disagree. Full broker review before filing."];
    sign.className = `sign ${tier[0]} pop`;
    sign.textContent = tier[1];
    $("tier-note").textContent = tier[2];

    const g = $("gold");
    if (gold) {
      const got = digitsOf(r.code);
      const ok = got === gold;
      const near = ok ? "match" : got.slice(0, 4) === gold.slice(0, 4) ? "same heading" : got.slice(0, 2) === gold.slice(0, 2) ? "same chapter" : "different";
      g.replaceChildren(document.createTextNode("CBP's ruling "), el("b", null, fmt(gold)), document.createTextNode(" · "), el("span", ok ? "ok" : "miss", near));
      g.hidden = false;
    } else g.hidden = true;

    const src = $("sources");
    src.replaceChildren();
    const finalDigits = digitsOf(r.code);
    const rows = r.simulated ? [["Simulated path", r.code]]
      : [["Decider path", r.decider_code], ["Past rulings", r.precedent_code], [r.llm_calls ? "Final pick" : "Final", r.code]];
    for (const [who, val] of rows) {
      const li = el("li", "src " + (val && digitsOf(val) === finalDigits ? "ok" : "diff"));
      li.append(el("span", "mark"), el("span", null, who), el("span", "val", fmt(val) || "none"));
      src.append(li);
    }
    src.hidden = false;

    const metrics = $("metrics");
    metrics.replaceChildren();
    const add = (k, v) => { const d = el("div"); d.append(el("dd", null, v), el("dt", null, k)); metrics.append(d); };
    if (r.simulated) {
      add("Simulated forks", String(r.decider_calls ?? state.forks.length));
      add("Wrong turns explored", String(r.backtracks || 0));
    } else {
      add("Decider calls", String(r.decider_calls ?? state.forks.length));
      add("LLM calls", String(r.llm_calls ?? 0));
    }
    if (r.wall_ms) add("Time", `${(r.wall_ms / 1000).toFixed(1)} s`);
    add("General duty", r.duty || "-");
    metrics.hidden = false;

    const chain = $("chain");
    chain.replaceChildren();
    for (const step of r.path || []) {
      if (!step.code && !step.text) continue;
      const li = el("li");
      if (step.code) li.append(el("span", "code", step.code));
      li.append(el("span", "t", step.text));
      li.title = `${step.code} ${step.text}`.trim();
      chain.append(li);
    }
    const reasons = (r.adjudications || []).map((a) => a.reason).filter(Boolean);
    $("why").textContent = reasons.length ? `Why this code: ${reasons[0]}` : "";
    $("detail").hidden = false;
  }, lead);
}

/* ---------------- runs ---------------- */

function startTicker(label) {
  state.t0 = performance.now();
  clearInterval(state.timer);
  const tick = () => {
    const s = ((performance.now() - state.t0) / 1000).toFixed(1);
    $("ticker").textContent = `${label} · fork ${state.forks.length} · ${s} s`;
  };
  tick();
  state.timer = setInterval(tick, 100);
}

async function classifyLive() { return runStream("live"); }
async function simulate() { return runStream("sim"); }

// Disable every run control while a run is going; `btn` gets the busy look. setBusy(null) restores.
function setBusy(btn) {
  for (const id of ["go", "sim", "fresh"]) {
    const b = $(id);
    b.classList.toggle("busy", b === btn);
    b.disabled = btn ? true : id === "go" && !state.live;
  }
}

// CBP's ruled code, when the textarea still holds the loaded real product unchanged.
const goldFor = (facts) => (state.sample && state.sample.facts.trim() === facts ? state.sample.gold : null);

async function newProduct() {
  const fresh = $("fresh");
  fresh.disabled = true;
  try {
    const res = await fetch(`/api/sample?exclude=${encodeURIComponent(state.sample ? state.sample.id : "")}`);
    if (!res.ok) throw new Error(`The server answered ${res.status}.`);
    const s = await res.json();
    state.sample = s;
    $("facts").value = s.facts;
    const note = $("sample-note");
    note.replaceChildren(document.createTextNode("Real product from CBP ruling "), el("b", null, s.id),
      document.createTextNode(` (${s.title}). Its ruled code is shown after the run.`));
    note.hidden = false;
    return s;
  } catch (err) {
    const note = $("sample-note");
    note.textContent = `Could not load a product: ${err.message || err}`;
    note.hidden = false;
    return null;
  } finally {
    if (!state.running) fresh.disabled = false;
  }
}

async function runStream(kind) {
  const sim = kind === "sim";
  if (sim && $("facts").value.trim().length < 10 && !(await newProduct())) return;
  const facts = $("facts").value.trim();
  if (facts.length < 10) { $("facts").focus(); return; }
  const gold = goldFor(facts);
  resetState();
  state.facts = facts;
  state.running = true;
  revealStage();
  setBusy($(sim ? "sim" : "go"));
  const token = state.token;
  if (sim) {
    const note = $("recorded");
    note.textContent = "Simulated run. A local keyword scorer answers each fork in place of Strands Decider; the tariff tree, the best-first search and its none-of-these backtracking are the real ones.";
    note.title = note.textContent;
    note.hidden = false;
  }
  startTicker(sim ? "Simulating" : "Decider live");
  render();
  const RECOVER = sim ? "Try again, or replay a recorded run." : "Check that Decider is running, press Simulate, or replay a recorded run.";
  let finished = false;
  const handle = (chunk) => {
    const text = chunk.replace(/^data: /, "").trim();
    if (!text) return;
    const event = JSON.parse(text);
    if (event.event === "fork") addFork(event);
    else { finished = true; renderResult(event.event === "error" ? { ...event, message: `${event.message} ${RECOVER}` } : event, gold); }
  };
  try {
    const response = await fetch(sim ? "/api/simulate" : "/api/classify", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ facts }),
    });
    if (!response.ok || !response.body) throw new Error(`The server answered ${response.status}.`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (token !== state.token) return;
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        handle(chunk);
      }
    }
    if (buffer.trim()) handle(buffer);
    if (!finished && token === state.token) renderResult({ event: "error", message: `The run ended before a code came back. ${RECOVER}` });
  } catch (err) {
    if (token === state.token) renderResult({ event: "error", message: `${err.message || err} ${RECOVER}` });
  } finally {
    if (token === state.token) setBusy(null);
  }
}

async function replay() {
  const id = $("replays").value;
  if (!id) return;
  resetState();
  revealStage();
  const token = state.token;
  $("play").disabled = true;
  try {
    const res = await fetch(`/api/replay/${encodeURIComponent(id)}`);
    if (!res.ok) throw new Error(`The server answered ${res.status} for that recorded run.`);
    const data = await res.json();
    if (token !== state.token) return;
    $("facts").value = data.facts;
    state.facts = data.facts;
    state.running = true;
    state.replay = true;
    const note = $("recorded");
    note.textContent = `Recorded run, ruling ${data.id} (${data.title}). Replayed from the evaluation results; the map shows the ${data.forks.length} forks along the winning path, and timings are the original run's.`;
    note.hidden = false;
    note.title = note.textContent;
    startTicker("Replaying");
    render();
    await sleep(500);
    for (const fork of data.forks) {
      if (token !== state.token) return;
      addFork(fork);
      await sleep(REDUCED ? 80 : 780);
    }
    if (token !== state.token) return;
    renderResult(data.result, data.gold);
  } catch (err) {
    if (token === state.token) renderResult({ event: "error", message: `${err.message || err} Pick another recorded run, or reload the page.` });
  } finally {
    if (token === state.token) $("play").disabled = false;
  }
}

function revealStage() {
  if (window.matchMedia("(max-width: 920px)").matches) document.querySelector(".stage").scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "start" });
}

/* ---------------- boot ---------------- */

function wireMap() {
  const map = $("map");
  let drag = null;
  map.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "mouse" || e.button !== 0) return;
    drag = { x: e.clientX, y: e.clientY, l: map.scrollLeft, t: map.scrollTop };
    state.follow = false;
  });
  window.addEventListener("pointermove", (e) => {
    if (!drag) return;
    map.classList.add("dragging");
    map.scrollLeft = drag.l - (e.clientX - drag.x);
    map.scrollTop = drag.t - (e.clientY - drag.y);
  });
  window.addEventListener("pointerup", () => { drag = null; map.classList.remove("dragging"); });
  map.addEventListener("wheel", () => { state.follow = false; }, { passive: true });
  let resizeTimer;
  const rerender = () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 120); };
  new ResizeObserver(rerender).observe(map);
  $("fit").addEventListener("click", () => {
    state.fit = !state.fit;
    $("fit").setAttribute("aria-pressed", String(state.fit));
    $("fit").textContent = state.fit ? "Actual size" : "Fit route";
    state.follow = !state.fit;
    render();
    if (state.fit) map.scrollTo({ left: 0, top: 0 });
  });
}

async function init() {
  state.origin = newOrigin();
  resetBoard();
  for (const [name, text] of SAMPLES) {
    const b = el("button", null, name);
    b.type = "button";
    b.addEventListener("click", () => { $("facts").value = text; $("sample-note").hidden = true; $("facts").focus(); });
    $("samples").append(b);
  }
  $("facts").addEventListener("input", () => { if (state.sample && !goldFor($("facts").value.trim())) $("sample-note").hidden = true; });
  $("fresh").addEventListener("click", newProduct);
  $("go").addEventListener("click", classifyLive);
  $("sim").addEventListener("click", simulate);
  $("play").addEventListener("click", replay);
  wireMap();
  render();

  try {
    const health = await (await fetch("/api/health")).json();
    const status = $("status");
    // The hosted copy is static files: no simulator, no sample endpoint. Show only what this server can do.
    const canSim = !!health.simulate;
    $("status-text").textContent = health.live ? `Decider live, ${health.decider.device}` : canSim ? "Decider offline, simulate or replay" : "Decider offline, replay only";
    status.className = "status " + (health.live ? "live" : "off");
    state.live = !!health.live;
    $("sim").hidden = !canSim;
    $("fresh").hidden = !canSim;
    document.body.classList.toggle("nosim", !canSim);
    $("go-note").textContent = canSim
      ? "Decider is offline. Simulate runs the same search with a keyword stand-in for Decider, or replay a real recorded run below."
      : "Live mode needs a running Decider. Replay a real recorded run below.";
    $("go").disabled = !health.live;
    $("go-note").hidden = !!health.live;
    document.body.classList.toggle("offline", !health.live);
    $("go").title = health.live ? "" : canSim ? "Live mode needs a running Decider. Simulate, or replay a recorded run instead." : "Live mode needs a running Decider. Replay a recorded run instead.";
    $("release").textContent = health.hts_release ? `Tariff data: ${health.hts_release} (USITC)` : "";
  } catch (err) {
    $("status-text").textContent = "server unreachable";
    $("status").className = "status off";
  }
  try {
    const list = await (await fetch("/api/replays")).json();
    for (const item of list) {
      const option = el("option", null, `${item.id}: ${item.title}${item.correct ? "" : " (missed)"}`);
      option.value = item.id;
      $("replays").append(option);
    }
    if (!list.length) $("replays").append(el("option", null, "no recorded runs yet"));
    const featured = list.find((item) => item.id === "N357194");
    if (featured) $("replays").value = featured.id;
    if (featured && $("go").disabled) replay();
  } catch (err) { /* replay list is optional */ }
}

init();
