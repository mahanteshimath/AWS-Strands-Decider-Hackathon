# 18,946 doors and one key: teaching an agent to classify imports without guessing

*Built for the AWS Builder Center "Agent Experience Hackathon: Strands Decider".
Tags: `#strands-decider-2b` `#policy`. Code (Apache-2.0): github.com/mahanteshimath/AWS-Strands-Decider-Hackathon*

## The $20 parcel problem

On 29 August 2025 the United States suspended the de minimis exemption. Overnight, every parcel
entering the US, including the $20 phone case, needed a **10-digit Harmonized Tariff Schedule
(HTS) code** on its customs entry. The code sets the duty, the quota, the anti-dumping exposure
and the paperwork. Get it wrong and the importer pays penalties, back duty or a seized shipment.

The schedule is a tree: 22 sections, 97 chapters, about 1,300 four-digit headings, and
**18,946 final codes** under 11,516 decisions, written in legal language. Over a quarter of the
options are literally the word "Other".

It is the clearest example I know of an agent drowning in options, so I measured how badly
on **332 real binding rulings issued by US Customs (CBP) in 2026**, held out from all tuning:

- **Ask an LLM directly** (Amazon Nova Pro on Bedrock): **1 out of 332** full codes correct, and
  **91% of the answers were codes that do not exist in the schedule.**
- **Give it tools**, as a Strands agent with keyword search and "list the lines under this code":
  **19% correct, and still 19% invented codes**, at about 9,800 tokens per product. On one tuning
  product, before I capped it, the agent looped through **201 tool calls and 19.6 million tokens**.
- **Copy the code of the most similar past ruling** (no LLM at all): **24% correct.** Plain
  retrieval beats the tool-using agent.

The LLM is not bad at reasoning. It is being asked the wrong question: "which of 18,946?"
instead of "which of these four?"

## The idea: never choose among thousands

Strands Decider 2B answers small, typed questions about a piece of text in one forward pass:
`noul` (true or false), `choice` (pick one of up to 255 options) and `score`. Its probabilities
are **calibrated**, and that is the property everything below relies on.

TariffTrail walks the tariff tree one fork at a time and asks Decider one `choice` question at each:

> *Which tariff line in the list describes the product?*
> A. Of cotton · B. Of synthetic fibres · C. Of wool or fine animal hair · D. Other (anything not
> covered by: ...) · **none_of_these**

Three design decisions turned this from a toy into something that works.

**1. Rank paths, not steps.** Each fork's probabilities sum to one, so multiplying them along a
path gives a probability that can be compared across the *entire* tree. The search is best-first
on that number. My first version walked greedily and backtracked to the most recent fork. It sent
an aviation headset cable into *Toys* and then *Furniture*. Ranking whole paths fixed that without
a single backtracking rule.

**2. Give every fork an exit.** Below the top level every question includes `none_of_these`.
On a wrong branch Decider puts 66 to 90% of its probability there, so that subtree's paths
collapse and the search moves on by itself.

**3. Retrieval proposes, Decider decides.** Walking down from section titles fails at the
heading level, where legal wording beats intuition (worked building stone is 6802, not "stone
articles, other" 6815). So TariffTrail first embeds the product with **Amazon Titan Text
Embeddings V2** and looks up the 20 most similar *pre-2026* CBP rulings. Their headings become the
first question, with eight candidates plus `none_of_these`. Among those eight, the right heading
was present 78% of the time on the tuning set. When none fits, the probability mass flows to the
full walk from the top.

## Then one Bedrock call, and a human who knows where to look

After the search, **one** Amazon Bedrock call chooses among Decider's top three complete codes,
plus the nearest past ruling's code, with similar rulings as context. It sees only real codes, so
it cannot invent one. That shortlist contained the right answer in 29 of 60 tuning cases (48%),
and Bedrock picked it in 22 of those, about three times out of four.

The plan was to skip Bedrock and the broker whenever Decider's path probability was high. **That
part did not work**, and the evaluation says so. I froze the rule before the test run: auto-file
only at a bar whose tuning cases are at least 90% correct. No bar qualified. Path probability did
rise with accuracy on the test set (23% correct below 0.2, 67% at 0.4–0.6, AUROC 0.63), but
multiplying eight forks of legal wording does not make a number you can file a customs entry on.

So TariffTrail never files a tariff code unattended. It uses agreement instead: when Decider,
Bedrock and the past rulings all name the same code, the entry goes to the front of the broker's
queue. That **fast-track** tier held 16% of test products, and **76% of them were right, against
29% of the rest.**

## Guarding the action: a Strands intervention

Classification is advice; filing is an action. The Strands agent's `file_entry` tool sits behind
`ClassificationGate`, an `InterventionHandler`:

- **Deny** a code that is not in the schedule.
- **Guide** the agent back if the code did not come from `classify_product` in this session.
- **Guide** if a second Decider `noul` says the filing describes different goods from what was classified.
- **Confirm** every filing with a licensed broker, saying whether it is fast-track (all sources
  agree) or disputed, and which alternatives were considered.

The calibrated decision becomes the human-in-the-loop policy for the action.

## Results

Test split: 332 held-out 2026 rulings, run once with the configuration frozen on 60 tuning rulings.

| System | 4-digit heading | **10-digit code** (95% CI) | Invented codes | Bedrock tokens / product |
|---|---|---|---|---|
| LLM, direct (Nova Pro) | 31.9% | 0.3% (0.1–1.7) | 90.7% | 241 |
| LLM agent + search tools (Strands, Nova Pro) | 39.5% | 19.0% (15.1–23.5) | 19.0% | 9,789 |
| Nearest past ruling | 38.0% | 24.4% (20.1–29.3) | 0% | 0 |
| Strands Decider alone (no LLM) | 46.7% | 25.3% | 0% | 0 |
| **TariffTrail** | **57.5%** | **36.7% (31.7–42.1)** | **0%** | **1,258** |

- **Accuracy:** nearly double the tool-using agent at 10 digits. On the same rulings, 92 were right
  only for TariffTrail and 33 only for the agent (exact McNemar p = 1.3 × 10⁻⁷). The tuning estimate
  was also 36.7%.
- **Cost:** 7.8× fewer Bedrock tokens than the agent, at most one call per product, and no loops.
- **Safety:** zero invented codes, by construction.
- **Decider alone**, with no LLM generation, already beats the agent (25.3% vs 19.0%).

For scale: the ATLAS benchmark reports 25% at 10 digits for GPT-5-Thinking on its own HTS test
set. Ten-digit tariff classification is hard, and nobody should file one unreviewed yet.

## Latency: 61 seconds on CPU, 2.6 seconds on a GPU

Eighteen Decider calls per product is only sensible if each call is cheap, so I measured it twice.
The frozen test run used a CPU host (my GPU quota was still zero when I froze the test):
**2.5 s per Decider call, 61 s per product**. When the quota arrived I ran the *same* 332 products
again, unchanged, on a g6.xlarge with an NVIDIA L4:

| | CPU (c7i.4xlarge) | GPU (g6.xlarge, L4) |
|---|---|---|
| Decider call, p50 / p95 | 2,499 / 5,144 ms | **72 / 131 ms** |
| Whole product incl. one Bedrock call, p50 / p95 | 60.6 / 86.7 s | **2.6 / 3.3 s** |
| 10-digit accuracy | 36.7% | 37.4% |

The accuracy gap is run-to-run noise (same final code on 300 of 332 products), not a GPU advantage.
The point is the shape: a calibrated decision at 72 ms is cheap enough to ask 18 times, and
most of the 2.6 seconds is the single Bedrock call, not the walk through 18,946 codes.

## The same pattern, a different tree

The pattern lives in one file, `tree_descent.py`, behind a four-method `Tree` interface. To prove
it is not tariff-specific, I pointed it at a catalog of **48 tools across 8 services** (GitHub,
Slack, Jira, Calendar, Gmail, S3, Salesforce, PagerDuty). It routed **23 of 24 requests**
correctly. All 17 requests above its confidence bar were right, and the one miss
("approve Dmitri's PR" sent to *merge* instead of *review*) scored 0.57, below the bar, so the
agent would have asked first.

## What I got wrong on the way

- **Greedy walk with stack backtracking:** cables classified as furniture. Replaced by best-first search on path probability.
- **Labelling low-confidence forks as Decider decisions:** the first version would have auto-filed a 0.19-confidence guess. Fixed; tariffs now never auto-file.
- **Trusting path probability as "safe to file":** measured, not good enough for customs, and replaced by agreement-ordered review.
- **A one-call Decider verification of the shortlist:** AUROC 0.67 for 6 extra seconds per product. Measured and dropped.
- **No cap on the baseline agent:** $16 of Bedrock spend on one looping product. Hard caps, enforced by a Strands intervention.
- **A results sync that overwrote a live file:** recovered the rows through `/proc/<pid>/fd` and fixed the runner.

## Try it

`README.md` has the five commands: fetch the HTS and the rulings, build the Titan index, serve
Decider, open the demo. The demo streams every Decider fork as it happens and can replay recorded
evaluation runs without a GPU.

- **Demo (recorded runs, 392 real classifications):** https://main.d3o5ktn9yc15oj.amplifyapp.com/
- **Code and the reusable pattern:** github.com/mahanteshimath/AWS-Strands-Decider-Hackathon, `PATTERN.md`
- **Video (2 minutes):** VIDEO_URL_HERE

*Decision support, not legal advice: a licensed customs broker is responsible for every entry.*
