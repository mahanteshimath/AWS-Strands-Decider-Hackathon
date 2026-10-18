---
workflow: general-video
flow: automation
storyboard: yes
message: "Don't make an agent choose among 18,946 options: let Strands Decider choose among a handful, many times, and know when to ask."
destination: AWS Builder Center hackathon submission (public video, under 3 minutes)
aspect: "16:9"
length: "~2:20"
language: en
audience: AWS builders and hackathon judges (Strands, Bedrock, agent developers)
voice: builder's cloned voice (Chatterbox Turbo, ~/.cache/cloudbytes/ref_clean.wav)
---

# TariffTrail demo video

## Intent
Narrated explainer + demo for the "Agent Experience Hackathon: Strands Decider". Hook on the de
minimis change and the measured LLM failure (90.7% invented codes), reframe ("which of these
four"), show the Decider tree walk and the one Bedrock call, a real recorded run in the TariffTrail
UI, the Strands intervention, the measured results, the honest limit, and the 48-tool reuse.

## Script
Approved by the user at gate 1 (2026-10-18): SCRIPT.md (17 lines). Every number is measured
(eval/RESULTS.md, examples/tool_catalog/RESULTS.md).

## Review
Storyboard and live HTML preview with timestamp feedback; render the MP4 only after approval (user's
standing preference). Voice: the user's clone, not a stock voice.

## Notes
- Visuals are drawn in the composition (diagrams, charts, a recreation of the TariffTrail UI driven
  by a real recorded run), not screen-captured, so the render is deterministic.
- AWS service names as text labels; no third-party slides.
- Close card: repo github.com/mahanteshimath/AWS-Strands-Decider-Hackathon, #strands-decider-2b #policy.
