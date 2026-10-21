# Builder Center submission sheet

Paste-ready fields for the hackathon's "Your project" tab. The article body is [`ARTICLE.md`](ARTICLE.md).

## Title

TariffTrail: Strands Decider 2B walks the US tariff tree so the agent never invents a customs code

## Short description (the card text on the Projects page)

TariffTrail gives a US import its 10-digit tariff code without guessing. Strands Decider 2B walks the official
tariff tree (18,946 codes) one calibrated choice at a time, then one Amazon Bedrock call picks among real codes
only. On 332 held-out 2026 CBP rulings: 36.7% exact against 19.0% for a tool-using LLM agent, zero invented codes,
$1.73 against $8.93 per 1,000 products. A Strands InterventionHandler sends every filing to a broker, and puts the
ones where Decider, Bedrock and past rulings agree at the front of the queue.

## Tags (both required, add before the deadline)

- `strands-decider-2b`
- `policy`

Optional extra tags, if the form allows more: `amazon-bedrock`, `strands-agents`, `agentic-ai`.

## Links

| What | URL |
|---|---|
| Public repository (Apache-2.0) | https://github.com/mahanteshimath/AWS-Strands-Decider-Hackathon |
| Demo video (2:59) | https://youtu.be/aU4kPYgsOcY |
| Live demo | https://main.d3o5ktn9yc15oj.amplifyapp.com/ |
| Reusable decision pattern | https://github.com/mahanteshimath/AWS-Strands-Decider-Hackathon/blob/main/PATTERN.md |

## Pasting the article

1. Paste everything in `ARTICLE.md` **below the first line** (the `# ...` title goes in the title field).
2. Images: the article hotlinks four images from `raw.githubusercontent.com`. If the preview shows them, keep them.
   If not, upload these files from the repo in the same places:
   - `docs/images/route-map.gif` (top, after the links line)
   - `docs/images/review-tiers.png` (after the fast-track paragraph)
   - `docs/images/accuracy-vs-cost.png` (after the results table)
   - `docs/images/ablation.png` (in "Is Decider doing the work?")
3. Check that the two code blocks (JSON and Python) and the three tables render.
4. Publish, then copy the article URL.

## After publishing

- Put the article URL into the link row of `README.md` (replace the `TODO at submission` comment) and push.
- Open the article once logged out to check it is public, and that the video plays from it.
- Submit before **Oct 23, 11:59 PM PDT**. After that, do not push code changes; docs-only fixes are fine if needed.
