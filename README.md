# Ask Raju

> Your AI-model knowledge memory. Grounded by default.

A Streamlit app that captures vendor claims, practitioner pushback, and benchmark contradictions about AI models — then synthesizes grounded answers with citations. No speculation, no smoothed-over disagreements.

Built as a hackathon prototype demonstrating four primitives for agentic memory: typed memory with conflict-flagging, tool self-governance, friction-gated schema evolution, and a foundational substrate that unifies world-knowledge with self-observation.

## What it does

- **Capture** — Paste a vendor model card. DeepSeek V4 Flash extracts model metadata, every benchmark mentioned, and the vendor's framing. One paste populates the `models`, `benchmarks`, and `opinions` tables, plus uploads an opinion markdown file to Supabase Storage.
- **Browse** — Per-model profile with metadata, benchmarks grouped by name with vendor-vs-practitioner conflicts paired in red, and opinions rendered from Storage.
- **Query** — Natural-language question → grounded synthesis with inline `[r:ID]` citation chips. Live-streamed. Confidence badge. Supports four pre-loaded demo questions one click away.

## Stack

- **App:** Streamlit 1.56 (Python 3.13)
- **Database:** Supabase Postgres (4 tables: models, benchmarks, opinions, syntheses)
- **Storage:** Supabase Storage bucket `opinions/` for markdown opinion files
- **LLM:** DeepSeek V4 Flash via NVIDIA NIM (OpenAI-compatible API)
- **Charts:** Altair (price-vs-intelligence frontier + intelligence ranking)

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (see "Push to GitHub" below).
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **New app** → pick this repo, branch `main`, main file `app.py`.
4. Click **Advanced settings** → paste your secrets in TOML format:
   ```toml
   NVIDIA_API_KEY = "nvapi-..."
   SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
   SUPABASE_KEY = "eyJ..."
   SUPABASE_SERVICE_ROLE_KEY = "eyJ..."
   ```
5. Click **Deploy**. ~3 min build. You get a stable `*.streamlit.app` URL.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .streamlit/secrets.toml from template and fill in real values
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# edit .streamlit/secrets.toml with your real keys

streamlit run app.py
```

## Database setup

Create a fresh Supabase project. Run the SQL in `spec_hackathon.md` (or extract from `seed.py`) to create `models`, `benchmarks`, `opinions`, `syntheses` tables. Create a public Storage bucket named `opinions`.

To populate demo data:
```bash
.venv/bin/python seed.py
```

This loads 8 models, 50 benchmarks (with 3 deliberate vendor-vs-practitioner conflicts), and 8 opinion markdown files into Supabase.

## Project structure

- `app.py` — single-file Streamlit app (~1700 lines)
- `seed.py` — demo data loader (idempotent)
- `requirements.txt` — Python dependencies
- `.streamlit/secrets.toml.template` — fill in and copy to `secrets.toml`
- `spec_hackathon.md` — full hackathon build spec
- `spec_v0.md` — full canonical protocol (3 primitives + substrate)
- `objective_hackathon.md` — why-this-build, demo arc, success criteria
- `objective.md` — longer-term v0 vision and 8-week launch arc
- `CLAUDE.md` — project context for Claude Code

## License

MIT.
