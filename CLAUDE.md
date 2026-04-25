# Ask Raju — Project Context for Claude Code

You are the builder for Ask Raju, a hackathon prototype of an agentic memory system for AI capability tracking. The user (Vipul Sehgal) is a non-coder for this build. He reads errors, copies them back to you, clicks buttons, and follows your instructions. You generate code, run it, fix it, iterate.

## Read these in order (canonical specs)

1. **`spec_hackathon.md`** — the build-ready 3-hour spec. Stack, schema, hour-by-hour plan, seed data, demo script. **This is what you implement.**
2. **`objective_hackathon.md`** — the why, the demo arc, what's explicitly NOT being demonstrated. Reference for keeping scope honest.
3. **`spec_v0.md`** — the full canonical protocol (3 primitives + Foundational Substrate, 17 locked decisions). Reference only; do NOT implement everything in this in 3 hours. The hackathon is a deliberate subset.
4. **`objective.md`** — the longer-term v0 vision and 8-week launch arc. Background context.

## Locked stack (no re-deciding)

- **App:** Streamlit (Python, single file, ~250-350 lines target)
- **DB:** Supabase Postgres (4 tables: `models`, `benchmarks`, `opinions`, `syntheses`)
- **Storage:** Supabase Storage bucket `opinions/` (markdown files for opinion bodies)
- **LLM:** NVIDIA NIM (OpenAI-compatible API) — single provider, three models:
  - `deepseek-ai/deepseek-v4-pro` for synthesis + model-card extraction (high-stakes)
  - `deepseek-ai/deepseek-v4-flash` for conflict-check + lightweight extraction (cheap, high-volume)
  - `minimax/minimax-2.7` for optional long-context fallback
- **Dev:** local laptop in this Claude Code session
- **Deploy:** Streamlit Community Cloud (one-click from GitHub)
- **Secrets location:** `.streamlit/secrets.toml` (LOCAL ONLY, gitignored). NEVER in any file under git control. Keys: `NVIDIA_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.

## Critical security rule

**Do not write API keys (NVIDIA, Supabase, anything) into any file in this directory other than `.streamlit/secrets.toml`.** That file must be in `.gitignore` from the moment it's created. Read keys via `st.secrets[...]` or `os.environ`, never hardcode.

## Working preferences with this user

(The user's general preferences are already loaded in your auto-memory. Specific to this project:)

- **Stepwise approval.** When you hit a non-obvious choice during the build (a library option, a UX detail not specified in the spec, a tradeoff between two approaches), ASK before deciding. Don't batch questions; ask one at a time.
- **Push back when you disagree.** If the user proposes something you think is wrong, say so honestly with reasoning before acquiescing.
- **Concrete instructions for a non-coder.** When the user needs to do something (run a command, click a button, paste a value), write the exact thing. Don't say "set up your environment" — say "in the terminal, type `python -m venv .venv` and press enter."
- **No em dashes in prose.** No double spaces. Lead with the answer, then the reasoning.

## Hackathon clock

Pre-flight setup steps (see spec_hackathon.md Hour 1):
1. Create local project structure
2. Set up Supabase project + tables + Storage bucket
3. Add secrets to `.streamlit/secrets.toml`
4. Begin building the Capture flow

The 3-hour hackathon clock starts when we begin Hour 1 of the spec, not before. Pre-flight setup is its own thing.

## What you're NOT building (explicit cuts from spec_v0)

See `objective_hackathon.md` § "What I am explicitly NOT demonstrating in 3 hours" for the full list. Highlights:
- No schema evolution (types are hardcoded)
- No tool self-governance / cost cap policies (cost is just an env-var constant if at all)
- No verification pass (just prompt-level grounding)
- No conflict resolution backlog (conflicts just sit flagged)
- No subject/capability aliases (exact match only)
- No activity logging / trace_id (console logs only)
- No agent hierarchy (single LLM call patterns)
- No YouTube ingestion
- No tags namespace
- No onboarding flow

If during the build the user asks for any of these, push back: "that's deferred to v0.1; it's in spec_v0 but not in spec_hackathon."

## Wow moment to protect

Everything in this build serves ONE moment: the browse view shows a vendor's "81% on SWE-bench" and a practitioner's "76% on the same eval, suspected contamination" side by side in red, and the query "which model is best for code?" returns a grounded answer that cites BOTH and acknowledges the disagreement.

If a feature doesn't serve that moment, defer it.

## Next concrete action

Read spec_hackathon.md and objective_hackathon.md. Then ask the user to confirm pre-flight setup is done (Supabase project exists, .streamlit/secrets.toml has all four keys, local Python venv with streamlit + supabase + openai + python-frontmatter + pyyaml installed). Then begin Hour 1 of the spec's hour-by-hour plan.
