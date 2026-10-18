## Results on the test split

| System | n | 2-digit | 4-digit | 6-digit | 8-digit | **10-digit** | invalid codes | LLM calls / product | LLM tokens / product | auto-cleared | auto-cleared correct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Nearest past rulings (retrieval only) | 332 | 55.1% | 38.0% | 31.0% | 29.2% | **24.4%** | 0.0% | 0.00 | 0 | - | - |
| LLM, direct answer | 332 | 56.9% | 31.9% | 13.9% | 1.5% | **0.3%** | 90.7% | 1.00 | 241 | - | - |
| LLM agent + HTS search tools (Strands) | 332 | 60.5% | 39.5% | 31.0% | 26.8% | **19.0%** | 19.0% | 3.86 | 9,789 | - | - |
| Strands Decider only (best path) | 332 | 63.3% | 46.7% | 32.5% | 29.2% | **25.3%** | 0.0% | 0 | 0 | - | - |
| **TariffTrail** (Decider search + one Bedrock shortlist call) | 332 | 70.5% | 57.5% | 46.7% | 43.7% | **36.7%** | 0.0% | 0.95 | 1,258 | 0% (by policy) | - |

### Review tiers (TariffTrail never auto-files a tariff code)

| tier | products | correct at 10 digits |
|---|---|---|
| fast-track (Decider, Bedrock and past rulings agree) | 54 (16.3%) | 41 (75.9%) |
| full review | 278 (83.7%) | 81 (29.1%) |

### Why not auto-clear: Decider's path probability vs correctness

| path probability | products | mean probability | actually correct (10-digit) |
|---|---|---|---|
| 0.0-0.2 | 290 | 0.08 | 22.8% |
| 0.2-0.4 | 35 | 0.27 | 37.1% |
| 0.4-0.6 | 6 | 0.49 | 66.7% |
| 0.6-0.8 | 1 | 0.62 | 100.0% |

### Search cost (Strands Decider)

- Decider calls per product: 18.4 (wrong-turn forks explored and abandoned: 14.6)
- Decider latency per call: 2971 ms; per product p50 60.7 s, p95 86.7 s
- Correct code among Decider's top 3 complete paths: 39.2%

### Uncertainty

TariffTrail 10-digit: 122/332 = 36.7% (95% CI 31.7%-42.1%)

| vs | their 10-digit (95% CI) | only TariffTrail right | only them right | exact McNemar p |
|---|---|---|---|---|
| Nearest past rulings | 24.4% (20.1%-29.3%) | 53 | 12 | 2.8e-07 |
| LLM agent + tools | 19.0% (15.1%-23.5%) | 92 | 33 | 1.3e-07 |
| LLM, direct | 0.3% (0.1%-1.7%) | 121 | 0 | 7.5e-37 |
