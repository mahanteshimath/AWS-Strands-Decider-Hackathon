# TariffTrail results

**Data:** 332 held-out binding classification rulings issued by CBP's New York office in 2026,
each naming one 10-digit code that exists in the 2026 HTS, Revision 21. The product
descriptions were rewritten without the answer and leak-audited (`data/make_eval.py`,
`data/audit_eval.py`). **Method:** [`research/PREREGISTRATION.md`](../research/PREREGISTRATION.md),
including Amendment 1, which froze the configuration after the 60-ruling dev split and before
any test run. The test split was run once. Every system's numbers are reported.

**Models:** Strands Decider 2B (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, CPU,
c7i.4xlarge). Amazon Bedrock `us.amazon.nova-pro-v1:0` for every LLM step (Claude was not
enabled on the account). Amazon Titan Text Embeddings V2 (512-d) for retrieval over 7,024
rulings dated before 2026.

## Headline (test, n = 332)

| System | 2-digit | 4-digit | 6-digit | 8-digit | **10-digit** (95% CI) | Invented codes | Bedrock calls / product | Bedrock tokens / product |
|---|---|---|---|---|---|---|---|---|
| LLM, direct answer | 56.9% | 31.9% | 13.9% | 1.5% | **0.3%** (0.1–1.7) | 90.7% | 1.00 | 241 |
| LLM agent + HTS search tools (Strands, capped) | 60.5% | 39.5% | 31.0% | 26.8% | **19.0%** (15.1–23.5) | 19.0% | 3.86 | 9,789 |
| Nearest past rulings (retrieval only) | 55.1% | 38.0% | 31.0% | 29.2% | **24.4%** (20.1–29.3) | 0.0% | 0 | 0 |
| Strands Decider only (retrieval-seeded search, no LLM) | 63.3% | 46.7% | 32.5% | 29.2% | **25.3%** | 0.0% | 0 | 0 |
| **TariffTrail** (Decider search + one Bedrock call) | **70.5%** | **57.5%** | **46.7%** | **43.7%** | **36.7%** (31.7–42.1) | **0.0%** | 0.95 | **1,258** |

Paired comparisons on the same 332 rulings (exact McNemar test):

| TariffTrail vs | only TariffTrail right | only the other right | p |
|---|---|---|---|
| LLM agent + tools | 92 | 33 | 1.3 × 10⁻⁷ |
| Nearest past rulings | 53 | 12 | 2.8 × 10⁻⁷ |
| LLM, direct | 121 | 0 | 7.5 × 10⁻³⁷ |

What this means:

- **Accuracy:** TariffTrail nearly doubles the tool-using agent at 10 digits (+17.7 points) and
  leads at every depth. Its dev estimate was also 36.7%, so the frozen configuration did not overfit.
- **Safety:** TariffTrail never invents a code: every answer is a real line of the current schedule.
  The plain LLM invented 90.7% of its answers and the agent 19.0%.
- **Cost:** TariffTrail uses 7.8× fewer Bedrock tokens than the agent, at most one short call per
  product, and no runaway loops. One *uncapped* agent run on dev used 201 tool calls and 19.6 M
  tokens on a single product.
- **Decider alone:** with no LLM generation at all (only Titan retrieval to seed the search), it
  beats the LLM agent (25.3% vs 19.0%) and leads all baselines at the heading level (46.7% at 4 digits).

## Review tiers: why TariffTrail never auto-files a tariff code

The plan was to auto-file when Decider's path probability was high. On dev that probability
did not predict correctness (AUROC 0.45, n = 60). On test it is modestly predictive (AUROC 0.63,
n = 332), and accuracy rises with it (23% below 0.2, 37% at 0.2–0.4, 67% at 0.4–0.6). It is still
nowhere near a level at which filing without a broker would be responsible, so the frozen policy
sends everything to review and uses agreement to order the queue:

| tier | products | correct at 10 digits |
|---|---|---|
| **fast-track**: Decider, Bedrock and the nearest past rulings agree | 54 (16.3%) | 41 (75.9%) |
| full review | 278 (83.7%) | 81 (29.1%) |

Path probability vs observed accuracy (test):

| path probability | products | mean probability | correct (10-digit) |
|---|---|---|---|
| 0.0–0.2 | 290 | 0.08 | 22.8% |
| 0.2–0.4 | 35 | 0.27 | 37.1% |
| 0.4–0.6 | 6 | 0.49 | 66.7% |
| 0.6–0.8 | 1 | 0.62 | 100% |

Measured negative result: a single Decider *verification* call over the shortlist (one `choice` plus
three `noul` questions on a shared state) reached AUROC 0.67 on dev and added 6.3 s per product,
so it was dropped.

## Search cost

- Decider calls per product: 18.4, of which 14.6 explore a wrong turn and are abandoned by the
  best-first search. "None of these" is what makes those branches cheap to leave.
- Decider latency on CPU: 2.97 s per call; 60.7 s per product (p50), 86.7 s (p95), with two
  products in flight on one c7i.4xlarge. The GPU numbers are in the next section.

## GPU replication and latency (added after the quota was approved)

After the frozen test run, the account's GPU quota was approved. The **whole test split was run
again, unchanged, on a g6.xlarge (NVIDIA L4)** with one product in flight at a time
(`eval/results/latency/gpu_l4/`, summarised by `eval/latency_report.py`). Nothing was tuned between
the two runs; this is a replication, not a new test.

| | CPU (c7i.4xlarge, frozen run) | GPU (g6.xlarge, L4) |
|---|---|---|
| 10-digit accuracy | 36.7% | **37.4%** |
| 4-digit accuracy | 57.5% | 57.8% |
| Invented codes | 0% | 0% |
| Decider calls per product | 18.4 | 18.3 |
| **Decider call, p50 / p95** | 2,499 / 5,144 ms | **72 / 131 ms** |
| **Whole product (incl. one Bedrock call), p50 / p95** | 60.6 / 86.7 s | **2.6 / 3.3 s** |
| Bedrock tokens per product | 1,258 | 1,265 |

- Same final code on 300 of 332 products, same Decider top code on 317 of 332. The 0.6-point
  accuracy difference is within run-to-run variation (GPU kernels are not bit-identical to CPU, and
  the Bedrock call is not deterministic); it is not evidence that the GPU is more accurate.
- The CPU row above used two workers; the GPU row used one, so its latencies are not inflated by
  contention. The headline accuracy table in this file stays the frozen CPU run.
- At the g6.xlarge on-demand list price (about $0.80 per hour), 2.6 s per product is roughly
  $0.0006 of GPU time. Bedrock is the larger cost.

- The correct code is among Decider's top 3 complete paths 39.2% of the time. Adding the
  nearest-ruling code to the Bedrock shortlist raised dev accuracy from 31.7% to 36.7%.

## Second domain: tool routing (same pattern code)

48 tools in 8 services, 24 hand-written requests, no LLM: 23 of 24 correct. The 17 requests with
p ≥ 0.6 were all correct (called directly), and the one miss (p = 0.57) would have been confirmed
with the user first. Full log: [`examples/tool_catalog/RESULTS.md`](../examples/tool_catalog/RESULTS.md).
24 requests is a demonstration, not a benchmark.

## Dev split (n = 60) for reference

LLM direct 0.0%, LLM agent 21.7%, nearest past rulings 23.3%, TariffTrail as frozen 36.7%
(re-measured offline from the recorded searches). Full tables: [`RESULTS_dev.md`](RESULTS_dev.md).
Raw per-case rows: `eval/results/{dev,test}/*.jsonl`.

## Limits

- The descriptions were rewritten by an LLM from CBP's text: cleaner and more complete than many
  real importer descriptions.
- One ruling equals one code; multi-code rulings and chapters 98 and 99 are excluded.
- LLM numbers are for Amazon Nova Pro. Claude Sonnet might do better. It could not be tested on this account.
- Decision support only: a licensed customs broker is responsible for every entry.
