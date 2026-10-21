# Heading refine: a post-hoc probe of the final pick

**Status: exploratory.** Run on Oct 21 2026, after the preregistered test run
([`research/PREREGISTRATION.md`](../research/PREREGISTRATION.md)) and the [ablation](ABLATION.md).
It changes no headline number and nothing in the app. Code: [`heading_refine.py`](heading_refine.py);
recorded rows: [`results/heading_refine/`](results/heading_refine/).

## The question

69 of the 332 test products (20.8%) end on the **right 4-digit heading but the wrong 10-digit code**.
The frozen Bedrock step only ever sees Decider's top three paths plus the nearest ruling's code, so if
the right line inside the heading is not among them it cannot be picked. What if, after the final pick,
one more call reads the *whole* official outline of that heading (mean 40 filing lines, max 300) and
re-picks the line?

Every arm re-uses the recorded Decider search for each product. Only the step after the search changes.
A reply that is not a filing line of that heading keeps the original code, so no arm can invent a code.

## Dev first (60 tuning rulings)

| Arm | 10-digit | vs frozen (fixed / broke) |
|---|---|---|
| Frozen TariffTrail (re-measured) | 36.7% (22) | |
| Same pick, Kimi K2.5 instead of Nova Pro | 43.3% (26) | +4 / -0 |
| **Refine with Nova Pro** | 46.7% (28) | +8 / -2 |
| **Refine with Kimi K2.5** | 58.3% (35) | +16 / -3 |
| Wider shortlist picked by Nova Pro, then refine with Kimi K2.5 | 60.0% (36) | +17 / -3 |

Other models tried on dev: Mistral Large 3, DeepSeek V3.2, gpt-oss-120b (all in `results/heading_refine/`).
Dev is small and was used to choose, so these numbers overstate.

## Declared before the test run

> Primary (one config, chosen on dev as the smallest change): `refine:frozen:moonshotai.kimi-k2.5`,
> i.e. TariffTrail's recorded final pick, unchanged, then one extra Bedrock call that reads the
> complete outline of that pick's heading and re-picks the 10-digit line.
> Secondary (Amazon-model-only variant, reported regardless of outcome): `refine:frozen:us.amazon.nova-pro-v1:0`.
> Not run on test: every other dev arm, to avoid picking the luckiest configuration on test.

## Test (332 held-out 2026 rulings)

```
python eval/heading_refine.py --stats      # reproduces this table from the recorded rows, no AWS calls
```

| System | 10-digit (95% CI) | Fixed / broke vs recorded | McNemar p | 4-digit |
|---|---|---|---|---|
| TariffTrail, recorded | 36.7% (31.7–42.1) | | | 57.5% |
| **+ heading refine, Kimi K2.5** | **43.7% (38.4–49.1)** | +34 / -11 | **0.0008** | 57.5% |
| + heading refine, Nova Pro | 39.2% (34.1–44.5) | +24 / -16 | 0.27 (not significant) | 57.5% |

Review tiers recomputed on the refined code (Kimi): fast-track 49 products (14.8%) at 77.6% exact,
heading-agreed 64 (19.3%) at 50.0%, the rest 219 (66.0%) at 34.2%.

## What it means

- **The gain is real but post-hoc.** The test split was already seen in the preregistered run and the
  ablation, so this needs a fresh held-out set before it can be a headline (plan:
  [`docs/what_next.md`](../docs/what_next.md), phase 0.2).
- **It fixes only the last digits.** The 4-digit heading is unchanged by construction: refine cannot
  rescue a wrong heading, which is still where 67% of misses happen.
- **The model matters for this step.** Nova Pro gained 2.5 points (not significant); Kimi K2.5 gained 7.
- **Cost:** about 2,000 extra Bedrock tokens per product, one extra call. Kimi K2.5's Bedrock price was
  not checked, so no cost per 1,000 is claimed for this arm.
- It stays out of the app until it is confirmed on fresh rulings.
