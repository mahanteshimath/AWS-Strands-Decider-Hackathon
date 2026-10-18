// TariffTrail demo UI. All data is inserted with textContent (never innerHTML), so product
// descriptions and tariff wording cannot inject markup.
"use strict";

const $ = (id) => document.getElementById(id);
const SAMPLES = [
  ["Sweater", "Women's knitted V-neck pullover. 44% polyamide, 21% alpaca, 21% wool, 14% metallic yarn by weight. Raglan sleeves, rib-knit cuffs and hem."],
  ["Cable", "Aviation headset cable with four individually insulated copper conductors, a 5-pin connector on one end, rated for 12 volts, used to connect a headset to a cockpit audio panel."],
  ["Stone slab", "Polished granite slabs from Brazil, 2 m by 3 m, 2 cm and 3 cm thick, cut and polished on one face, for kitchen countertops."],
  ["Toy", "Plush stuffed toy shaped like a dinosaur, 30 cm tall, polyester outer shell and polyester fibre stuffing, for children over 3."],
];

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function pct(p) {
  return p === null || p === undefined ? "" : `${(100 * p).toFixed(p < 0.1 ? 1 : 0)}%`;
}

function renderFork(fork, chosenId) {
  const li = el("li", "fork");
  const title = el("div", "fork-title");
  title.append(el("span", null, `${fork.node.code ? fork.node.code + " " : ""}${fork.node.text}`.slice(0, 90)));
  const meta = [];
  if (fork.p_path !== null && fork.p_path !== undefined) meta.push(`path p ${fork.p_path.toFixed(2)}`);
  if (fork.latency_ms) meta.push(`${fork.latency_ms} ms`);
  if (meta.length) title.append(el("span", "meta", meta.join(" · ")));
  li.append(title);

  const top = chosenId || (fork.options[0] && fork.options[0].id);
  for (const opt of fork.options) {
    const row = el("div", "opt" + (opt.id === top ? " chosen" : "") + (opt.id === "none_of_these" ? " none" : ""));
    const label = el("span", "label");
    if (opt.code) label.append(el("span", "code", opt.code));
    label.append(document.createTextNode(opt.text));
    label.title = opt.text;
    row.append(label, el("span", "pct", pct(opt.p)));
    const wrap = el("div", "barwrap");
    const bar = el("div", "bar");
    wrap.append(bar);
    row.append(wrap);
    li.append(row);
    requestAnimationFrame(() => { bar.style.width = `${Math.max(1, 100 * opt.p)}%`; });
  }
  const noneP = (fork.options.find((o) => o.id === "none_of_these") || {}).p || 0;
  if (noneP > 0.5) li.classList.add("abandoned");
  $("trail").append(li);
  li.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function renderResult(r, gold) {
  const box = $("result");
  box.replaceChildren();
  box.hidden = false;
  if (r.event === "error") {
    box.append(el("p", "error", r.message));
    return;
  }
  const verdict = el("div", "verdict");
  verdict.append(el("span", "code-big", r.code || "no code"));
  const stamp = r.auto ? ["auto", "AUTO-CLEARED"] : r.fast_track ? ["fast", "FAST-TRACK REVIEW"] : ["review", "BROKER REVIEW"];
  verdict.append(el("span", "stamp " + stamp[0], stamp[1]));
  box.append(verdict);

  const facts = el("div", "facts-row");
  const add = (k, v) => { const s = el("span"); s.append(document.createTextNode(k + " "), el("b", null, v)); facts.append(s); };
  add("path probability", (r.p || 0).toFixed(2));
  add("general duty", r.duty || "-");
  add("Decider calls", String(r.decider_calls ?? "-"));
  add("LLM calls", String(r.llm_calls ?? 0));
  if (r.wall_ms) add("time", `${(r.wall_ms / 1000).toFixed(1)} s`);
  box.append(facts);

  const path = el("ol", "path");
  for (const step of r.path || []) {
    const li = el("li");
    if (step.code) li.append(el("span", "code", step.code));
    li.append(document.createTextNode(step.text));
    path.append(li);
  }
  box.append(path);

  const fmt = (c) => (c || "").replace(/(\d{4})(\d{2})(\d{2})(\d{2})/, "$1.$2.$3.$4");
  const reasons = (r.adjudications || []).map((a) => a.reason).filter(Boolean);
  if (reasons.length) box.append(el("p", "why", `Bedrock, choosing among the shortlist: ${reasons[0]}`));
  if (r.decider_code || r.precedent_code) {
    box.append(el("p", "why", `Sources: Decider's best path ${fmt(r.decider_code) || "-"} · nearest past rulings ${fmt(r.precedent_code) || "-"} · final ${r.code}`));
  }
  box.append(el("p", "why", r.fast_track
    ? "All three sources agree: fast-track review. The filing tool still asks a licensed broker to confirm (Strands Confirm)."
    : "The sources disagree: full broker review before filing (Strands Confirm)."));
  if (gold) {
    const digits = (r.code || "").replace(/\D/g, "");
    const ok = digits === gold;
    box.append(el("p", "gold " + (ok ? "ok" : "miss"), `CBP's ruling: ${gold.replace(/(\d{4})(\d{2})(\d{2})(\d{2})/, "$1.$2.$3.$4")} ${ok ? "(match)" : "(different)"}`));
  }
}

function reset() {
  $("trail").replaceChildren();
  $("result").hidden = true;
  $("recorded").hidden = true;
}

async function classifyLive() {
  const facts = $("facts").value.trim();
  if (facts.length < 10) { $("facts").focus(); return; }
  reset();
  $("go").disabled = true;
  try {
    const response = await fetch("/api/classify", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ facts }),
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, cut).replace(/^data: /, "");
        buffer = buffer.slice(cut + 2);
        if (!chunk) continue;
        const event = JSON.parse(chunk);
        if (event.event === "fork") renderFork(event);
        else renderResult(event);
      }
    }
  } catch (err) {
    renderResult({ event: "error", message: String(err) });
  } finally {
    $("go").disabled = false;
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function replay() {
  const id = $("replays").value;
  if (!id) return;
  reset();
  $("play").disabled = true;
  try {
    const data = await (await fetch(`/api/replay/${encodeURIComponent(id)}`)).json();
    $("facts").value = data.facts;
    const note = $("recorded");
    note.textContent = `Recorded run, ruling ${data.id} (${data.title}). Replayed from the evaluation results; timings are the original run's.`;
    note.hidden = false;
    for (const fork of data.forks) {
      renderFork(fork, fork.chosen);
      await sleep(650);
    }
    renderResult(data.result, data.gold);
  } catch (err) {
    renderResult({ event: "error", message: String(err) });
  } finally {
    $("play").disabled = false;
  }
}

async function init() {
  for (const [name, text] of SAMPLES) {
    const b = el("button", null, name);
    b.type = "button";
    b.addEventListener("click", () => { $("facts").value = text; });
    $("samples").append(b);
  }
  $("go").addEventListener("click", classifyLive);
  $("play").addEventListener("click", replay);

  try {
    const health = await (await fetch("/api/health")).json();
    const status = $("status");
    status.textContent = health.live ? `Decider live · ${health.decider.device}` : "Decider offline · replay only";
    status.className = "status " + (health.live ? "live" : "off");
    $("go").disabled = !health.live;
    $("release").textContent = health.hts_release ? `Tariff data: ${health.hts_release} (USITC)` : "";
  } catch (err) {
    $("status").textContent = "server unreachable";
  }
  try {
    const list = await (await fetch("/api/replays")).json();
    for (const item of list) {
      const option = el("option", null, `${item.id} · ${item.title}${item.correct ? "" : " (missed)"}`);
      option.value = item.id;
      $("replays").append(option);
    }
    if (!list.length) $("replays").append(el("option", null, "no recorded runs yet"));
  } catch (err) { /* replay list is optional */ }
}

init();
