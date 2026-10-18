# Evaluation pre-registration

Written on 2026-10-18, before any system was run on the test split. The test split will be
run **once**, after the configuration below is frozen, and every number it produces will be
reported, including the ones that do not favour TariffTrail.

## Question

Can a small calibrated decision model (Strands Decider 2B), walking the official tariff tree,
classify real products to the full 10-digit US HTS code more accurately, more safely and more
cheaply than a frontier LLM on Amazon Bedrock working alone?

## Data

- **Tariff schedule:** the 2026 HTSUS, Revision 21, from the USITC REST API (`exportList`,
  chapters 1-97), plus the official section and chapter titles. Chapters 98 and 99 (special
  provisions and temporary legislation) are excluded because they are not product classification.
- **Cases:** binding classification rulings issued by CBP's New York office (CROSS) in 2026 that
  name exactly one tariff number which exists in Revision 21. 1,038 rulings qualified, and a
  seeded random sample of 400 (seed 20261018) was taken.
- **Inputs without answers:** each ruling's factual passage (between the request and "The
  applicable subheading") was rewritten by Amazon Nova 2 Lite as the importer's product
  description. An automatic check rejected any output mentioning codes, headings, chapters,
  classification, tariffs, duty, CBP or rulings, with one retry. 8 of 400 were rejected. An
  independent audit found 0 cases containing their own code digits and 0 legal terms.
  The 20 cases containing numbers carry part numbers, which importers really supply.
- **Split:** 60 tuning cases (dev) and 332 held-out test cases, fixed by the seeded split in
  `data/make_eval.py`.
- **Precedents:** only rulings dated before 2026-01-01 (7,024) are searchable by the system, so
  no test ruling, and no ruling issued after it, can be retrieved as a precedent.

## Systems

All LLM steps use the same Bedrock reasoner: the best model the account can invoke, which is
`us.amazon.nova-pro-v1:0` at the time of writing. The model actually used is recorded on every row.

1. **LLM, direct answer:** one Converse call asking for the 10-digit code.
2. **LLM agent with tools:** a Strands agent with keyword search over the HTS and "list the
   lines under a code", capped at 8 tool calls and 12 model calls. The cap was added after one
   uncapped tuning case looped through 201 tool calls; that case is reported, not hidden.
3. **Strands Decider only:** best-first search over the tree on Decider's path probability.
   No LLM.
4. **TariffTrail:** system 3, plus one Bedrock call per product, only when the best path's
   probability is below the auto-clear threshold. That call chooses among the top 3 complete
   codes, with similar pre-2026 rulings as context.

## Metrics

- **Primary:** exact 10-digit accuracy, measured against the code in the ruling.
- Accuracy by depth: 2, 4, 6 and 8 digits.
- **Invalid-code rate:** answers that are not a line in the current HTS.
- **Auto-clear rate**, and accuracy among auto-cleared products: the products the system would
  file with no LLM call and no human review.
- **Calibration:** Decider's path probability against observed accuracy, in bins.
- **Cost and latency:** LLM calls and tokens per product, Decider calls per product, and p50/p95
  wall time. Decider ran on CPU (c7i.4xlarge) because the account's GPU quota was 0 at the time;
  GPU latency is reported separately if measured.

## What is tuned on dev, and how

- **Auto-clear threshold:** the lowest threshold whose auto-cleared dev cases are at least 90%
  correct at 10 digits. If none qualifies, use 0.9.
- The search policy (budget 24 Decider calls, shortlist of 3) and the question wording are fixed
  before the test run.
- Nothing is changed after the test run starts. If a bug makes the test run invalid, it is fixed
  and the whole test run repeated, and both runs are reported.

## Known limitations, stated in advance

- The rewritten product descriptions are written by an LLM from CBP's own text, so they are more
  complete than many real importer descriptions.
- One ruling equals one product and one code. Rulings with several codes, and goods classified in
  chapters 98 and 99, are out of scope.
- Claude models on Bedrock were not available to this account during the build. If they become
  available before the test run, the LLM baselines and the adjudicator use the newest Claude
  Sonnet, and that is recorded.

## Amendment 1 (2026-10-18, after the dev run, before any test-split run)

What the dev split (60 rulings) showed, and what is frozen as a result. Nothing here was chosen
by looking at the test split, which has not been run by any system.

1. **Two systems added to the comparison.** *Nearest past ruling* (the similarity-weighted vote
   of the 20 nearest pre-2026 rulings; no LLM, no Decider) is the honest floor for retrieval.
   TariffTrail now seeds its search with headings from those same rulings ("retrieval proposes,
   Decider decides"), so retrieval must be shown on its own.
2. **Search changed before the dev run.** It moved from a greedy walk to a best-first search on
   path probability, with a seeded first fork (8 headings from the 20 nearest rulings, plus none
   of these). This happened after a 5-case smoke test, which is reported in the article.
3. **Shortlist frozen as Decider's top 3 complete codes plus the nearest-ruling code** (when it is
   not already on it). This was measured offline on dev by re-running only the Bedrock step on the
   recorded searches: 31.7% → 36.7% at 10 digits, at 989 → 1,296 tokens per product.
4. **Auto-clear: none on tariffs.** Decider's path probability did not predict correctness on dev
   (AUROC 0.45). A one-call Decider verification of the shortlist reached AUROC 0.67. The
   strongest signal, Decider, Bedrock and the nearest ruling all agreeing, covered 9 of 60
   products at 7 of 9 correct (78%). Nothing reached the pre-registered 90% bar. Per the rule
   above, the threshold would default to 0.9, under which no dev product auto-clears. **TariffTrail
   therefore sends every tariff classification to broker review.** The three-way agreement is
   reported on test as a *fast-track review* tier, not as auto-filing.
5. **Test run as frozen:** search budget 24, seed k=20 rulings / 8 headings, shortlist as in (3),
   reasoner `us.amazon.nova-pro-v1:0`, embeddings `amazon.titan-embed-text-v2:0`, Decider
   `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` on CPU. Baselines on test: LLM direct,
   LLM agent (capped), nearest past ruling.
