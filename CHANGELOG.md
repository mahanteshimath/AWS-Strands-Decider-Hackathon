# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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
