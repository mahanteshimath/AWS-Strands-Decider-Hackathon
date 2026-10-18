## Results on the dev split

| System | n | 2-digit | 4-digit | 6-digit | 8-digit | **10-digit** | invalid codes | LLM calls / product | LLM tokens / product | auto-cleared | auto-cleared correct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Nearest past rulings (retrieval only) | 60 | 55.0% | 35.0% | 31.7% | 26.7% | **23.3%** | 0.0% | 0.00 | 0 | - | - |
| LLM, direct answer | 60 | 58.3% | 35.0% | 20.0% | 1.7% | **0.0%** | 93.3% | 1.00 | 228 | - | - |
| LLM agent + HTS search tools (Strands) | 60 | 60.0% | 45.0% | 36.7% | 31.7% | **21.7%** | 23.3% | 3.65 | 8,270 | - | - |
| Strands Decider only (best path) | 60 | 63.3% | 55.0% | 30.0% | 25.0% | **23.3%** | 0.0% | 0 | 0 | - | - |
| **TariffTrail** (Decider search + one Bedrock shortlist call) | 60 | 71.7% | 65.0% | 38.3% | 35.0% | **30.0%** | 0.0% | 0.83 | 967 | 0% (by policy) | - |

### Review tiers (TariffTrail never auto-files a tariff code)

| tier | products | correct at 10 digits |
|---|---|---|
| fast-track (Decider, Bedrock and past rulings agree) | 0 (0.0%) | 0 (-) |
| full review | 60 (100.0%) | 18 (30.0%) |

### Why not auto-clear: Decider's path probability vs correctness

| path probability | products | mean probability | actually correct (10-digit) |
|---|---|---|---|
| 0.0-0.2 | 56 | 0.09 | 25.0% |
| 0.2-0.4 | 2 | 0.24 | 0.0% |
| 0.4-0.6 | 1 | 0.46 | 0.0% |
| 0.6-0.8 | 1 | 0.66 | 0.0% |

### Search cost (Strands Decider)

- Decider calls per product: 18.2 (wrong-turn forks explored and abandoned: 13.9)
- Decider latency per call: 4209 ms; per product p50 78.8 s, p95 135.0 s
- Correct code among Decider's top 3 complete paths: 40.0%

### Uncertainty

TariffTrail 10-digit: 18/60 = 30.0% (95% CI 19.9%-42.5%)

| vs | their 10-digit (95% CI) | only TariffTrail right | only them right | exact McNemar p |
|---|---|---|---|---|
| Nearest past rulings | 23.3% (14.4%-35.4%) | 9 | 5 | 0.42 |
| LLM agent + tools | 21.7% (13.1%-33.6%) | 14 | 9 | 0.4 |
| LLM, direct | 0.0% (-0.0%-6.0%) | 18 | 0 | 7.6e-06 |
