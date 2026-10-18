# TariffTrail — hackathon video script (DRAFT for gate 1)

Target: 16:9, ~2:35, narrated in the builder's cloned voice. `⟨TT⟩` = TariffTrail test-set number,
filled from eval/RESULTS.md when the test run finishes. All other numbers are measured.

## L01 · hook
say: Since August 2025, every parcel entering the United States needs one of eighteen thousand nine hundred tariff codes.
show: A parcel drops onto a conveyor; a counter spins up to 18,946 codes behind it.

## L02 · the failure
say: We asked an AI model on Amazon Bedrock for the code. Ninety-one percent of its answers did not even exist.
show: Answers stamp onto a wall; most get a red DOES NOT EXIST stamp. Caption: 90.7% invented, 332 real CBP rulings.

## L03 · tools do not fix it
say: Give it search tools, and it wanders. One product took two hundred and one tool calls and nineteen million tokens.
show: A tool-call counter racing to 201, tokens to 19.6M, an agent loop spinning.

## L04 · the reframe
say: The model was not stupid. It was asked the wrong question. Not which of eighteen thousand, but which of these four.
show: 18,946 tiles collapse into four cards.

## L05 · enter Decider
say: Strands Decider is a two billion parameter decision model. It answers typed questions in one pass, with calibrated probabilities.
show: Decider chip; a choice question with four options and probability bars filling.

## L06 · the walk
say: TariffTrail walks the official tariff tree, one fork at a time, and every fork has an exit: none of these.
show: Tree animation: section, chapter, heading, line; a wrong branch lights red on "none of these" and collapses.

## L07 · path probability
say: Multiplying Decider's answers along a path ranks every path in the tree, so a wrong turn backtracks by itself.
show: Two candidate paths with running products; the search jumps to the better one three levels up.

## L08 · retrieval proposes
say: Retrieval proposes, Decider decides. Titan embeddings find similar past rulings, and Decider picks among their headings.
show: Titan icon, 20 past rulings fan out, 8 headings, Decider chooses one.

## L09 · one Bedrock call
say: Only then does Bedrock speak, once, choosing among a short list of real codes. It cannot invent one.
show: Shortlist of 4 real codes; Nova Pro picks one; a lock icon on "real codes only".

## L10 · demo intro
say: Here is a real run on a twenty twenty six customs ruling.
show: TariffTrail UI, replay mode, a real ruling.

## L11 · demo walk
say: Each card is one Decider decision. Green is chosen, red is none of these. The result arrives with its full legal path.
show: Trail cards animate in with probability bars; result card with code, path and duty.

## L12 · the gate
say: Filing is an action, so a Strands intervention guards it. Invented codes are denied. Everything else waits for a licensed broker.
show: ClassificationGate: Deny, Guide, Confirm chips light up in turn.

## L13 · results
say: On three hundred thirty two held-out rulings, TariffTrail got ⟨TT⟩ percent of full codes right. The tool-using agent got nineteen. The plain model, almost none.
show: Bar chart: TariffTrail ⟨TT⟩%, nearest ruling 24.4%, LLM agent 19.0%, LLM direct 0.3%.

## L14 · cost
say: With zero invented codes, and about seven times fewer Bedrock tokens than the agent.
show: 0% invented vs 19%; tokens per product ⟨TT tokens⟩ vs 9,789.

## L15 · honesty
say: One thing did not work. Decider's path probability did not predict when it was right, so TariffTrail never files a tariff code on its own.
show: Calibration chart, flat. Stamp: BROKER REVIEW.

## L16 · reuse
say: The pattern is one file. Pointed at forty eight tools, it routed twenty three of twenty four requests, and the one miss asked first.
show: tree_descent.py card; tool catalog tree; 23/24, 17/17 auto-called correct.

## L17 · close
say: TariffTrail. Choose among a handful, many times, and know when to ask. The code is open source.
show: Logo, repo URL, #strands-decider-2b #policy.
