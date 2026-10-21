# TariffTrail: Strands Decider 2B walks the US tariff tree so the agent never invents a customs code

*18,946 doors and one key. Built for the AWS Builder Center "Agent Experience Hackathon: Strands Decider".
Tags: `#strands-decider-2b` `#policy` `#tool-selection`. Code (Apache-2.0): github.com/mahanteshimath/AWS-Strands-Decider-Hackathon*

**Decision pattern demonstrated: Policy.** Before the agent may file a customs entry, Strands Decider 2B
classifies the product into its tariff category, one calibrated `choice` per level of the official
tree, and that decision sets what the agent is allowed to do next (deny, send back, or hand to a broker).
The same recipe also does **tool selection** over a 48-tool catalog, where its calibrated confidence is
safe to act on: all 17 requests above the bar were routed right, and the one miss scored below it, so the
agent asked a person first.

> **TL;DR.** Every US import now needs a 10-digit tariff code. Asked directly, an LLM invents a code
> that does not exist 91% of the time, and a tool-using agent gets 19% right. **TariffTrail** lets
> Strands Decider 2B walk the official tariff tree one calibrated choice at a time, then spends one
> short Amazon Bedrock call choosing among *real* codes. On 332 held-out 2026 customs rulings it gets
> **36.7% exactly right with zero invented codes, at $1.73 per 1,000 products against the agent's
> $8.93**, and a broker confirms every filing. For scale, the ATLAS benchmark reports 25% at 10 digits
> for GPT-5-Thinking on its own tariff test set. The decision pattern, **Calibrated Tree Descent**, is one
> standard-library file plus a Strands gate, and the same code routes requests across 48 tools.

**[▶ Watch the 3-minute video](https://youtu.be/aU4kPYgsOcY)** · **[Try the live demo](https://main.d3o5ktn9yc15oj.amplifyapp.com/)** ·
**[Code and the reusable pattern](https://github.com/mahanteshimath/AWS-Strands-Decider-Hackathon)**

![TariffTrail classifying a hardcover book: a route map of Strands Decider's probability at every fork, ending on code 4901.99.00.70](https://raw.githubusercontent.com/mahanteshimath/AWS-Strands-Decider-Hackathon/main/docs/images/route-map.gif)

*A real recorded run, CBP ruling N361497. Each stop is one Decider call, each branch is labelled
with its probability, and each dotted red branch is `none_of_these`. It lands on `4901.99.00.70`,
the code CBP ruled. [Replay this run](https://main.d3o5ktn9yc15oj.amplifyapp.com/#run=N361497).*

## The reusable decision recipe: Calibrated Tree Descent

Three parts you can copy into your own agent. Full write-up: [`PATTERN.md`](https://github.com/mahanteshimath/AWS-Strands-Decider-Hackathon/blob/main/PATTERN.md).

**1. The typed question and its option set.** One Decider call per fork of the tree:

```json
{
  "state": "PRODUCT FACTS:\n<the product>\n\nCLASSIFIED SO FAR (official tariff wording):\n<path chosen so far>",
  "questions": {
    "child": {
      "type": "choice",
      "instructions": "Which tariff line in the list describes the product? Choose by the product's facts and the official wording of each line, at this level of the US Harmonized Tariff Schedule.",
      "criteria": {
        "A": "Of cotton",
        "B": "Of synthetic fibres",
        "C": "Other (anything not covered by: Of cotton; Of synthetic fibres)",
        "none_of_these": "None of these lines can describe the product; an earlier level was chosen wrongly"
      }
    }
  }
}
```

The option-set rules: neutral letters (so the model chooses on meaning, never on a memorised code), the
tree's own wording, every "Other" rewritten against its siblings, and a `none_of_these` exit below the top
level. Up to 255 options per fork.

**2. The wiring that puts it in the agent's path.** A decision tool plus a Strands `InterventionHandler`
on the tool that acts:

```python
descent = CalibratedTreeDescent(tree, Decider(), policy=Policy(auto=0.6))   # any tree: tariff codes, tools, runbooks
ledger = DecisionLedger()
agent = Agent(tools=[decision_tool(descent, ledger, name="choose"), act],
              interventions=[DecisionGate(descent, ledger, guarded={"act": "item"}, decide_tool="choose")])
# act(item=...) is denied for made-up items, sent back if not decided, and paused for a person below the bar
```

| Before the guarded call | Strands action |
|---|---|
| The item is not a leaf of the tree | `Deny` |
| It was not chosen by the descent in this session | `Guide` ("decide first") |
| Its path probability is below `Policy.auto` | `Confirm`: a person approves |
| Otherwise | `Proceed` |

**3. How to use it.** Wrap your hierarchy in `DictTree` (or implement the four-method `Tree` protocol over
your data), label 50 cases, run once with `auto` above 1 so nothing auto-acts, read the threshold sweep,
and set `auto` to the lowest bar your error tolerance allows. If none qualifies, auto-act on nothing.
`tree_descent.py` and its Decider client use only the Python standard library.

## The $20 parcel problem

On 29 August 2025 the United States suspended the de minimis exemption. Overnight, every parcel
entering the US, including the $20 phone case, needed a **10-digit Harmonized Tariff Schedule
(HTS) code** on its customs entry. The code sets the duty, the quota, the anti-dumping exposure
and the paperwork. Get it wrong and the importer pays penalties, back duty or a seized shipment.

The schedule is a tree of 22 sections and 99 chapters that ends in **18,946 final codes** under
11,516 decisions, written in legal language. Almost a third of the options (32%) are literally the
word "Other".

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
On a wrong branch Decider puts most of its probability there, so that subtree's paths collapse
and the search moves on by itself.

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

![Accuracy of the products a broker reviews first](https://raw.githubusercontent.com/mahanteshimath/AWS-Strands-Decider-Hackathon/main/docs/images/review-tiers.png)

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

| System | 4-digit heading | **10-digit code** (95% CI) | Invented codes | Cost per 1,000 products |
|---|---|---|---|---|
| LLM, direct (Nova Pro) | 31.9% | 0.3% (0.1–1.7) | 90.7% | $0.30 |
| LLM agent + search tools (Strands, Nova Pro) | 39.5% | 19.0% (15.1–23.5) | 19.0% | $8.93 |
| Nearest past ruling | 38.0% | 24.4% (20.1–29.3) | 0% | ≈ $0 |
| Strands Decider alone (no LLM) | 46.7% | 25.3% | 0% | $0.38 |
| **TariffTrail** | **57.5%** | **36.7% (31.7–42.1)** | **0%** | **$1.73** |

Cost is us-east-1 list price from the AWS Price List API: Nova Pro tokens as recorded, plus
g6.xlarge GPU time as measured with one product at a time.

![Accuracy against cost per 1,000 products](https://raw.githubusercontent.com/mahanteshimath/AWS-Strands-Decider-Hackathon/main/docs/images/accuracy-vs-cost.png)

- **Accuracy:** nearly double the tool-using agent at 10 digits. On the same rulings, 92 were right
  only for TariffTrail and 33 only for the agent (exact McNemar p = 1.3 × 10⁻⁷). The tuning estimate
  was also 36.7%.
- **Cost:** about a fifth of the agent's, 7.8× fewer Bedrock tokens, at most one call per product,
  and no loops.
- **Safety:** zero invented codes, by construction.
- **Decider alone**, with no LLM generation, already beats the agent (25.3% vs 19.0%).

For scale: the ATLAS benchmark reports 25% at 10 digits for GPT-5-Thinking on its own HTS test
set. Ten-digit tariff classification is hard, and nobody should file one unreviewed yet.

## Is Decider doing the work? I checked

A fair reader asks whether the retrieval step does the real work. So after the test run I ran an
ablation on the same 332 products. Every arm keeps the recorded Decider search and the same Bedrock
prompt at temperature 0, and changes only the shortlist Bedrock picks from.

![Ablation: which shortlist sources Bedrock picks from](https://raw.githubusercontent.com/mahanteshimath/AWS-Strands-Decider-Hackathon/main/docs/images/ablation.png)

- **Neither source is enough alone.** Bedrock picking from Decider's top 3 gets 31.9%; from
  retrieval's top 4, 33.1%; from both together (TariffTrail), 36.7%.
- **Decider wins the heading.** Against the best design without Decider, TariffTrail is ahead at
  4 digits, 57.5% vs 51.2% (p = 0.015). At 10 digits its lead, 36.7% vs 33.1% (p = 0.2), is within
  noise: re-running the frozen shortlist step alone moves accuracy by a point.
- **Decider reaches codes retrieval cannot.** 22% of the test products have a code that none of the
  7,024 indexed rulings uses, so retrieval can never propose it. The tree walk had 16 of those in
  its top 3, and TariffTrail got 13 right.
- **The bottleneck has moved.** A wider shortlist (Decider's 3 plus retrieval's 4) holds the right
  answer 56% of the time, yet Bedrock's pick stays at 36%. The next gain is in choosing, not in
  finding candidates. That arm was chosen after seeing test results, so it needs fresh data to confirm.

I would rather show you that than a single flattering number.

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
The point is the shape: a calibrated decision at 72 ms is cheap enough to ask 18 times. The whole
walk through 18,946 codes takes about 1.7 of those 2.6 seconds, and the one Bedrock call most of
the rest. At list price that GPU time costs $0.60 per 1,000 products, about half of what the one
Bedrock call costs.

## The same pattern, a different tree

The pattern lives in one file, `tree_descent.py`, behind a small `Tree` interface. To show it is
not tariff-specific, I pointed it at a catalog of **48 tools across 8 services** (GitHub, Slack,
Jira, Calendar, Gmail, S3, Salesforce, PagerDuty). It routed **23 of 24 requests** correctly. All
17 requests above its confidence bar were right, and the one miss ("approve Dmitri's PR" sent to
*merge* instead of *review*) scored 0.57, below the bar, so the agent would have asked first.

Then I put it inside a Strands agent with `strands_kit.py`: a `decision_tool` the agent calls to
choose a tool, and a domain-free `DecisionGate` on the tool that acts. "Move PAY-311 to Done" scored
0.72 and went straight through. "Push tomorrow's design review to Friday 3pm" scored 0.38, so
Strands paused the agent until a person said yes.

One lesson from that run is about agent experience. My first decision tool told the model
`safe_to_act: false`. Nova Pro then asked the user itself and never called the tool, which looks
safe but leaves the policy to the model's mood. The tool now reports only the choice, and the gate,
in plain code, enforces the threshold I measured. **Put the policy where the model cannot argue
with it.**

## What I learned

- **Shrink the question, not the model.** The same tree that defeats an LLM asked "which of
  18,946?" is easy as a chain of "which of these four?". Decider, at 2B parameters with retrieval
  seeds and no LLM, got 25.3% of full codes right; Nova Pro asked directly got 0.3%.
- **Calibrated is not the same as safe to act.** Path probability made no mistakes above its bar
  on a two-level tool catalog (17 of 17) and was only a weak signal on an eight-level legal tree.
  Freeze the bar before the test, and accept "auto-clear nothing" as an answer.
- **Agreement beats any single confidence.** Three independent sources naming the same code (76%
  right) was a better trust signal than any one model's probability.
- **Put the policy where the model cannot argue with it.** The decision is a number; what the
  agent may do with it is plain code in a Strands intervention.

### What I got wrong on the way

- **Greedy walk with stack backtracking:** cables classified as furniture. Replaced by best-first search on path probability.
- **Labelling low-confidence forks as Decider decisions:** the first version would have auto-filed a 0.19-confidence guess. Fixed; tariffs now never auto-file.
- **Trusting path probability as "safe to file":** measured, not good enough for customs, and replaced by agreement-ordered review.
- **A one-call Decider verification of the shortlist:** AUROC 0.67 for 6 extra seconds per product. Measured and dropped.
- **Assuming Decider did all the work:** the ablation shows retrieval and Decider find different right answers; both stay.
- **Telling the agent whether it was safe to act:** it then made the call itself. The gate decides now.
- **No cap on the baseline agent:** $16 of Bedrock spend on one looping product. Hard caps, enforced by a Strands intervention.
- **A results sync that overwrote a live file:** recovered the rows through `/proc/<pid>/fd` and fixed the runner.

## What's next

After the frozen test I probed the final pick (labelled post-hoc, declared before it touched the test
set). One extra Bedrock call that reads the *whole* outline of the chosen heading and re-picks the
10-digit line took the same 332 products from **36.7% to 43.7%** (+34 fixed / -11 broken, McNemar
p = 0.0008) with Kimi K2.5 on Bedrock; with Nova Pro it was 39.2% (not significant). It cannot fix a wrong
heading, which is still where two thirds of the misses happen, so it stays out of the app until it is
confirmed on fresh rulings. Details: [`eval/HEADING_REFINE.md`](https://github.com/mahanteshimath/AWS-Strands-Decider-Hackathon/blob/main/eval/HEADING_REFINE.md).

The full plan, with where every miss happens and what each step should buy, is
[`docs/what_next.md`](https://github.com/mahanteshimath/AWS-Strands-Decider-Hackathon/blob/main/docs/what_next.md):
real fallback when retrieval misses the heading, chapter notes in Decider's state, and asking the
importer the one fact the description leaves out.

## Try it

`README.md` has the commands: fetch the HTS and the rulings, build the Titan index, serve
Decider, open the demo. The demo streams every Decider fork as it happens and can replay recorded
evaluation runs without a GPU. Every number in this article is regenerated from committed result
files by `eval/report.py`, `eval/ablation.py` and `eval/charts.py`.

Three recorded runs worth watching (each link opens and plays that run; replays show the winning
route, not the forks the search tried and abandoned):

- **An Anubis costume.** Decider's first answer was `none_of_these` (52%) over the costume heading
  (48%), so 21 of its 24 calls explored other parts of the tree. The costume route still won, at
  CBP's code: https://main.d3o5ktn9yc15oj.amplifyapp.com/#run=N357194
- **A hardcover book.** Six forks, four of them "Other (anything not covered by ...)" lines in a
  row, then "Hardbound books" at 60%: https://main.d3o5ktn9yc15oj.amplifyapp.com/#run=N361497
- **A car alarm with remote start.** At the radio-apparatus heading the right branch came third,
  at 29%, behind `none_of_these` and "Radar apparatus". One fork later Decider was 97% sure it is
  radio remote-control apparatus:
  https://main.d3o5ktn9yc15oj.amplifyapp.com/#run=N359480

- **Run Decider yourself on a free Colab GPU, no AWS account:** `notebooks/try_tarifftrail.ipynb` (tool routing,
  any of the 392 evaluation rulings re-run live, and your own product)
- **Demo (Classify hosted, Simulate, and 392 recorded real classifications):** https://main.d3o5ktn9yc15oj.amplifyapp.com/
  The 392 replays are the evaluated runs. **Classify hosted** runs your product live on the AWS User Group
  Madurai hosted strands-decider-2B, a newer build than the `v1-2610` checkpoint measured above, at
  its free tier of 10 requests a minute (one to two and a half minutes a product), so read it as a live
  demo, not as the evaluated system. **Simulate** shows the same search with a keyword stand-in for Decider.
- **Code and the reusable pattern:** github.com/mahanteshimath/AWS-Strands-Decider-Hackathon, `PATTERN.md`
- **The pattern in a Strands agent:** `examples/tool_catalog/agent.py`
- **Video (2:59):** https://youtu.be/aU4kPYgsOcY

*Decision support, not legal advice: a licensed customs broker is responsible for every entry.*
