# Objective — Ask Raju Hackathon

**Status:** Build-ready
**Author:** Vipul Sehgal
**Date:** 2026-04-25
**Time budget:** 3 hours
**Builder:** Claude Code (Vipul: reads errors, clicks buttons, follows instructions, doesn't write code)
**Companion documents:** `spec_hackathon.md` (technical spec for the 3-hour build), `objective.md` (full v0 vision and launch arc), `spec_v0.md` (full protocol, fully locked)

---

## Why I'm doing this hackathon

I have been refining a real protocol for agentic memory (`spec_v0.md`) and a real product idea (Ask Raju) over multiple sessions of design work. The full launch arc is 8 weeks. The hackathon is a forcing function to ship a working slice of the idea **today, in 3 hours**, that proves the killer demo moment to a room of judges.

It's also a stress test for me: can the spec produce a working prototype quickly when handed to Claude Code, or did I over-design? If the spec is right, this should be straightforward. If it's wrong, the friction will surface in the next 3 hours and I'll learn what to fix.

The hackathon win is secondary. The real win is: **I leave with a working tool and a stronger conviction that the spec is right.**

---

## What I want from the 3 hours

A live demo at a public URL where:

1. I can paste a vendor model-card and watch the system extract structured model metadata + multiple benchmark rows + a vendor opinion in one paste, with the data appearing live in Supabase Studio for the audience to see.
2. I can browse a model and see a real model profile: vendor metadata, a benchmark table with two scores visually flagged in red because they disagree (Anthropic's claim vs an independent re-run), and a list of long-form opinions rendered as proper markdown.
3. I can ask a natural-language question and get a grounded answer with inline `[r:id]` citations that point to specific seeded records, including an acknowledged dissent ("two sources disagree on this; here's both").

If those three moments work end-to-end, the demo is a win. Everything else is decoration.

---

## The product (the demo subset of Ask Raju)

Ask Raju is a knowledge-management tool for AI capability claims. The full v0 has three primitives (conflict-flagging typed memory, tool self-governance, friction-gated schema evolution) on a substrate (typed records, agent + human retrieval lenses, model selection).

**The hackathon ships a deliberate subset:**

- **Capture surface (3 flavors):** model card → populates `models` + `benchmarks` + vendor opinion in one paste; independent benchmark → populates `benchmarks`; opinion → uploads markdown file to Supabase Storage with metadata row.
- **Browse surface:** model profile with metadata, benchmarks table with conflict pairing in red, opinions list rendered from Supabase Storage as markdown.
- **Query surface:** grounded synthesis with inline citations and acknowledged dissent.

**Storage shape:**
- `models`, `benchmarks`, `opinions`, `syntheses` tables in Supabase Postgres
- Opinion bodies as actual markdown files in a Supabase Storage bucket (`opinions/{model_name}/{date}-{slug}.md`)
- Each opinion file is self-describing via YAML frontmatter

Full schema and rationale in `spec_hackathon.md`.

---

## The wow moment (what should land for judges)

Every hackathon demo lives or dies on one moment. For Ask Raju, it's this: **a model's browse view shows vendor's "81% on SWE-bench" and a practitioner's "76% on the same eval, suspected contamination" side by side in red, and the query "which model is best for code?" returns a grounded answer that cites BOTH rows and acknowledges the disagreement instead of smoothing it away.**

That moment makes the audience feel: this tool refuses to lie to me about the AI race. Most knowledge tools confidently flatten contradictions. This one shows the contradiction as a feature.

If I can land that in the 3-minute pitch, the rest is supporting material.

---

## What I am explicitly NOT demonstrating in 3 hours

The full protocol does ten things this hackathon doesn't. Naming them prevents me (and any judge or reviewer who reads the spec) from thinking the hackathon defines the bounds of the protocol:

- **Schema evolution** (Primitive 3 entirely): types are hardcoded for the demo
- **Tool self-governance** (Primitive 2 entirely): cost cap is a constant, not a memory-resident policy
- **Verification pass on synthesis output:** the LLM is prompted to ground in records but no separate verifier runs
- **Conflict resolution backlog** with rationale-required acceptance: conflicts just sit flagged
- **LLM-suggested aliases** for subject/capability matching: exact-match only on normalized strings
- **Activity logging / trace_id / human debug lens:** console logs only
- **Per-agent preferred_models priority lists / sub-agent spawning:** single LLM provider, single calls
- **Cross-table conflict** (benchmark vs opinion): same-table conflict only
- **Onboarding** (interactive type vocabulary drafting): types are hardcoded
- **Per-type temporal_semantics:** all types behave as recency-wins implicitly

Each of these is in `spec_v0.md` and on the v0 roadmap. The hackathon's job is to prove the **core wow** — capture, conflict-flag, ground — not the full protocol.

---

## Stack and decisions (locked)

See `spec_hackathon.md` for full technical detail. Quick summary:

- **App:** Streamlit (Python)
- **DB:** Supabase Postgres + Supabase Storage bucket
- **LLM:** Anthropic API (Sonnet 4.6 for synthesis + extraction, Haiku for cheap conflict-check)
- **Dev environment:** Replit (browser-based, zero local setup)
- **Deploy:** Streamlit Community Cloud (one-click from GitHub)
- **Workflow:** Claude Code generates code in Replit terminal; Vipul reads errors, copies them back to Claude, clicks deploy buttons

One open decision still being discussed separately: whether to use NVIDIA API for DeepSeek V4 Flash/Pro and MiniMax 2.7 inference (vs all-Anthropic). Resolution will be added to `spec_hackathon.md` when locked.

---

## The 3-minute demo arc

Per `spec_hackathon.md`'s demo script:

| Time | Move |
|---|---|
| 0:00–0:15 | Hook: "Every week a new AI model drops with claims that contradict last week's. I forget the nuance. Ask Raju captures every claim with provenance and surfaces contradictions so I never forget the disagreements." |
| 0:15–1:00 | Browse Opus 4.7's profile. Point at the vendor 81% vs practitioner 76% on SWE-bench, paired in red. "Ask Raju doesn't smooth this away." |
| 1:00–1:45 | Capture live: paste a fresh vendor model card. Watch the system populate models + benchmarks + opinion in one paste, with rows appearing live in Supabase Studio open in another tab. |
| 1:45–2:45 | Query: "Which model is best for long-context recall?" Grounded answer with inline `[r:id]` citations, including the acknowledged dissent on Gemini 3 Pro and MiniMax 2.7. |
| 2:45–3:00 | Close: "Three primitives in the full protocol. The same primitives drive a production system in TurnoCockpit. Spec at github.com/vipul/ask-raju." |

---

## Connection to the bigger picture

What this hackathon delivers is **one of two production proofs for the agentic memory protocol I am publishing**. The other is TurnoCockpit running these primitives on real bus-leasing operations data in parallel.

The launch arc (`objective.md`):

1. ✓ Write the v0 spec (done, locked in `spec_v0.md`)
2. → Build Ask Raju (this hackathon)
3. Onboard 10–15 builder friends to use Ask Raju daily for 4 weeks
4. Catch real contradictions in real usage; collect receipts
5. Write the launch piece grounded in those real receipts
6. Drop the spec as a public gist + open-source the Ask Raju repo
7. Newsletter post + LinkedIn distribution
8. TurnoCockpit production case study as follow-up

The hackathon is step 2 of that 8-step arc. The 3-hour build is itself a forcing function — if I can ship a working subset of Ask Raju in 3 hours, then the spec is provably implementable, which is the credibility-receipt the launch piece will need.

---

## Success criteria for the 3 hours

**Necessary (must hit):**

- Live demo at a Streamlit Community Cloud URL
- All three capture flavors work (model card, benchmark, opinion)
- Browse view shows model profiles with conflict pairing in red
- Query returns grounded answer with inline citations
- The wow moment lands at least once during the pitch
- I leave with a public URL I can share on LinkedIn this week

**Stretch (nice to hit):**

- Captures during the demo (not just pre-seeded data) work without errors
- Supabase Studio open in another tab during the demo for the "see the data" effect
- Synthesis answer cites at least one personal observation (mine, from seed)
- I use the tool myself within 24 hours of the hackathon for a real model-pick decision

**Won't hit and that's fine:**

- Polish equivalent to a production product
- Anything from the "explicitly NOT demonstrating" list above
- Onboarding friends today (that's week 3 of the launch arc)

---

## What this is NOT

- Not a finished product. It's a working slice that proves a specific moment.
- Not a substitute for the full v0 spec. The spec stays canonical; this is one possible early implementation.
- Not a public launch. The hackathon URL might be shared after if it's solid; the real launch follows the 8-week arc with proper receipts.
- Not the final architecture. Choices made for 3-hour speed (single-direction conflict_link, no tags, no schema evolution, etc.) will be revisited for v0.1.
