# Objective — Ask Raju

**Status:** Draft v0.3
**Author:** Vipul Sehgal
**Date:** 2026-04-25
**Product name:** Ask Raju
**Companion document:** `spec_v0.md` (canonical technical spec, fully locked across 18 decisions)

## Why I'm building this

I am tired of not knowing which AI model is actually best for what.

Every week a new model drops. Every lab claims its model leads on something. Every leaderboard ranks them differently. Every practitioner thread on Hacker News has a take, half of them contradict the other half. I read it all, form an opinion, then forget the nuance two weeks later when a new release shows up. By the time I'm picking a model for a real task in TurnoCRM or TurnoCockpit, I'm half-guessing from a hazy memory of what I read three months ago.

This costs me real money and real time. Last month I paid for a heavy-tier model on a task that a cheaper model handled equally well. Two weeks before that I picked the cheaper one for a task it quietly failed at, and I shipped a bad result before realizing. Both mistakes were avoidable if I had a system that remembered what I had read, what I had personally observed, and where the evidence pointed.

I want to build that system, for myself first. If others find it useful, great. The first user is me.

## What I actually want

A persistent memory that:

- Captures every claim about every AI model from every source I trust, with full provenance
- Stores my own usage observations alongside vendor and third-party claims, weighted appropriately
- Surfaces contradictions instead of smoothing them away (when Anthropic's launch post and a Hacker News thread disagree about Opus, I want to see both)
- Tracks how my understanding and the consensus shift over time (a model's reputation today is not the same as it was 3 weeks ago)
- Answers "which model should I use for X right now" with a synthesis I can trust, including the assumptions that produced it
- Lets me come back in 2 months and not have lost the nuance I had today

## The product, concretely

Three surfaces. Nothing else in v0.

### 1. Capture

A paste box plus an optional Chrome extension. I drop in a URL, a tweet, a blog excerpt, a personal observation from my own work. The system extracts the structured fields: which model, which capability, what claim, source, date, claimant. I review the auto-generated tags before save. The record is stored as a typed memory entry.

Example captures I would make tomorrow:
- Anthropic's Opus 4.7 launch post: "state of the art on SWE-bench Verified at 81%"
- Practitioner on HN: "Opus 4.7 is great at refactors but worse than Sonnet 4.6 on greenfield React"
- My own usage: "Opus failed twice today on a Postgres migration that Sonnet got right on the first try"

### 2. Browse

One page per model. One page per capability ("code refactoring," "agentic tool use," "long-context recall"). One page per claimant. Each page shows every claim with provenance and timestamps. Contradictions are visually flagged in red. This is the page I will look at when I am about to pick a model for a real task.

### 3. Query

Ask the system anything in natural language:

- "Which model is best for code refactoring right now?"
- "What changed about Opus's reputation in the last two weeks?"
- "Show me every contradiction about Gemini 3 Pro."
- "What did I personally observe about Sonnet on Postgres tasks?"

Every answer is grounded: each claim cites a specific source record by ID. If the captured records can't support an answer, the system says "I don't have data on this" rather than guess. A metadata header above the answer shows the confidence and a count of any verification-removed claims, so I can tell at a glance whether the system held back. The structured form of the synthesis (citations, source weights, exclusions, dissents) is queryable for anyone who wants to drill in.

## The three primitives this system will demonstrate

The system needs to do three things that most AI memory tools skip. These are the primitives the build will exercise and that I will write up after enough real use:

1. **Conflict-flagging typed memory.** Two records about the same model and same capability that disagree get flagged structurally. Nothing is silently merged into a smoothed average. Synthesis records ride on the same primitive: every synthesis must cite its sources, stay grounded in the captured records, and say "I don't know" when the records can't support an answer.
2. **Tool self-governance via memory-resident policies.** Tools (the fetch agents, the capture agent, the model-call wrapper) read their constraints from memory at runtime ("don't fetch from sources without citations," "rate-limit X.com," cost cap from onboarding). Policies are editable records, not code.
3. **Friction-gated schema evolution with decision provenance.** The type vocabulary, tag namespaces, policy schemas, and temporal semantics are all editable, but every change passes through a high-friction gate (cooldown, rationale, LLM-assisted case-law analysis, single human authority). Every decision is logged and feeds future LLM recommendations.

These are the three ideas I have been refining out of an earlier four-primitive draft (which itself was extracted from the TurnoCockpit PRD). Two earlier candidates — Plan-as-the-assumptions-register and Tier-sticky sub-agent delegation — turned out to be TurnoCockpit-specific complexity that reduces cleanly: the synthesis trust requirement collapses into Primitive 1's grounding contract; the cost-economics framing collapses into deployment-level model selection (single primary agent with priority-ordered preferred_models). The three remaining primitives are the universal floor.

**"It works" is a precursor to "it works cost-effectively."** The protocol defines what makes the system trustable. Cost optimization is a refinement built on top, not a foundational primitive.

Full mechanism, schemas, and edge-case handling are in `spec_v0.md`.

## Data sources for v0

Be ruthless. Only these:

- Official launch posts and model cards from Anthropic, OpenAI, Google, Meta, xAI (RSS or scrape)
- LMArena leaderboard snapshots, daily
- One curated benchmark feed (LiveBench)
- One practitioner aggregator (Hacker News /show + AI-tagged threads, or a small set of curated substacks)
- YouTube interviews and reviews (see design note below)
- My own captures via paste box and Chrome extension

Skipped in v0: Twitter/X scraping, random blog crawling, Discord and Slack channels. All are rabbit holes that can come in v1 if v0 earns its keep.

### YouTube ingestion design

YouTube is structurally different from a tweet or a blog post: a single 30-minute video can contain 15 distinct claims about 8 different models, often by multiple speakers. One video becomes **many records**, not one.

- **Transcript acquisition:** prefer YouTube's auto-caption API or `youtube-transcript-api`-style fetch. If unavailable for a given video, fall back to a paste box that accepts the user-pasted transcript.
- **Parent record:** one record per video carrying the URL, title, channel, full transcript, and metadata. Stored once, used as the source-of-truth provenance anchor.
- **Child records:** a claim-extraction agent runs over the transcript and emits N typed claim records. Each child record links back to the parent video, carries a timestamp, and identifies the **speaker** as claimant (not the channel, since interviews routinely have multiple speakers including guests reporting third-party claims).
- **Two-level provenance:** child records support "speaker reporting someone else's claim" by carrying both `speaker` and `attributed_to` fields. A video where the host says "Anthropic told me X" stores `speaker = host`, `attributed_to = Anthropic`.
- **Extraction accuracy as a first-class case:** the spec must treat "the extraction agent got this claim wrong" as a normal failure mode, not an edge case. User reviews extracted claims before save and can edit, drop, or merge them. Wrong extractions feed back into agent tuning.

## Why now, and why this domain

Three reasons:

1. **The pain is mine and immediate.** I am picking AI models multiple times a week for real work. The cost of a wrong pick is real money and real time. I will use this tool every day from the moment it works.
2. **The data environment is naturally rich.** Vendor claims, third-party benchmarks, practitioner reports, and my own usage are four different epistemic types. The typed memory layer earns its keep on day one.
3. **Friends in my network have the same pain.** Other founders and builders pick AI models constantly and forget the nuance constantly. If the tool works for me, 10 to 15 of them will use it without me having to convince them.

## Strategic bets

1. **Build for myself first.** Every design decision is answered by "would I, Vipul, want this when I am picking a model on Tuesday morning?" Not "would users want this." The first user is me.
2. **Ship the working tool before publishing anything about the spec.** No write-up without receipts. The spec becomes credible only because the tool works.
3. **Onboard friends quietly.** No public launch in week 1. Send the link to 10 to 15 builders I know. Let them break it. Capture what surprises them.
4. **Single primary agent, runtime sub-agents.** The protocol describes one agent (the knowledge manager) with tools for capture, retrieve, synthesize, verify, propose schema. Sub-agents spawn at runtime when the agent wants to delegate (e.g., a long-transcript extraction). No pre-declared agent hierarchy.
5. **"It works" precedes "it works cost-effectively."** Get the system trustable first. Cost economics (tier-sticky-style optimization) is a deployment-level refinement, not a protocol concern.
6. **TurnoCockpit runs in parallel as the second proof.** Two domains running on the same three primitives makes the spec look general instead of accidental.
7. **Distribution stays personal.** Newsletter and LinkedIn. No paid promotion. The story carries itself if the tool is real.

## Launch arc (target: 8 weeks from 2026-04-25)

| Week | Move |
|---|---|
| 1 | ✓ Spec v0 written and fully locked across 18 decisions (`spec_v0.md`). Lock product name. Pick tech stack. Set up repo, data model, capture flow. |
| 2 | Browse UI, provenance display, the contradiction-flagging surface. |
| 3 | Query agent, grounded-answer rendering with metadata header, tagging. |
| 4 | Onboard 10 to 15 builder friends. Start capturing claims daily. |
| 5 | Use the system every day for my own model picks. Catch real contradictions. Log them. |
| 6 | Polish. Write the launch piece based on real receipts (claims captured, contradictions surfaced, model-pick decisions improved). |
| 7 | Publish the gist + open-source the repo. Newsletter post + LinkedIn. |
| 8 | TurnoCockpit production proof points published as a follow-up case study. |

## Open decisions (spec is locked; these are tooling/distribution decisions)

The 18 design decisions in `spec_v0.md` are all locked. What's still open belongs to build setup and distribution:

1. **Product name.** ✓ LOCKED: **Ask Raju**. The name IS the catchphrase ("let me ask Raju," "what does Raju say?"). Two words solve the disambiguation problem of bare "Raju" and frame the interaction as asking a knowledgeable friend rather than possessing a helper. Decided 2026-04-25.
2. **Tech stack.** Default: Postgres + Node or Spring Boot + React + Claude Code. Hosting on Vercel + Supabase, or fully local with Docker Compose. Confirm before week 2.
3. **License.** MIT recommended for maximum adoption. Confirm before repo creation.
4. **Workspace model.** Single shared workspace for me and friends, or per-user schemas. Affects auth, data isolation, onboarding friction.
5. **TurnoCockpit slice in parallel.** Which one or two primitives to ship on Turno's real data first, and what production incident to harvest for the launch piece.
6. **Initial models in deployment config.** Likely Qwen 28B local (preferred) + Anthropic Haiku/Sonnet API as fallbacks. Confirm before first build.

## Out of scope for v0

- Multi-user accounts with full RBAC. Admin-issued passwords for me and friends, like the TurnoCockpit pilot model.
- Sandbox / counterfactual layer. TurnoCockpit-specific, does not earn its keep here.
- Plan-as-the-assumptions-register edit-and-rerun mechanic (the heavyweight version of synthesis transparency). Reduced to the lightweight grounding contract within Primitive 1.
- Tier-sticky sub-agent delegation as a primitive. Reduced to single-agent + priority-ordered preferred_models at the substrate.
- Pre-declared agent hierarchy. Single primary agent; sub-agents are runtime-spawned ephemera.
- Cross-deployment forking semantics. Code distribution is a git concern; data sharing is human-mediated via standard schema_proposal export/import.
- Mobile. Desktop only.
- Paid tier. Free during the pilot.
- Push notifications and alerts.
- Vendor-specific deep integrations beyond the six core data sources listed (vendor posts, LMArena, LiveBench, HN, YouTube, my own captures).

## What success looks like

For me, personally:

- I stop guessing when I pick a model for a task. I look at the model's page, see the latest claims with provenance, and pick deliberately.
- When I am surprised by a model's behavior, I capture the observation in 30 seconds and it shows up in future queries.
- Two months from now I can answer "what did I think about Gemini 3 in April?" without trying to remember.

For the wider goal:

- 10 to 15 friends use it weekly within 30 days of the friends launch.
- 500+ GitHub stars on the reference implementation within 30 days of public drop.
- Two or more builders write follow-up posts critiquing or extending the three-primitive spec within 90 days.
- TurnoCockpit pilot demonstrably catches a real production conflict using one of the same primitives.
- The launch piece's "It works precedes it works cost-effectively" framing surfaces in at least one other builder's writing within 60 days (sign that the framing is genuinely portable, not just my private slogan).

## What this is NOT

- Not a SaaS product. Not a startup. Not a fundraise vehicle.
- Not a generic note-taking app. It is specifically for capturing and reasoning over claims about AI models.
- Not a benchmark site. It aggregates and contextualizes claims, it does not run benchmarks.
- Not a permanent commitment to maintain forever. If the tool stops being useful to me personally, the project ends honestly.
