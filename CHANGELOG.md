# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Links to recorded runs: `#run=<ruling>` (for example `#run=N361497`) opens the demo on that run and plays it, and
  replaying any run puts its link in the address bar. `docs/images/route-map.gif` is a real replay for the README and
  the article.
- **Classify hosted** button (`tariff_trail/hosted.py`, `tariff_trail/env.py`): the same search against the
  AWS User Group Madurai hosted Strands Decider (`POST /v1/decide`, Bearer key from `aws_strands_decider_key` or
  `DECIDER_API_KEY` in `.env`). The key stays on the server; calls are paced to 9 a minute across all requests
  with retry on 429/503, and the page shows when it is waiting. Hosted runs are labelled `hobson-v19`, not the
  `v1-2610` model the evaluation used. "Classify live" is now "Classify local".
- Public cloud API (`infra/build_lambda.py`, `infra/deploy_api.ps1`, `tariff_trail/web/guard.py`): the FastAPI app on
  AWS Lambda behind a streaming Function URL (Lambda Web Adapter, zip package, Bedrock via an IAM role). The Amplify site
  now calls it, so it offers Classify hosted, Simulate and New product as well as the recorded replays, and no
  Classify local (`TT_DISABLE_LOCAL=1`, `local: false` in `/api/health`). `TT_PUBLIC=1` limits each visitor to 6 hosted
  runs an hour and 2 at once per instance. `infra/deploy_site.ps1 -ApiUrl` bakes the API URL into the static site,
  which falls back to replays if the API is down.
- Heading-agreed review tier (`tariff_trail/agreement.py`, `heading_agreed` on results, a hollow yellow
  stamp in the UI, wording in the gate's `Confirm`): Decider, Bedrock and the nearest past rulings share
  the 4-digit heading but not the full code. 17.8% of test products, 72.9% right at the heading, 50.8%
  exact, against 23.3% exact for the products that split even on the heading. Defined after the test
  run and checked on dev, so it is documented as exploratory. The frozen classifier and the test
  numbers are unchanged. `eval/report.py` now prints all three tiers.
- Route map zoom controls (zoom out, zoom in, reset to 100%, fit to screen) on the map itself, plus Ctrl/Cmd+wheel or
  trackpad pinch to zoom around the cursor and `+` / `-` / `0` / `F` keys. Fit now measures the real route extent.
- `tariff_trail/strands_kit.py`: the pattern for any Strands agent, a `decision_tool` and a domain-free
  `DecisionGate` (`InterventionHandler`: Deny unknown items, Guide undecided ones, Confirm below the auto bar).
- `examples/tool_catalog/agent.py`: the 48-tool router as a gated Strands agent, with recorded runs above and below the bar.
- Post-hoc ablation (`eval/ablation.py`, `eval/ABLATION.md`): which shortlist source finds the answer, re-run noise, and
  a wider exploratory shortlist.
- Cost per 1,000 products at list price, and charts for the README and article (`eval/charts.py`, `docs/images/`).
- `notebooks/try_tarifftrail.ipynb`: Strands Decider 2B live on a free Colab GPU with no AWS account (tool routing,
  re-running any evaluation ruling from its precomputed retrieval seed in `data/eval/seeds.jsonl`, your own product;
  the full system when AWS credentials are present).
- Release `precedents-v1` with the prebuilt Titan index of 7,024 pre-2026 rulings, and `data/fetch_precedents.py`
  (SHA-256 checked), so the full system runs without rebuilding the index.
- Architecture diagrams as editable draw.io files (`docs/architecture/`): system overview, Calibrated Tree Descent on a
  real trace, `ClassificationGate` flow, and the AWS deployment.
- Open-source community files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CITATION.cff`, issue and pull
  request templates, and a GitHub Actions workflow (tests and diagram sync check).

### Changed
- README rewritten with quickstart, architecture, results, pattern usage, limitations and FAQ.

## [0.1.0] - 2026-10-18

First public version, built for the AWS Builder Center "Agent Experience Hackathon: Strands Decider".

### Added
- **Calibrated Tree Descent** (`tariff_trail/tree_descent.py`): best-first search over any decision tree using Strands
  Decider 2B's per-fork probabilities, with `none_of_these` at every fork and seed, shortlist and missing-fact hooks.
- **TariffTrail**: classification of products into 10-digit US HTS codes (2026 Revision 21) with a retrieval seed over
  7,024 pre-2026 CBP rulings, one Amazon Bedrock adjudication call, and a fast-track review tier.
- **ClassificationGate**: a Strands `InterventionHandler` that denies invented codes, guides unclassified ones, runs a
  Decider grounding check, and requires broker confirmation before `file_entry`.
- Evaluation on 332 held-out 2026 CBP rulings against four baselines, with confidence intervals and McNemar tests.
- GPU latency replication on an NVIDIA L4 (72 ms per Decider call, 2.6 s per product at p50).
- Second domain example: routing requests to 1 of 48 tools (23/24 correct).
- Demo UI (live and recorded runs), a replay-only static export hosted on AWS Amplify, AWS infrastructure scripts,
  the Builder Center article source, and the demo video source.
