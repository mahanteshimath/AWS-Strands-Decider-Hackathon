# TariffTrail

**An agent that classifies products into US tariff codes by walking the official tariff tree
with Strands Decider 2B, then spends one short Amazon Bedrock call to choose among real codes.**

Hackathon tags: `#strands-decider-2b` `#policy`. Licence: Apache-2.0.
**Reusable decision pattern: [PATTERN.md](PATTERN.md)**, implemented in one file,
[`tariff_trail/tree_descent.py`](tariff_trail/tree_descent.py).

## Why this problem

Since US de minimis was suspended (29 August 2025), every import into the United States needs a
10-digit HTS code, including the $20 parcel. The schedule has **18,946 final codes** under
11,516 decisions, written in legal language full of "Other". It is the textbook case of an
agent with too many options:

- **Asked directly** (Nova Pro on Bedrock, 332 held-out 2026 rulings): 0.3% of full codes right, and
  **90.7% of the answers were codes that do not exist**.
- **As a Strands agent with HTS search tools:** 19.0% right and 19.0% invented codes, at about
  9,800 tokens per product. One uncapped run looped through 201 tool calls and 19.6 million tokens
  on a single product.

## What it does

```
product facts ──► Titan embeddings: 8 headings from the 20 most similar past CBP rulings
                  │
                  ▼
        Strands Decider 2B: one calibrated choice per fork, "none of these" at every level,
        best-first search on path probability (product of Decider's probabilities)
                  │
     every product ──► one Bedrock call picks among Decider's top 3 complete codes + the nearest
                       past ruling's code. It can only choose a real code
                  │
                  ▼
        Strands agent: file_entry is guarded by ClassificationGate (InterventionHandler)
        Deny invented codes · Guide unclassified ones · Confirm (licensed broker) every filing,
        fast-tracked when Decider, Bedrock and past rulings agree
```

- **It cannot invent a code.** Every answer is a leaf of the official 2026 HTS (Revision 21).
- **It knows its limits.** Decider's confidence was not reliable enough to file tariff codes
  unattended, so every filing goes to a broker, and agreement between three independent sources
  puts the easy 16% at the front of the queue (76% of those are right, vs 29% of the rest).
- **It is cheap.** At most one short Bedrock call per product (1,258 tokens), instead of an agent loop.

## Results

All numbers come from real 2026 CBP rulings and are reproducible with the scripts in `eval/`.
Method and frozen choices: [`research/PREREGISTRATION.md`](research/PREREGISTRATION.md).
Full tables, including review tiers, calibration and significance tests: [`eval/RESULTS.md`](eval/RESULTS.md).

Test split: **332 held-out 2026 CBP rulings**, run once with the frozen configuration.

| System | 4-digit | **10-digit** (95% CI) | Invented codes | Bedrock tokens / product |
|---|---|---|---|---|
| LLM, direct answer (Nova Pro) | 31.9% | 0.3% (0.1–1.7) | 90.7% | 241 |
| LLM agent + HTS search tools (Strands, Nova Pro, capped) | 39.5% | 19.0% (15.1–23.5) | 19.0% | 9,789 |
| Nearest past ruling (retrieval only) | 38.0% | 24.4% (20.1–29.3) | 0% | 0 |
| Strands Decider only (retrieval-seeded, no LLM) | 46.7% | 25.3% | 0% | 0 |
| **TariffTrail** | **57.5%** | **36.7% (31.7–42.1)** | **0%** | **1,258** |

TariffTrail vs the LLM agent on the same rulings: 92 products only TariffTrail got right and 33
only the agent got right (exact McNemar p = 1.3 × 10⁻⁷). It uses 7.8× fewer Bedrock tokens and
invents no codes. For scale, the ATLAS benchmark (arXiv 2509.18400) reports 25% at 10 digits
for GPT-5-Thinking on a different HTS test set.

**Second domain, same pattern code:** routing requests to 1 of 48 tools across 8 services was
23 of 24 correct. All 17 requests it was confident about were right, and the one miss was held
for the user ([`examples/tool_catalog/RESULTS.md`](examples/tool_catalog/RESULTS.md)).

## Run it

```bash
uv sync --extra dev                        # Python 3.11+
python data/fetch_hts.py                   # 2026 HTS from USITC (public domain)
python data/fetch_cross.py                 # CBP rulings from CROSS (public domain)
AWS_PROFILE=... python -m tariff_trail.precedents build      # Titan embeddings of pre-2026 rulings
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099
uvicorn tariff_trail.web.app:app --port 8000                 # demo UI: live or recorded runs
python -m tariff_trail.agent "Classify and file: women's knitted pullover, 44% polyamide ..."
pytest                                                       # offline tests, no GPU needed
```

A replay-only copy of the demo UI (392 real recorded runs, no live Decider) is hosted on AWS Amplify:
https://main.d3o5ktn9yc15oj.amplifyapp.com/ . `python scripts/export_static.py` rebuilds it into `site/`.

`infra/` holds the AWS setup actually used: an SSM-only EC2 host with no inbound ports, an IAM
instance role for Bedrock, a private S3 bucket, a $50 budget alert, and an SSM runner.

## Repository map

| Path | What |
|---|---|
| `tariff_trail/tree_descent.py` | **The reusable pattern:** best-first Calibrated Tree Descent, seed/shortlist/missing-fact hooks, `DictTree` |
| `tariff_trail/decider.py` | Dependency-free Strands Decider client |
| `tariff_trail/hts/` | The HTS as a tree (sections, chapters, headings, indented lines) and the tariff question wording |
| `tariff_trail/precedents.py` | Titan embeddings of pre-2026 rulings; `HeadingSeed` |
| `tariff_trail/adjudicator.py` | One Bedrock call over the top-3 shortlist |
| `tariff_trail/gate.py` | `ClassificationGate`, a Strands `InterventionHandler` |
| `tariff_trail/agent.py` | The Strands agent: classify, look up duty, list lines, file entry |
| `tariff_trail/web/` | Demo UI (FastAPI + Server-Sent Events) |
| `data/` | Fetchers, leak-checked evaluation set builder and audit |
| `eval/` | Runner, report, traces, retrieval probe, results |
| `examples/tool_catalog/` | The same pattern routing 48 tools |

## Limits

Decision support, not legal advice: a licensed customs broker is responsible for every entry.
The evaluation descriptions were rewritten by an LLM from CBP's own text, so they are cleaner
than many real importer descriptions. Chapters 98 and 99 are out of scope.
