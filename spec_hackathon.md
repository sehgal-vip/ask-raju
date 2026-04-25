# Spec — Ask Raju Hackathon Build (3 hours)

**Status:** Build-ready
**Author:** Vipul Sehgal
**Date:** 2026-04-25
**Time budget:** 3 hours
**Builder:** Claude Code (Vipul debugs)
**Companion documents:** `objective.md`, `spec_v0.md` (full protocol — this hackathon spec is the demo subset)

---

## Goal

A working prototype that demos the **wow moment**: capture three claims about an AI model, two of them contradict each other, the system flags the contradiction visually, and a query gets a grounded answer that cites sources and acknowledges the dissent.

Everything else is decoration. If the demo flow above works, the hackathon is won. If not, nothing else matters.

---

## Stack (locked)

| Layer | Choice | Why |
|---|---|---|
| **UI / app** | Streamlit | Fastest Python UI for LLM apps. ~200 lines of code total. Smallest surface for Claude to break. |
| **Database** | Supabase Postgres + Storage | Restart-safe (data survives deploys), demo-visible (Studio + bucket browser open in tabs during demo), free tier sufficient. |
| **All LLM calls** | NVIDIA NIM (OpenAI-compatible API) | Single-provider for v0-hackathon simplicity. Different models for different tasks (see split below). Wire up once with `from openai import OpenAI` + `base_url="https://integrate.api.nvidia.com/v1"`. |
| **Dev environment** | Local (Cursor + Claude integration) | Builder has Cursor + Claude + Node working locally. Faster iteration than Replit (real terminal, hot reload, instant file edits, better DevTools). Python venv setup is a 2-minute step. |
| **Deploy** | Streamlit Community Cloud | Stable URL, free, one-click deploy from GitHub repo. |
| **Repo** | GitHub public | For Streamlit Cloud to pull from. Replit can push directly to GitHub. |
| **Secrets** | `.streamlit/secrets.toml` (local, gitignored) → Streamlit Cloud Secrets (deploy) | `NVIDIA_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`. NEVER hardcoded; always read from `st.secrets[...]` or `os.environ`. |

### Model split within NVIDIA NIM

Three open-weight models, one client, different model-id strings per task:

| Task | NIM model id | Why this model |
|---|---|---|
| Synthesis (final grounded answer) | `deepseek-ai/deepseek-v4-pro` | Most capable; supports reasoning mode for careful grounding |
| Model-card extraction (structured fields from vendor posts) | `deepseek-ai/deepseek-v4-pro` | Structured extraction benefits from reasoning |
| Conflict-check (yes/no comparison between two records) | `deepseek-ai/deepseek-v4-flash` | Cheap, fast; reasoning_effort omitted for this task |
| Opinion claim-extraction (lightweight metadata pull) | `deepseek-ai/deepseek-v4-flash` | Cheap, low-stakes |
| Long-context summarization (only if an opinion file is too long for normal context) | `minimax/minimax-2.7` | 4M context window; only invoked if needed |

The demo line: "Ask Raju routes work to the right open-weight model for each task. The synthesis runs on DeepSeek V4 Pro because it's high-stakes; the conflict-check runs on V4 Flash because it's cheap and high-volume; long context falls back to MiniMax 2.7 when needed. All open-source, all via NVIDIA NIM."

**Workflow assumption:** the builder (Vipul) doesn't write code but can read error messages, copy them, click buttons, and follow Claude's instructions. Claude Code generates and iterates the code in Replit's terminal; Vipul confirms behavior and pastes any error messages Claude doesn't see directly back to it.

**Tradeoff I made: Sonnet vs Haiku for the model.** Sonnet 4.6 for capture extraction and synthesis; Haiku for the conflict-check call (cheaper, fast enough). Both via Anthropic API. Flag if you want everything on Sonnet for simplicity.

---

## What's IN (the demo subset)

### Three surfaces

1. **Capture**: three flavors driven by what you paste:
   - **Model card** (vendor launch post): LLM extracts model metadata + N benchmarks + a vendor opinion. One paste populates rows in 3 tables.
   - **Independent benchmark** (leaderboard snapshot, eval re-run): LLM extracts model + benchmark + score + claimant. Goes only into `benchmarks`. Conflict-check against existing benchmark rows for same model+benchmark.
   - **Opinion** (HN thread, blog post, your own observation, tweet): LLM extracts model + capability + claimant. Body stored as a markdown file in Supabase Storage with a metadata row in `opinions`.
2. **Browse**: dropdown to pick a model → model profile (metadata + benchmarks table + list of opinions rendered as markdown). Conflicting benchmarks visually paired in red. Conflicting opinions surfaced with "this disagrees with..." note.
3. **Query**: natural-language input → retrieve matching records across `benchmarks` and `opinions` for the relevant model+capability → LLM synthesizes grounded answer with inline `[r:id]` citations → save synthesis as a row in `syntheses`.

### Three storage layers, three epistemic types

- **`models` table:** structured model metadata (vendor, release date, context window, parameter count, pricing, open-source flag)
- **`benchmarks` table:** structured numeric claims with provenance. Multiple sources per benchmark allowed (vendor's claim AND practitioner re-run can both be stored, with conflict_link between them).
- **`opinions` table + Supabase Storage bucket:** metadata row in `opinions` table; markdown body lives as an actual file in Storage. Files are organized as `opinions/{model_name}/{date}-{slug}.md` with frontmatter mirroring the metadata row (self-describing if extracted).
- **`syntheses` table:** generated answers with structured citations and confidence. Stored so you can revisit "what did Raju say last week."

### Conflict detection

Two separate primitives, one per structured table:

- **Benchmark conflict:** on capture, query existing `benchmarks` rows for same model+benchmark+source_type combination. If a vendor claim and an independent eval disagree on score (e.g., 81% vs 76%), the LLM (Haiku, cheap) confirms it's a substantive disagreement and sets `conflict_link` on both rows.
- **Opinion conflict:** same pattern for `opinions` rows that disagree on the same model+capability dimension.

Cross-table conflicts (e.g., vendor benchmark says X, practitioner opinion says "actually Y") are interesting but skipped for v0-hackathon to keep complexity bounded.

### Browse view per model

A model's profile page shows three sections:
- **Metadata** (rendered from `models` row): vendor, release date, context window, parameter count, pricing
- **Benchmarks** (rendered from `benchmarks` rows): table grouped by benchmark name, with conflicts visually paired in red
- **Opinions** (rendered from `opinions` rows + their markdown files): list of long-form opinions, rendered as proper markdown, with claimant + date + source link visible

### Query / synthesis

Natural-language question → LLM extracts target model + capability from query → retrieve relevant `benchmarks` and `opinions` rows → fetch any opinion files needed for context → send to LLM with grounding contract prompt: "Answer using ONLY these records. Cite each by its `id` like `[r:abc123]`. If the records don't support an answer, say 'I don't have data on this.'" → render answer with inline citation chips → save as `syntheses` row.

---

## What's OUT (with explicit deferred-from-spec notes)

These are all in `spec_v0.md` but skipped for the 3-hour build. Each note tells future-Vipul (or a v0.1 build) what to add.

| Cut | Reason | Deferred to |
|---|---|---|
| Schema evolution / interactive onboarding (Primitive 3 entirely) | 24-hour cooldowns and case-law analysis don't fit a 3-hour build | v0.1 |
| Tool self-governance / cost cap / rate limit / runtime override (Primitive 2 entirely) | Hardcode a single `max_calls_per_query=20` constant for safety; no policy records | v0.1 |
| Verification pass on synthesis output | LLM is instructed to ground in records via prompt; no separate verification call | v0.1 |
| Conflict resolution backlog with rationale-required acceptance | Conflicts just sit flagged; user can't resolve them in v0-hackathon | v0.1 |
| Subject/capability LLM-suggested aliases (Decision 1.2 hybrid) | Exact-match only on normalized strings | v0.1 |
| Activity logging / trace_id / human debug lens | Console logs only | v0.2 |
| `preferred_models` priority lists | Hardcoded model assignments per call type | v0.1 |
| Sub-agent spawning (`spawn_subagent`) | Single-call LLM invocations only | v0.1 |
| YouTube ingestion (parent-child extraction) | Just paste box, single record per paste | v0.1 |
| Tags namespace structure | Single flat `tags` list (or skip tags entirely) | v0.1 |
| Metadata header on synthesis output (confidence + verification removal count) | Simple "Confidence: X" line at top | v0.1 |
| Per-type `temporal_semantics` | All types behave as `recency_wins` implicitly | v0.1 |
| User auth | Single shared workspace, no login | v0.2 |
| Override mechanism / elevation offer | No override flow; cost cap is just a hard call counter | v0.1 |

---

## Data model (Supabase Postgres + Supabase Storage)

Four tables in Postgres + one Storage bucket for opinion files.

### Postgres tables

```sql
CREATE TABLE models (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL UNIQUE,         -- normalized id: 'opus-4.7', 'deepseek-v4-pro'
  display_name    text NOT NULL,                -- 'Claude Opus 4.7'
  vendor          text NOT NULL,                -- 'Anthropic', 'DeepSeek', 'MiniMax', 'Alibaba/Qwen', 'OpenAI', 'Google'
  family          text,                         -- 'Claude', 'DeepSeek-V', 'MiniMax', 'Qwen', 'GPT', 'Gemini'
  released_at     date,
  context_window  integer,                      -- tokens, e.g., 1000000
  parameter_count text,                         -- '~1.5T MoE', '671B (37B active)', '28B', etc.
  is_open_source  boolean DEFAULT false,
  pricing_input   numeric,                      -- $/1M input tokens (null for fully open / local)
  pricing_output  numeric,
  source_url      text,                         -- the model card we extracted this from
  notes           text,
  created_at      timestamptz DEFAULT now()
);

CREATE TABLE benchmarks (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id        uuid REFERENCES models(id) NOT NULL,
  benchmark_name  text NOT NULL,                -- 'swe-bench-verified', 'mmlu-pro', 'humaneval', 'codeforces-elo'
  score           numeric,                      -- 81, 92.5, etc.
  unit            text DEFAULT '%',             -- '%', 'elo', 'tokens/sec'
  methodology     text,                         -- subset, conditions, caveats
  source_type     text NOT NULL,                -- 'vendor_official' | 'leaderboard' | 'practitioner' | 'independent_eval'
  source_url      text,
  claimant        text,                         -- 'Anthropic launch post', 'LMArena', 'HN @kapil_v'
  effective_at    timestamptz DEFAULT now(),
  conflict_link   uuid REFERENCES benchmarks(id),
  created_at      timestamptz DEFAULT now()
);

CREATE TABLE opinions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id        uuid REFERENCES models(id),  -- nullable: cross-model opinions allowed
  capability      text,                         -- optional dimension this opinion is about
  storage_path    text NOT NULL,                -- e.g., 'opinions/opus-4.7/2026-04-22-vipul-postgres-failure.md'
  claimant        text NOT NULL,                -- 'Vipul', 'r/LocalLLaMA thread', 'Simon Willison'
  source_type     text NOT NULL,                -- 'vendor_official' | 'practitioner' | 'personal_usage'
  source_url      text,
  effective_at    timestamptz DEFAULT now(),
  conflict_link   uuid REFERENCES opinions(id),
  created_at      timestamptz DEFAULT now()
);

CREATE TABLE syntheses (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  query           text NOT NULL,
  answer_md       text NOT NULL,                -- markdown body with [r:id] inline citations
  citations_json  jsonb,                        -- structured cites: [{record_type, record_id, ...}]
  confidence      numeric,
  created_at      timestamptz DEFAULT now()
);

CREATE INDEX ON benchmarks (model_id, benchmark_name);
CREATE INDEX ON opinions (model_id);
CREATE INDEX ON opinions (claimant);
```

### Supabase Storage bucket

Bucket name: `opinions` (public read for v0-hackathon; tighten in v0.1)

File structure:
```
opinions/
  opus-4.7/
    2026-04-15-anthropic-launch-vendor-framing.md
    2026-04-18-hn-thread-discussion.md
    2026-04-22-vipul-postgres-failure.md
  deepseek-v4-pro/
    2026-04-10-release-day-impressions.md
    2026-04-12-vipul-coding-test.md
  ...
```

Each opinion file has YAML frontmatter mirroring the metadata row (self-describing if extracted from the bucket):

```markdown
---
model: opus-4.7
capability: code-refactoring
claimant: Vipul
source_type: personal_usage
date: 2026-04-22
---

Failed twice today on a Postgres migration that Sonnet got right on the first try.
Both attempts produced syntactically valid SQL but used PG13-style quoted identifiers
instead of PG16's standard. Sonnet 4.6 understood the version constraint immediately.
Bumping back to Sonnet for migration work.
```

### Notes on the schema

- **No `tags` field anywhere.** Capability is a structured column on benchmarks and opinions; richer tagging deferred to v0.1.
- **`conflict_link` is single-direction within each table.** Each row knows ONE thing it conflicts with (sufficient for the demo). Many-to-many deferred.
- **No cross-table conflict (benchmark vs opinion).** Same-table conflict only. Cross-table is a v0.1 feature.
- **Synthesis records are their own table** (not the same as benchmarks/opinions). They reference benchmarks and opinions in `citations_json`.

---

## Hour-by-hour plan

### Hour 1 (0:00 → 1:00) — Scaffold

- Create local project folder `ask-raju`, open in Cursor, set up Python venv, `pip install streamlit supabase openai python-frontmatter pyyaml` (4 min)
- Set up Supabase project, create the four tables via Studio's SQL editor (paste schema from this doc) + create `opinions` Storage bucket with public read (12 min)
- Create `.streamlit/secrets.toml` with NVIDIA + Supabase keys (3 min)
- Open Cursor's Claude integration, paste both `spec_hackathon.md` and `objective_hackathon.md` into context, tell Claude to scaffold three Streamlit pages and wire up Supabase + Storage + NVIDIA NIM client (single OpenAI client with NIM base_url) (10 min generation + watch)
- Build the Model Card capture flow: paste box → LLM extracts model metadata + benchmarks + vendor opinion → write rows to `models`, `benchmarks`, `opinions` + upload opinion file to Storage (25 min)
- Test end-to-end with the Anthropic Opus 4.7 launch post: one paste populates 1 model row + N benchmark rows + 1 opinion file (6 min)

**End of hour 1:** running `streamlit run app.py` locally, can paste a model card and see all three tables populate plus the markdown file appear in Supabase Storage.

### Hour 2 (1:00 → 2:00) — Conflict detection + Browse

- Add benchmark conflict-check call after capture: fetch existing `benchmarks` rows for same model+benchmark, ask LLM to compare scores, set `conflict_link` if they disagree (15 min)
- Add opinion conflict-check call: same pattern for `opinions` rows on same model+capability (10 min)
- Build Browse page: dropdown of models → model profile with three sections (metadata table, benchmarks table grouped by name, opinions list rendered from Storage) (20 min)
- Add visual conflict pairing on benchmarks (red highlight, side-by-side display when `conflict_link` is set) (10 min)
- Test: capture two benchmarks that should conflict, verify the conflict is flagged in Browse (5 min)

**End of hour 2:** browse view shows full model profiles with rendered opinion files; conflict-flagging fires.

### Hour 3 (2:00 → 3:00) — Query + polish + demo prep

- Build Query page: text input → extract subject/capability from query → retrieve matching records → LLM synthesis with grounded answer + citations (25 min)
- Inline citation rendering: parse `[r:id]` markers in answer, render as chips (10 min)
- Load seed data via Supabase Studio CSV import or seed script run from local (10 min — see Seed data section below)
- Polish: title, brief intro text, "Ask Raju" branding, clean up Capture page to look presentable (5 min)
- Push from local to GitHub (`git init`, `git add`, `git commit`, `git push`), then deploy to Streamlit Community Cloud by connecting the repo and adding the same secrets in Streamlit Cloud's UI (10 min)

**End of hour 3:** working demo on a public Streamlit Cloud URL with seed data and live capture/query, plus Supabase Studio open in another tab as the "see the data" backdrop.

---

## Seed data

Three layers, loaded once at deploy time via a Python seed script (Claude generates this).

### Models seed (~7 rows)

| name | display_name | vendor | family | released_at | context_window | parameter_count | is_open_source | pricing_input | pricing_output |
|---|---|---|---|---|---|---|---|---|---|
| opus-4.7 | Claude Opus 4.7 | Anthropic | Claude | 2026-04-15 | 1000000 | undisclosed | false | 15 | 75 |
| sonnet-4.6 | Claude Sonnet 4.6 | Anthropic | Claude | 2026-02-20 | 1000000 | undisclosed | false | 3 | 15 |
| gpt-6 | GPT-6 | OpenAI | GPT | 2026-03-10 | 256000 | undisclosed | false | 12 | 60 |
| gemini-3-pro | Gemini 3 Pro | Google | Gemini | 2026-03-25 | 2000000 | undisclosed | false | 7 | 35 |
| deepseek-v4-pro | DeepSeek V4 Pro | DeepSeek | DeepSeek-V | 2026-03-30 | 256000 | 671B (37B active) | true | 0.5 | 2 |
| minimax-2.7 | MiniMax 2.7 | MiniMax | MiniMax | 2026-04-05 | 4000000 | 456B MoE | true | 0.4 | 1.6 |
| qwen-3-28b | Qwen 3 28B | Alibaba/Qwen | Qwen | 2026-01-15 | 128000 | 28B | true | null | null |

### Benchmarks seed (~14 rows, with 3 deliberate contradictions)

| model | benchmark_name | score | unit | source_type | claimant |
|---|---|---|---|---|---|
| opus-4.7 | swe-bench-verified | 81 | % | vendor_official | Anthropic launch post |
| **opus-4.7** | **swe-bench-verified** | **76** | **%** | **independent_eval** | **HN re-run by @kapil_v** ⚠️ conflict with above |
| opus-4.7 | mmlu-pro | 87 | % | vendor_official | Anthropic launch post |
| sonnet-4.6 | swe-bench-verified | 75 | % | vendor_official | Anthropic capabilities post |
| sonnet-4.6 | humaneval | 91 | % | vendor_official | Anthropic capabilities post |
| gpt-6 | mmlu-pro-tools | 79 | % | vendor_official | OpenAI release notes |
| gpt-6 | swe-bench-verified | 78 | % | vendor_official | OpenAI release notes |
| gemini-3-pro | needle-in-haystack-1m | 99.5 | % | vendor_official | Google launch post |
| **gemini-3-pro** | **needle-in-haystack-1m** | **89** | **%** | **independent_eval** | **Stanford long-context eval** ⚠️ conflict |
| deepseek-v4-pro | humaneval | 92 | % | vendor_official | DeepSeek release notes |
| deepseek-v4-pro | codeforces-elo | 2150 | elo | vendor_official | DeepSeek release notes |
| minimax-2.7 | needle-in-haystack-4m | 99.5 | % | vendor_official | MiniMax launch post |
| **minimax-2.7** | **needle-in-haystack-4m** | **84** | **%** | **practitioner** | **Independent benchmark, recall degraded after 1.5M** ⚠️ conflict |
| qwen-3-28b | mmlu-pro | 78 | % | vendor_official | Qwen tech report |

Three contradictions in this set: Opus on SWE-bench (vendor 81% vs practitioner re-run 76%), Gemini on long-context (vendor 99.5% vs Stanford 89%), MiniMax on 4M context recall (vendor 99.5% vs independent 84%). All three are vendor-vs-practitioner disagreements that visually pair in the Browse view.

### Opinions seed (~10 markdown files in Supabase Storage)

```
opinions/
  opus-4.7/
    2026-04-15-anthropic-launch-vendor-framing.md       (vendor)
    2026-04-18-hn-thread-discussion.md                   (practitioner)
    2026-04-22-vipul-postgres-failure.md                 (personal_usage)
  sonnet-4.6/
    2026-02-20-anthropic-launch.md                       (vendor)
    2026-04-10-vipul-extraction-tasks.md                 (personal_usage)
  gemini-3-pro/
    2026-03-25-google-launch-context-claims.md           (vendor)
    2026-04-08-stanford-eval-pushback.md                 (practitioner)
  deepseek-v4-pro/
    2026-03-30-release-day-impressions.md                (practitioner)
    2026-04-12-vipul-coding-test.md                      (personal_usage)
  minimax-2.7/
    2026-04-05-minimax-launch-post.md                    (vendor)
```

Each file is 100-300 words of substantive markdown with frontmatter (model, capability, claimant, source_type, date) and a body that captures real-feeling content (not lorem ipsum). Two of them — `opus-4.7/2026-04-22-vipul-postgres-failure.md` and `deepseek-v4-pro/2026-04-12-vipul-coding-test.md` — are personal observations from Vipul to ground the demo in real usage.

### Why this seed works for the demo

- **7 models** including both closed (Anthropic, OpenAI, Google) and open-source (DeepSeek, MiniMax, Qwen). Reflects the actual landscape.
- **14 benchmark rows with 3 deliberate vendor-vs-practitioner conflicts.** Three opportunities to demo the conflict-flagging primitive in the browse view.
- **10 opinion files including 2 personal observations from Vipul.** The personal ones make it feel like a real working tool, not a demo, and showcase the markdown rendering capability.
- **Total seed effort: ~15 minutes** if Claude generates the seed script + populates from prepared data dumps you give it.

---

## Demo script (3-minute pitch)

**0:00 — Hook (15 sec).** "Every week a new AI model drops with claims that contradict last week's claims. I forget the nuance. So I built Ask Raju — it captures every claim about every model, with provenance, and surfaces contradictions so I never forget the disagreements."

**0:15 — Browse (45 sec).** Open Browse page → select Opus 4.7 → scroll to swe-bench. Point at the visually-paired contradiction: "Anthropic says 81%, this practitioner says 76% with suspected contamination. Ask Raju doesn't smooth this away. It shows me both."

**1:00 — Capture live (45 sec).** Open Capture page → paste a fresh claim about Opus on a NEW capability (something not in seed data). Show the LLM extracting structured fields, the record appearing in Supabase Studio side-by-side. "I just captured a new claim. The system extracted the model, the capability, and the source. If this had contradicted an existing record, it would've been flagged automatically."

**1:45 — Query with grounding (1 min).** Ask "Which model is best for code refactoring?" → show the grounded answer with inline `[r:id]` chips → click a chip to show the source record → point out the dissent acknowledgment. "Every claim in the answer cites a specific record. The answer doesn't make things up. When the data is missing, it says so."

**2:45 — Close (15 sec).** "Three primitives: conflict-flagging memory, grounded synthesis, and (in the full spec) friction-gated schema evolution. Three hours of build, but the same primitives drive a production system in TurnoCockpit."

---

## Decisions locked so far

Most major architecture is now locked:

- ✓ Stack: Streamlit + Supabase (Postgres + Storage) + Anthropic API + Replit dev env + Streamlit Community Cloud deploy
- ✓ Four-table schema: `models`, `benchmarks`, `opinions`, `syntheses`
- ✓ Opinions as actual markdown files in Supabase Storage with metadata rows
- ✓ Three capture flows: model card, independent benchmark, opinion
- ✓ Same-table conflict only (no cross-table); single-direction conflict_link
- ✓ No tags field; capability lives as a structured column
- ✓ Sonnet for synthesis + extraction; Haiku for cheap conflict-check calls
- ✓ Seed: 7 models + 14 benchmarks (with 3 deliberate conflicts) + 10 opinion files

## Still open (the NVIDIA API question)

The remaining tradeoff to decide before Claude starts: **do we use NVIDIA API for some of the model calls (DeepSeek V4 Flash/Pro, MiniMax 2.7), or stay all-Anthropic?**

This is the next conversation. Two readings:
- **Demo angle:** showing the system using a mix of cloud (Anthropic) and NVIDIA-hosted open-source models would be a richer story than "all Anthropic."
- **Time angle:** integrating a second LLM provider in a 3-hour hackathon adds setup time and failure modes.

We'll discuss this separately.
