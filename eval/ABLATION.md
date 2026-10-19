## Ablation on the test split (post-hoc; n = 332)

Each arm shows Bedrock (same prompt, same model, temperature 0) a different shortlist; Bedrock must pick from it, so it cannot invent a code. *Shortlist recall* is the share of products whose correct 10-digit code is on the shortlist: the best any picker could do.

| System | Decider | Retrieval | Bedrock | shortlist recall | 4-digit | **10-digit** (95% CI) | Bedrock tokens / product | only TariffTrail right / only this right (exact McNemar) |
|---|---|---|---|---|---|---|---|---|
| Nearest past rulings (vote) | - | yes | - | - | 38.0% | **24.4%** (20.1%-29.3%) | 0 | 53 / 12 (p = 2.8e-07) |
| Strands Decider only (best path) | yes | seeds the walk | - | - | 46.7% | **25.3%** (20.9%-30.2%) | 0 | 44 / 6 (p = 3.2e-08) |
| Retrieval top 4 + Bedrock pick | - | yes | yes | 45.2% | 51.2% | **33.1%** (28.3%-38.4%) | 1,466 | 43 / 31 (p = 0.2) |
| Decider top 3 + Bedrock pick | yes | seeds the walk | yes | 39.2% | 52.7% | **31.9%** (27.1%-37.1%) | 955 | 24 / 8 (p = 0.007) |
| Decider top 3 + nearest ruling + Bedrock pick (re-run) | yes | yes | yes | 47.0% | 57.8% | **37.7%** (32.6%-43.0%) | 1,263 | 4 / 7 (p = 0.55) |
| Decider top 3 + retrieval top 4 + Bedrock pick (exploratory) | yes | yes | yes | 56.3% | 61.1% | **36.4%** (31.5%-41.8%) | 1,749 | 17 / 16 (p = 1) |
| **TariffTrail as recorded** (frozen test run) | yes | yes | yes | 47.0% | 57.5% | **36.7%** (31.7%-42.1%) | 1,258 | - |

### Who found the right code (TariffTrail as recorded)

| correct code was ... | products | TariffTrail got it right |
|---|---|---|
| in Decider's top 3 and was the nearest-ruling vote | 55 (16.6%) | 52 |
| in Decider's top 3 only (retrieval vote missed it) | 75 (22.6%) | 53 |
| the nearest-ruling vote only (Decider's top 3 missed it) | 26 (7.8%) | 17 |
| on neither | 176 (53.0%) | 0 |

### Recall of the candidate generators

| generator | top 1 | top 3 | top 4 | top 8 |
|---|---|---|---|---|
| Retrieval vote over 20 nearest rulings | 24.4% | 41.9% | 45.2% | 50.0% |
| Decider's best complete paths | 25.3% | 39.2% | - | - |

At the heading (4 digits), TariffTrail 191/332 vs retrieval top 4 + Bedrock 170/332: only TariffTrail right 45, only retrieval right 24, exact McNemar p = 0.015.

Re-running the frozen shortlist step gives the same final code for 308/332 products (92.8%): the run-to-run noise of the Bedrock pick at temperature 0.

73 of 332 products (22.0%) have a correct code that no ruling in the retrieval index (pre-2026) uses, so retrieval can never propose it. Decider's top 3 held it for 16 of them; TariffTrail classified 13 correctly.
