# What next: a plan to take TariffTrail to 90%

TariffTrail gets **36.7%** of 10-digit codes exactly right on the 332 held-out 2026 CBP rulings
([`eval/RESULTS.md`](../eval/RESULTS.md)). This document is the plan to reach **at least 90%**: where the
misses are, which change addresses each one, how to measure each step, and the order to do them in.

Every "now" number below was measured from the recorded test rows
(`eval/results/test/tariff_trail.jsonl`, `data/eval/seeds.jsonl`). Every "target" number is an estimate
to be confirmed on fresh data, not a result.

---

## 1. Decide which 90% we mean

"90% accurate" can mean three different things, and they are not equally reachable.

| Target | Definition | Now | Reachable? |
|---|---|---|---|
| **T1, heading** | Right 4-digit heading, no questions asked | 57.5% | Yes. It is a stepping stone, and the duty rate usually depends on more digits. |
| **T2, exact with questions** | Right 10-digit code after at most 2 clarifying questions to the importer | not measured | **Yes, with all of phases 1 to 4. This is the headline target.** |
| **T3, selective** | 90% of the codes in the fast-track queue are right, and that queue covers at least 50% of products | 75.9% at 16.3% coverage | Yes, once T2 work raises the base rate |

**Why "90% exact from one paragraph, no questions" is not the headline.** Many rulings turn on a fact
the description does not state: unit value, fibre percentage by weight, width, voltage. Products whose
code ends in a statistical suffix other than `00` are right only **25.6%** of the time (215 products),
against **57.3%** for suffix `00` (117 products). No model can recover a fact that isn't in the text.
That number will still be reported as "exact, 0 questions", next to T2.

**Rules that hold throughout.** These are what make the 36.7% trustworthy, so they stay:

- 0% invented codes.
- A licensed broker confirms every filing; T3 changes the order of the queue, not who signs.
- The cost stays well below the LLM agent's $8.93 per 1,000 products (budget: at most $5).
- Latency on one L4 GPU stays at or under 6 s per product at p50, excluding the time a human takes to answer questions.

## 2. Where the 210 misses are now

### The funnel

Exact accuracy is the product of two numbers: **P(heading right) × P(exact code | heading right) = 57.5% × 63.9% = 36.7%.**
Reaching 90% needs both of them at about 95%.

| Stage | Now | What it means |
|---|---|---|
| Right heading among the 8 retrieval seeds | **77.7%** (258/332) | When it isn't there, the product is lost: **2 of 74** are right (2.7%) |
| Right chapter among the 8 seeds | 87.7% | Retrieval usually gets the neighbourhood right |
| Seed recall at top 1 / 3 / 5 / 8 | 42.2 / 65.4 / 72.9 / 77.7% | Recall is still rising at 8, so 8 cuts it short |
| Decider ranks the right seed first, when it was seeded | 149/258 (58%) | 72 were 2nd or 3rd, 25 were 4th or lower, 12 never appeared in the top list |
| Final heading right | **57.5%** (191/332) | |
| Exact, given the heading is right | **63.9%** | 78.7% given the right 6 digits, 84.1% given the right 8 |
| Right code on the Bedrock shortlist | 47.0% (156/332) | |
| Bedrock picks it, given it is on the shortlist | 78.2% (122/156) | |

### The fallback that never fires

The design says that `none_of_these` at the seeded fork falls back to a full walk from the top of the
tree. On the test split it never did:

- Where the right heading was **not** seeded, Decider's mean p(`none_of_these`) at that fork was 0.149.
- Where it **was** seeded, the mean was 0.123, so the signal barely separates the two cases.
- It was chosen **0 times**.
- No search expanded the root or a section node.
- 10 rows had no seeded step at all.

This one fact explains most of the 74 lost products.

### Where the misses first leave the right path

| First wrong digit | Misses |
|---|---|
| Chapter (digits 1–2) | **98** |
| Heading (3–4) | 43 |
| Subheading (5–6) | 36 |
| 8-digit line (7–8) | 10 |
| Statistical suffix (9–10) | 23 |

141 of the 210 misses (67%) are already wrong by the 4-digit heading. **Fix the top of the tree first.**

### The hardest chapters

Six chapters hold **102 of the 210 misses (49%)**:

| Chapter | Misses / products |
|---|---|
| 84, machinery | 27 / 37 |
| 94, furniture and lighting | 22 / 29 |
| 87, vehicles and parts | 14 / 21 |
| 39, plastics | 14 / 24 |
| 85, electrical | 13 / 26 |
| 90, instruments | 12 / 13 |

These are the chapters where legal notes decide the answer: parts rules, principal function, composite goods.

### Two smaller observations

- **Legal notes are never shown.** Decider and Bedrock see the official line wording, with "Other" rewritten
  against its siblings (`HTSTree.option_text`). No section or chapter note reaches either model, although
  customs classification is decided by GRI 1, "the terms of the headings and any relative section or chapter notes".
- **Longer descriptions do worse.** The longest quarter of descriptions scores 30.1%, against 41.0% for the
  shortest quarter. That points to complex or composite goods, not to too little text.

## 3. Phase 0: measurement we can trust (do this first)

The current test split has been used for the ablations and for this analysis. From now on it counts as **development data**.

| # | Action | Done when |
|---|---|---|
| 0.1 | Commit the funnel above as `eval/error_funnel.py`, printed by `eval/report.py` for every system: seed recall @n, heading accuracy, exact given heading, shortlist recall, pick given shortlist, first-wrong-digit histogram, misses by chapter. | Running it on the recorded rows reproduces every number in section 2 |
| 0.2 | Build a fresh held-out set, **test-2026b**. `data/eval/meta.json` shows 1,038 eligible 2026 rulings, of which 400 were sampled, so about 638 are unused. Add rulings issued after 2026-09-25. Same leak audit (`data/audit_eval.py`). Aim for at least 600, so a 90% result has a 95% CI of about ±2.4 points. | The set is committed and has never been run |
| 0.3 | Build a **messy** set of about 100 terse importer-style descriptions ("LED desk lamp, plastic, USB"), written from the same rulings, to measure the cost of clean rewritten text. | Committed |
| 0.4 | Preregistration Amendment 2: name T1, T2 and T3, the guardrails and the one-run rule for test-2026b. | `research/PREREGISTRATION.md` updated before any test-2026b run |
| 0.5 | Report each change with a CI and a paired McNemar test against the previous configuration. The run-to-run noise floor is about 1 point (92.8% of codes are identical on a re-run), so any gain under about 2 points counts as noise. | |

## 4. Phase 1: put the right heading within reach (target 95%)

**The problem:** 22% of products start without the right heading, and the fallback never rescues them.

| # | Action | Where | How to measure |
|---|---|---|---|
| 1.1 | **Make the fallback real.** When retrieval is unsure, also put the chapters of the top seeds (and the root) into the best-first queue, at a prior weight, so the search can leave the seeds without needing Decider to pick `none_of_these`. Two triggers to compare: (a) the top seed's similarity-weighted vote share is below a cut-off; (b) the seeds span 3 or more chapters. | `tree_descent.py` (`seed` may return chapter ids), `precedents.HeadingSeed` | Right heading among the nodes the search reaches. Recall of the 74 lost products |
| 1.2 | **Seed with more headings.** Try n = 8 → 12 → 16, and k = 20 → 40 rulings. Recall is still climbing at 8 (72.9% at 5, 77.7% at 8). | `HeadingSeed(k, n)` | Seed recall @n, offline from Titan alone; then Decider calls per product |
| 1.3 | **Search the tariff text as well as the rulings.** Index the heading and subheading wording (plus explanatory text where licensing allows), and combine BM25 and Titan scores. Before searching, one cheap Bedrock call (Nova Micro) rewrites the facts into tariff vocabulary: material, function, form, user. | `precedents.py`, new `hts/index.py` | Seed recall @8 against 77.7% |
| 1.4 | **A real "is it here?" question.** Replace the passive `none_of_these` with an explicit `noul` question at the seeded fork: "Is the product's heading in this list?" Keep it only if its AUROC on dev beats 0.75. | `tree_descent.py` | AUROC; recall of the lost products |
| 1.5 | **A wider precedent index.** The index has 7,024 rulings from Oct 2021 to Dec 2025, and 22% of test products have a code no indexed ruling uses. Add earlier New York rulings and HQ rulings from CROSS, and map retired codes to Revision 21 (or drop them). | `data/fetch_cross.py`, `precedents build` | Share of products whose code appears in the index (now 78%) |

**Exit criterion:** the right heading is reachable for at least 95% of dev products, at no more than 30 Decider calls per product (18.4 now).

## 5. Phase 2: give Decider the law (heading accuracy 57.5% → 90%)

| # | Action | Where | How to measure |
|---|---|---|---|
| 2.1 | **Section and chapter notes in the state.** Load the HTS legal notes. At each section, chapter and heading fork, add only the note paragraphs that name or exclude an option on the menu, such as "This chapter does not cover…". Keep the state short so the server's prefix cache still helps. | `hts/tree.py` (a `notes` field), `hts/questions.hts_state` | Heading accuracy, and Decider's rank of the right seed (58% first now) |
| 2.2 | **Evidence for each option.** At the heading fork, show the nearest past ruling under each candidate heading in one line ("a similar product, N3xxxxx, went to 9405"). Retrieval still proposes and Decider still decides; it now decides with evidence. | `tree_descent` `on_options` hook (new), `precedents.search(prefix=…)` | Heading accuracy |
| 2.3 | **GRI questions where they apply.** For sets, composite goods and parts (chapters 39, 84, 85, 87, 94, 95), ask Decider an essential-character or principal-function `choice` question before the heading fork, and put its answer in the state. | `hts/questions.py` | Accuracy on those chapters (102 of the 210 misses) |
| 2.4 | **Playbooks for the hard chapters.** For each of the six chapters, keep a short, reviewed list of the notes and distinctions that settle most rulings, for example Section XVI Note 2 (parts) and Chapter 94 Note 1 (exclusions). Build them from the dev misses; never from test-2026b. | `hts/playbooks/*.md` | Per-chapter accuracy on dev, then on test-2026b once |

**Exit criterion:** at least 90% heading accuracy on dev with phases 1 and 2 together.

## 6. Phase 3: below the heading, ask for the fact (63.9% → 92% exact given the heading)

| # | Action | Where | How to measure |
|---|---|---|---|
| 3.1 | **Ask for the missing fact.** The `on_missing` hook and the `MISSING_FACTS` vocabulary already exist. Turn them on in the eval with an **importer simulator**: a Bedrock call that answers from the original CBP ruling text and is filtered so it cannot reveal a code or heading number. Allow at most 2 questions. | `eval/run_eval.py --questions 2`, new `eval/importer_sim.py` | Exact accuracy at 0, 1 and 2 questions: the T2 headline |
| 3.2 | **Check numbers and percentages with code, not a model.** Parse the conditions in line text ("valued over $", "containing 85 percent or more by weight", "of a width exceeding 30 cm", "not exceeding 1,000 V") into predicates. Pull the matching attributes from the facts once, as structured JSON. Before Decider sees a fork, drop any option the facts contradict; when the attribute is missing, raise exactly that question (feeds 3.1). Every pruning is shown in the trace. | new `hts/conditions.py`, `tree_descent` option filter | Accuracy on suffix-not-00 products (25.6% now) and at the 6→8 and 8→10 forks |
| 3.3 | **Show the UI question.** This is the first roadmap item: ask the importer the one missing fact in the demo, instead of guessing. | `web/static/app.js`, `web/app.py` | Demo; and the same simulator in the hosted copy |

**Exit criterion:** exact given the heading is at least 92% with 2 or fewer questions, and the median product needs at most 1.

## 7. Phase 4: make the final pick reliable (78.2% → 95% when the answer is on the shortlist)

**Already measured (post-hoc, [`eval/HEADING_REFINE.md`](../eval/HEADING_REFINE.md)):** one extra call that reads the
whole outline of the chosen heading and re-picks the 10-digit line took test from 36.7% to 43.7% with Kimi K2.5
(+34 / -11, p = 0.0008) and to 39.2% with Nova Pro (not significant). It is the first thing to confirm on test-2026b.

| # | Action | Where | How to measure |
|---|---|---|---|
| 4.1 | **Show the differences, not the whole path.** For the shortlist, show the shared path once, then only the lines where the candidates differ, plus the notes from 2.1. Ask for the deciding fact before the letter. | `adjudicator.PROMPT` | Pick given shortlist (78.2%) |
| 4.2 | **A combiner trained on the recorded rows.** Logistic regression over features already recorded: Decider path probability and rank, the retrieval vote's weight, Bedrock's choice, agreement flags and the chapter. It needs no new model calls, so it can be built today on the 392 recorded dev and test rows with cross-validation. It also gives the calibrated score for T3. | new `eval/combiner.py`, then `classify.py` | Pick accuracy; AUROC (path probability alone is 0.63) |
| 4.3 | **A stronger or repeated pick, within budget.** Try Claude Sonnet when it is enabled on the account (it has not been tested here), Nova Premier, and 3-vote self-consistency with Nova Pro. Keep a change only if it adds at least 2 points within the $5 per 1,000 budget. | `bedrock.py` roles | Accuracy and cost per 1,000, together |
| 4.4 | **Show the broker a top 5, not a top 3.** Retrieval's top 4 plus Decider's top 3 already reach 56.3% recall, and phase 1 should raise that. | `classify.py`, UI | Top-5 recall: at least 95% is the broker-facing target |

**Exit criterion:** pick given shortlist is at least 95%, and top-5 recall is at least 95% on dev.

## 8. Phase 5: learn from the rulings we already have

Each pre-2026 ruling is a fully labelled path: one correct choice at every fork from the section down to
the 10 digits. 7,024 rulings give tens of thousands of labelled fork decisions, all dated before every
test ruling, so they can be used for training without leaking the answer.

| # | Action | How to measure |
|---|---|---|
| 5.1 | **Examples at the fork.** Add to the state the choices the two nearest rulings made at the same fork ("a similar product went to 6110.30"). | Accuracy per fork level |
| 5.2 | **Recalibrate Decider's probabilities** per fork level and chapter, against these labels (temperature or isotonic scaling). This feeds the best-first order and T3. | Calibration error per level |
| 5.3 | **Fine-tune, if it is allowed.** Check first whether the Strands Decider licence and tooling permit fine-tuning or LoRA on the `v1-2610` checkpoint; this has not been verified. If they do, train on fork decisions with a strict time split, and report it as a separate system next to the stock one. | Paired comparison against stock Decider |
| 5.4 | **Broker corrections back in.** Every confirmed or corrected filing becomes a precedent, and its corrected path becomes a training example. | Accuracy over time on new rulings |

## 9. Phase 6: operational 90% (T3)

- Build the fast-track queue from the phase 4.2 combiner score instead of three-way agreement.
- Pick the cut-off on dev so that precision is at least 90%.
- Report its coverage on test-2026b.
- Target: **at least 90% precision at 50% or more coverage** (now 75.9% at 16.3%).
- Everything below the cut-off goes to full review with the top 5 and the evidence.
- The policy doesn't change: the broker still confirms every filing.

## 10. Milestones

These projections are estimates, built from the funnel as P(heading) × P(exact | heading). Each must be confirmed on dev, and then once on test-2026b.

| Milestone | Phases | Heading | Exact given heading | **Exact, 10-digit** |
|---|---|---|---|---|
| Now (measured) | | 57.5% | 63.9% | **36.7%** |
| M1 | 0, 1, 4.2 | ~72% | ~66% | **~48%** |
| M2 | + 2 | ~85% | ~70% | **~60%** |
| M3 | + 3 (≤ 2 questions) | ~88% | ~88% | **~77%** |
| M4 | + 4, 5 | ≥ 95% | ≥ 95% | **≥ 90% (T2)** |

The step from M3 to M4 is the uncertain one. If phase 5 can't fine-tune Decider, M4 depends on the
legal notes, the condition checker and the combiner together closing the last gap. If dev stalls below
85% after phase 4, report that honestly and make T3 the 90% claim.

## 11. Risks and how we guard against them

| Risk | Guard |
|---|---|
| Overfitting to the 392 rulings we keep looking at | test-2026b is run once, under Amendment 2. Playbooks are written from dev misses only |
| The importer simulator leaks the answer | Filter out codes, heading numbers and "classified under" phrases; audit 50 transcripts by hand; report 0-question accuracy as well |
| Clean, rewritten descriptions flatter the result | Report the messy set (0.3) next to every headline |
| A wrong gold code: some rulings arguably have more than one valid code | Keep the one-ruling-one-code rule; list disputed cases rather than drop them |
| Cost or latency creep from more calls | Record cost per 1,000 and p50/p95 latency on every run; keep any change only if it fits the guardrails |
| HTS revisions change codes | Pin the release (2026 Rev 21) per run; map retired codes in the index |

## 12. The first week, in order

1. Commit `eval/error_funnel.py` (0.1), and check that it reproduces section 2.
2. Build test-2026b (0.2) and the messy set (0.3); write Amendment 2 (0.4).
3. Offline, with no Decider: seed recall at n = 8, 12 and 16, with and without the tariff-text index (1.2, 1.3).
4. Offline, from the recorded rows: the combiner (4.2) with cross-validated pick accuracy and AUROC.
5. On the GPU host (about 3 s per product, so a dev pass costs under $1 of GPU time): the chapter fallback (1.1), then legal notes (2.1).
6. Write up each result in `eval/RESULTS.md` under "After the hackathon", with the funnel, CI and McNemar test, including the changes that don't help.
