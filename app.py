"""Ask Raju — Hour 1 build: scaffold + Model Card capture flow.

Three Streamlit pages (Capture, Browse, Query). Hour 1 implements:
- Clients for NVIDIA NIM, Supabase Postgres, Supabase Storage
- Model Card capture: paste vendor launch post → LLM extracts model + benchmarks + opinion
  → writes to models/benchmarks/opinions tables + uploads opinion .md to Storage

Browse and Query are stubbed for Hour 2 and Hour 3.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

import streamlit as st
from markdown_it import MarkdownIt
from openai import OpenAI
from supabase import Client, create_client

_MD = MarkdownIt("commonmark", {"breaks": True, "html": False})

# ---------- Page config ----------
st.set_page_config(page_title="Ask Raju", page_icon="◆", layout="wide")


# ---------- Global CSS injection (font, chrome hide, brand classes) ----------
def inject_global_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

        /* Hide Streamlit chrome */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header[data-testid="stHeader"] { background: transparent; height: 0; }
        .stDeployButton { display: none; }
        div[data-testid="stToolbar"] { display: none; }
        /* Hide sidebar entirely — using horizontal nav in brand bar */
        section[data-testid="stSidebar"] { display: none !important; }
        button[kind="header"] { display: none !important; }

        /* Tight container, generous max-width for chat-style hero */
        .block-container {
          padding-top: 0 !important;
          padding-bottom: 3rem;
          max-width: 1080px;
        }

        /* Typography */
        html, body, [class*="css"], .stMarkdown, .stText, .stTextInput input, .stTextArea textarea {
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        code, pre, .stCode { font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace !important; }

        h1 { font-size: 2.8em; font-weight: 800; letter-spacing: -0.028em; line-height: 1.05; margin: 0 0 12px 0; }
        h2 { font-size: 1.7em; font-weight: 700; letter-spacing: -0.02em; line-height: 1.15; margin: 0 0 10px 0; }
        h3 { font-size: 1.2em; font-weight: 700; letter-spacing: -0.012em; margin: 0 0 8px 0; }

        /* Body text */
        p, .stMarkdown p { font-size: 1em; line-height: 1.65; }

        /* Tighter Streamlit element spacing */
        .stMarkdown, [data-testid="stVerticalBlock"] > div { gap: 0.5rem; }
        [data-testid="stVerticalBlock"] { gap: 0.6rem; }
        [data-testid="stHorizontalBlock"] { gap: 0.5rem; }
        .element-container { margin-bottom: 0.4rem !important; }

        /* Primary button — accent blue */
        .stButton > button[kind="primary"] {
          background: #2563eb; border-color: #2563eb; color: white;
          font-weight: 600; border-radius: 10px;
          transition: transform 0.06s ease, background 0.15s ease;
        }
        .stButton > button[kind="primary"]:hover {
          background: #1d4ed8; border-color: #1d4ed8; transform: translateY(-1px);
        }
        .stButton > button[kind="primary"]:active { transform: translateY(0); }

        /* Secondary buttons (suggestion chips) */
        .stButton > button[kind="secondary"] {
          background: rgba(127,127,127,0.06);
          border: 1px solid rgba(127,127,127,0.18);
          font-size: 0.88em; font-weight: 500;
          border-radius: 999px; padding: 6px 14px; min-height: 32px;
        }
        .stButton > button[kind="secondary"]:hover {
          background: rgba(37,99,235,0.08); border-color: rgba(37,99,235,0.4); color: #2563eb;
        }

        /* Big text input on hero */
        .stTextInput input {
          font-size: 1.15em !important; padding: 14px 18px !important;
          border-radius: 14px !important; border: 1px solid rgba(127,127,127,0.25) !important;
          background: rgba(127,127,127,0.03) !important;
        }
        .stTextInput input:focus {
          border-color: #2563eb !important;
          box-shadow: 0 0 0 3px rgba(37,99,235,0.15) !important;
          background: white !important;
        }

        /* ------- Brand bar (slim, horizontal nav inside) ------- */
        .raju-brandbar {
          display: flex; justify-content: space-between; align-items: center;
          padding: 12px 22px; margin: 0 0 28px 0;
          background: #0f172a;
          color: #e2e8f0;
          border-radius: 0 0 14px 14px;
          font-family: 'Inter', sans-serif;
          gap: 16px; flex-wrap: wrap;
        }
        .raju-brand-row { display: flex; align-items: baseline; gap: 12px; flex-shrink: 0; }
        .raju-logo { color: #38bdf8; font-size: 1.45em; line-height: 1; }
        .raju-logo--pulsing { animation: raju-pulse 1.4s ease-in-out infinite; }
        @keyframes raju-pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }
        .raju-wordmark { font-weight: 800; font-size: 1.15em; letter-spacing: -0.02em; color: #f8fafc; }
        .raju-stats {
          display: flex; gap: 12px; font-size: 0.85em; color: #cbd5e1;
          margin-left: auto; align-items: center; flex-wrap: wrap;
        }
        .raju-stats b { color: #f8fafc; font-weight: 700; }
        .raju-dot { opacity: 0.35; }
        .raju-conflict b { color: #fb7185; }

        /* ------- Hero ------- */
        .raju-hero {
          text-align: center; padding: 36px 16px 24px 16px; max-width: 760px;
          margin: 0 auto;
        }
        .raju-hero .raju-eyebrow {
          font-size: 0.78em; opacity: 0.55; text-transform: uppercase;
          letter-spacing: 0.12em; margin-bottom: 14px; font-weight: 600;
        }
        .raju-hero h1 {
          font-size: 3em; font-weight: 800; letter-spacing: -0.03em;
          line-height: 1.05; margin: 0 0 14px 0;
        }
        .raju-hero p {
          font-size: 1.1em; opacity: 0.7; max-width: 600px; margin: 0 auto;
          line-height: 1.55;
        }

        /* Page-level secondary hero (Browse/Capture pages) */
        .raju-page-hero { padding: 4px 0 20px 0; }
        .raju-page-hero h2 { font-size: 1.7em; }
        .raju-page-hero p { opacity: 0.7; margin: 4px 0 0 0; font-size: 1em; }

        /* ------- Chat bubble (Raju's response area) ------- */
        .raju-bubble {
          background: rgba(127,127,127,0.04);
          border: 1px solid rgba(127,127,127,0.15);
          border-radius: 16px;
          padding: 22px 26px;
          margin: 18px 0;
          font-size: 1.02em;
          line-height: 1.7;
        }
        .raju-bubble-header {
          display: flex; align-items: center; gap: 10px;
          margin-bottom: 14px; padding-bottom: 12px;
          border-bottom: 1px solid rgba(127,127,127,0.12);
        }
        .raju-bubble-avatar {
          width: 28px; height: 28px; border-radius: 50%;
          background: #2563eb; color: white;
          display: inline-flex; align-items: center; justify-content: center;
          font-weight: 800; font-size: 0.95em;
        }
        .raju-bubble-name { font-weight: 700; font-size: 0.98em; }
        .raju-bubble-meta { opacity: 0.55; font-size: 0.82em; margin-left: auto; }

        /* The streamed answer area — make the first paragraph (verdict) prominent */
        .raju-answer { padding: 4px 0 0 0; }
        .raju-answer > p:first-of-type {
          font-size: 1.18em; line-height: 1.55; font-weight: 600;
          padding: 14px 18px; margin: 0 0 16px 0;
          background: rgba(37,99,235,0.06);
          border-left: 4px solid #2563eb;
          border-radius: 6px;
        }
        .raju-answer > p:first-of-type strong {
          font-weight: 700;
        }
        .raju-answer p, .raju-answer li { font-size: 0.97em; line-height: 1.65; }
        .raju-answer ul { padding-left: 1.2em; margin: 6px 0 14px 0; }
        .raju-answer h2, .raju-answer h3,
        .raju-answer p strong:first-child {
          font-size: 0.78em; text-transform: uppercase;
          letter-spacing: 0.08em; opacity: 0.7;
        }

        /* User question pill above the bubble */
        .raju-you-asked {
          display: inline-flex; align-items: center; gap: 10px;
          background: rgba(37,99,235,0.08); border: 1px solid rgba(37,99,235,0.25);
          color: #2563eb; padding: 8px 14px; border-radius: 999px;
          font-size: 0.92em; font-weight: 500;
          margin: 8px 0 4px 0;
        }
        .raju-you-asked b { font-weight: 700; opacity: 0.65; font-size: 0.85em;
          text-transform: uppercase; letter-spacing: 0.08em; }

        /* ------- Comparison charts section ------- */
        .raju-charts-header {
          display: flex; align-items: baseline; gap: 12px;
          margin: 32px 0 8px 0;
        }
        .raju-charts-header h3 { margin: 0; }
        .raju-charts-header span { opacity: 0.55; font-size: 0.9em; }

        /* Stat cards (Home page) */
        .raju-stat-card {
          border: 1px solid; border-radius: 14px; padding: 22px 24px;
          background: rgba(127,127,127,0.03);
        }
        .raju-stat-num { font-size: 2.6em; font-weight: 800; line-height: 1; }
        .raju-stat-label { opacity: 0.65; font-size: 0.92em; margin-top: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_global_css()

# ---------- Clients (cached so we don't reconnect every rerun) ----------
@st.cache_resource
def get_nvidia_client() -> OpenAI:
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=st.secrets["NVIDIA_API_KEY"],
    )


@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


@st.cache_resource
def get_supabase_admin_client() -> Client:
    """Service-role client for Storage uploads (writes need elevated permissions)."""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_ROLE_KEY"])


# ---------- Live memory stats + brand bar ----------
@st.cache_data(ttl=30)
def get_memory_stats() -> dict:
    """Live counts for the brand bar. Cached 30s to avoid hammering DB on every rerun."""
    sb = get_supabase_client()
    n_models = sb.table("models").select("id", count="exact").execute().count or 0
    n_bench = sb.table("benchmarks").select("id", count="exact").execute().count or 0
    # Conflict_link is bidirectional, so each conflict pair shows up twice.
    conflict_rows = (
        sb.table("benchmarks").select("id").not_.is_("conflict_link", "null").execute().data or []
    )
    n_conflicts = len(conflict_rows) // 2
    n_opinions = sb.table("opinions").select("id", count="exact").execute().count or 0
    return {
        "models": n_models,
        "benchmarks": n_bench,
        "conflicts": n_conflicts,
        "opinions": n_opinions,
    }


def render_brand_bar():
    """Render the slim brand bar with logo, stats. Horizontal nav rendered separately below."""
    s = get_memory_stats()
    pulsing = " raju-logo--pulsing" if st.session_state.get("raju_thinking") else ""
    st.markdown(
        f"""
        <div class="raju-brandbar">
          <div class="raju-brand-row">
            <span class="raju-logo{pulsing}">◆</span>
            <span class="raju-wordmark">Ask Raju</span>
          </div>
          <div class="raju-stats">
            <span><b>{s['models']}</b> models</span>
            <span class="raju-dot">·</span>
            <span><b>{s['benchmarks']}</b> benchmarks</span>
            <span class="raju-dot">·</span>
            <span><b>{s['opinions']}</b> opinions</span>
            <span class="raju-dot">·</span>
            <span class="raju-conflict"><b>{s['conflicts']}</b> conflicts</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_nav(current_page: str):
    """Render horizontal chip-style nav. Call once after brand bar."""
    NAV = [("Query", "💬"), ("Browse", "🗂️"), ("Capture", "📥"), ("Home", "✦")]
    cols = st.columns([1, 1, 1, 1, 6])  # nav buttons + spacer
    for i, (name, icon) in enumerate(NAV):
        with cols[i]:
            is_current = name == current_page
            if is_current:
                st.markdown(
                    f"<div style='padding: 6px 14px; background: #2563eb; color: white; "
                    f"border-radius: 999px; font-weight: 600; font-size: 0.9em; "
                    f"text-align: center; margin: 2px 0;'>{icon} {name}</div>",
                    unsafe_allow_html=True,
                )
            else:
                if st.button(f"{icon} {name}", key=f"nav_{name}", use_container_width=True):
                    st.session_state["nav"] = name
                    st.rerun()


# ---------- LLM model IDs ----------
MODEL_HIGH_STAKES = "z-ai/glm4.7"                   # synthesis (GLM 4.7 thinking OFF: 0.76s TTFT, 88 TPS — fastest measured)
MODEL_CHEAP = "deepseek-ai/deepseek-v4-flash"       # extraction, conflict-check
MODEL_LONG_CONTEXT = "minimax/minimax-2.7"          # optional fallback for long content (may not exist on NIM)


# ---------- LLM helpers ----------
def llm_extract_model_card(text: str) -> dict:
    """Send a vendor model card to DeepSeek V4 Pro. Return structured extraction:
    {
      "model": {name, display_name, vendor, family, released_at, context_window,
                parameter_count, is_open_source, pricing_input, pricing_output, source_url, notes},
      "benchmarks": [{benchmark_name, score, unit, methodology, source_type, claimant}, ...],
      "opinion": {capability, body_md, claimant, source_type}
    }
    """
    nv = get_nvidia_client()

    system_prompt = """You extract structured information from AI model launch posts (a.k.a. "model cards").

Given the text of a vendor's model card or launch announcement, return a SINGLE JSON object with this exact shape:

{
  "model": {
    "name": "lowercase-hyphenated-id, e.g. 'opus-4.7' or 'deepseek-v4-pro'",
    "display_name": "Human-readable name, e.g. 'Claude Opus 4.7'",
    "vendor": "Anthropic | OpenAI | Google | DeepSeek | MiniMax | Alibaba/Qwen | Meta | Mistral | xAI | (other)",
    "family": "Claude | GPT | Gemini | DeepSeek-V | MiniMax | Qwen | Llama | (other)",
    "released_at": "YYYY-MM-DD or null if not stated",
    "context_window": integer in tokens or null,
    "parameter_count": "string like '671B (37B active)' or '28B' or 'undisclosed'",
    "is_open_source": true | false,
    "pricing_input": number ($/1M input tokens) or null,
    "pricing_output": number ($/1M output tokens) or null,
    "source_url": "URL of the model card if mentioned in text, else null",
    "notes": "1-2 sentence summary of what's notable about this model"
  },
  "benchmarks": [
    {
      "benchmark_name": "lowercase-hyphenated, e.g. 'swe-bench-verified' or 'mmlu-pro'",
      "score": numeric value,
      "unit": "% | elo | tokens/sec | (other)",
      "methodology": "subset, conditions, or caveats mentioned, else null",
      "source_type": "vendor_official",
      "claimant": "the vendor's name + 'launch post' (e.g. 'Anthropic launch post')"
    }
  ],
  "opinion": {
    "capability": "the primary capability this model card emphasizes (e.g. 'code-refactoring', 'long-context-recall', 'agentic-tool-use'), or null if broad",
    "body_md": "A markdown-formatted summary of the vendor's framing, 100-300 words. Capture how the vendor positions the model. Use vendor's own claims and tone. Include key numbers.",
    "claimant": "Vendor name + 'launch post' (mirrors benchmark claimant)",
    "source_type": "vendor_official"
  }
}

Rules:
- If a field is not mentioned in the text, use null (or empty array for benchmarks if none).
- Normalize model names to lowercase-hyphenated form (e.g. "Claude Opus 4.7" → "opus-4.7").
- Only include benchmarks the vendor explicitly claims with a numeric score.
- The opinion's body_md should be 100-300 words of substantive markdown. Use headings, lists where natural. Capture the vendor's framing accurately, do not editorialize.
- Output ONLY the JSON, no explanation, no markdown fences.
"""

    # Use V4 Flash for extraction. Vendor model cards are well-structured marketing
    # copy — V4 Pro's reasoning mode adds 30-90s of "thinking" without improving accuracy
    # on this task. Reserve V4 Pro for synthesis where grounded reasoning matters.
    completion = nv.chat.completions.create(
        model=MODEL_CHEAP,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=4096,
        # Explicitly disable reasoning even on Flash for max speed on this task.
        extra_body={"chat_template_kwargs": {"thinking": False}},
    )

    raw = completion.choices[0].message.content.strip()
    # Strip markdown fences if present (model sometimes wraps despite instruction)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ---------- DB + Storage helpers ----------
def slugify(text: str, max_length: int = 60) -> str:
    """Filesystem-safe slug from arbitrary text."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_length] if len(s) > max_length else s


def upsert_model(model_data: dict) -> str:
    """Insert model if it doesn't exist (by name), return id. If exists, return existing id."""
    sb = get_supabase_client()

    # Check existence
    existing = sb.table("models").select("id").eq("name", model_data["name"]).limit(1).execute()
    if existing.data:
        return existing.data[0]["id"]

    # Insert
    insert_payload = {k: v for k, v in model_data.items() if v is not None}
    result = sb.table("models").insert(insert_payload).execute()
    return result.data[0]["id"]


def insert_benchmarks(model_id: str, benchmarks: list[dict]) -> list[str]:
    """Insert benchmark rows. Returns list of inserted ids."""
    if not benchmarks:
        return []

    sb = get_supabase_client()
    payload = []
    for b in benchmarks:
        row = {k: v for k, v in b.items() if v is not None}
        row["model_id"] = model_id
        payload.append(row)

    result = sb.table("benchmarks").insert(payload).execute()
    return [r["id"] for r in result.data]


def list_models() -> list[dict]:
    """Return all models for selection dropdowns. Sorted by display_name."""
    sb = get_supabase_client()
    result = sb.table("models").select("id, name, display_name, vendor").order("display_name").execute()
    return result.data or []


def get_existing_benchmarks(model_id: str, benchmark_name: str) -> list[dict]:
    """Find existing benchmark rows for same model + benchmark_name (for conflict checking)."""
    sb = get_supabase_client()
    result = (
        sb.table("benchmarks")
        .select("id, score, unit, source_type, claimant, methodology")
        .eq("model_id", model_id)
        .eq("benchmark_name", benchmark_name)
        .execute()
    )
    return result.data or []


def set_benchmark_conflict_link(id_a: str, id_b: str) -> None:
    """Mark two benchmark rows as conflicting with each other (bidirectional)."""
    sb = get_supabase_client()
    sb.table("benchmarks").update({"conflict_link": id_b}).eq("id", id_a).execute()
    sb.table("benchmarks").update({"conflict_link": id_a}).eq("id", id_b).execute()


# ---------- Conflict detection (LLM-judged) ----------
def llm_judge_benchmark_conflict(new_row: dict, existing_row: dict) -> tuple[bool, str]:
    """Ask DeepSeek V4 Flash whether two benchmark rows for the same model+benchmark
    substantively disagree. Returns (is_conflict, reasoning_one_liner).
    """
    nv = get_nvidia_client()

    prompt = f"""Two benchmark scores claim performance for the SAME model on the SAME benchmark.
Determine if they SUBSTANTIVELY disagree (a real factual conflict that a knowledge system should flag), or if they are within normal variance / methodology differences that don't constitute a conflict.

Score A: {new_row.get('score')} {new_row.get('unit', '')}
  Source type: {new_row.get('source_type')}
  Claimant: {new_row.get('claimant')}
  Methodology: {new_row.get('methodology') or 'not specified'}

Score B: {existing_row.get('score')} {existing_row.get('unit', '')}
  Source type: {existing_row.get('source_type')}
  Claimant: {existing_row.get('claimant')}
  Methodology: {existing_row.get('methodology') or 'not specified'}

Consider: a difference of >5 absolute percentage points (or equivalent) coming from different source types (vendor vs independent eval) is usually a real conflict. A small difference (<3pp) within the same source type is usually noise.

Reply with EXACTLY this format on two lines:
VERDICT: YES or NO
REASON: one short sentence explaining your verdict
"""
    completion = nv.chat.completions.create(
        model=MODEL_CHEAP,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=200,
        extra_body={"chat_template_kwargs": {"thinking": False}},
    )
    text = completion.choices[0].message.content.strip()
    is_conflict = bool(re.search(r"VERDICT:\s*YES", text, re.IGNORECASE))
    reason_match = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE)
    reason = reason_match.group(1).strip() if reason_match else text
    return is_conflict, reason


def check_benchmark_conflicts(new_row_id: str, model_id: str, benchmark_name: str) -> list[dict]:
    """After inserting a new benchmark, check for conflicts with existing rows.
    Sets conflict_link on both sides for each conflict found.
    Returns list of conflict notifications: [{existing_id, existing_claimant, reason}, ...]
    """
    sb = get_supabase_client()

    # Fetch the row we just inserted
    new_row_result = sb.table("benchmarks").select("*").eq("id", new_row_id).limit(1).execute()
    if not new_row_result.data:
        return []
    new_row = new_row_result.data[0]

    # Fetch other rows for same model+benchmark, exclude self and already-paired-with-something
    existing = get_existing_benchmarks(model_id, benchmark_name)
    candidates = [r for r in existing if r["id"] != new_row_id]

    conflicts_found = []
    for cand in candidates:
        is_conflict, reason = llm_judge_benchmark_conflict(new_row, cand)
        if is_conflict:
            set_benchmark_conflict_link(new_row_id, cand["id"])
            conflicts_found.append(
                {"existing_id": cand["id"], "existing_claimant": cand["claimant"], "reason": reason}
            )
            # For v0-hackathon: link to first conflict found and stop. Multi-conflict handling deferred.
            break

    return conflicts_found


# ---------- Independent benchmark extraction ----------
def llm_extract_independent_benchmark(text: str, available_models: list[dict]) -> dict:
    """Parse a leaderboard snapshot or eval re-run text into a benchmark row.
    Returns {suggested_model_name, benchmark_name, score, unit, methodology, source_type, claimant, source_url}.
    """
    nv = get_nvidia_client()

    model_list_str = "\n".join(f"- {m['name']} ({m['display_name']}, {m['vendor']})" for m in available_models)
    if not model_list_str:
        model_list_str = "(no models registered yet)"

    system_prompt = f"""Extract a benchmark result from text describing an independent evaluation, leaderboard snapshot, or practitioner re-run. Return ONLY a JSON object with this exact shape:

{{
  "suggested_model_name": "match to one of the registered models below by their normalized name; null if no match",
  "benchmark_name": "lowercase-hyphenated, e.g. 'swe-bench-verified'",
  "score": numeric value,
  "unit": "% | elo | tokens/sec | (other)",
  "methodology": "subset, conditions, caveats; null if not specified",
  "source_type": "leaderboard | practitioner | independent_eval",
  "claimant": "who reported this — name + venue, e.g. 'HN re-run by @kapil_v' or 'Stanford long-context eval'",
  "source_url": "URL if mentioned, else null"
}}

Registered models (suggested_model_name should be one of these names if a match exists):
{model_list_str}

Output ONLY the JSON, no explanation, no markdown fences.
"""
    completion = nv.chat.completions.create(
        model=MODEL_CHEAP,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=512,
        extra_body={"chat_template_kwargs": {"thinking": False}},
    )
    raw = completion.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def insert_single_benchmark(model_id: str, benchmark_data: dict) -> str:
    """Insert one benchmark row (used by independent benchmark capture). Returns inserted id."""
    sb = get_supabase_client()
    row = {k: v for k, v in benchmark_data.items() if v is not None and k != "suggested_model_name"}
    row["model_id"] = model_id
    result = sb.table("benchmarks").insert(row).execute()
    return result.data[0]["id"]


def upload_opinion_file(model_name: str, opinion: dict, model_id: str) -> tuple[str, str]:
    """Build the opinion markdown file (with frontmatter), upload to Storage, insert metadata row.
    Returns (storage_path, opinion_id)."""
    sb_admin = get_supabase_admin_client()
    sb = get_supabase_client()

    today = date.today().isoformat()
    slug = slugify(opinion["claimant"])
    storage_path = f"opinions/{model_name}/{today}-{slug}.md"

    # Construct markdown with YAML frontmatter
    fm = {
        "model": model_name,
        "capability": opinion.get("capability"),
        "claimant": opinion["claimant"],
        "source_type": opinion["source_type"],
        "date": today,
    }
    fm_lines = ["---"]
    for k, v in fm.items():
        if v is None:
            fm_lines.append(f"{k}: null")
        elif isinstance(v, str):
            fm_lines.append(f"{k}: {v}")
        else:
            fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    body = "\n".join(fm_lines) + "\n\n" + opinion["body_md"]
    file_bytes = body.encode("utf-8")

    # Upload (overwrite-safe: use upsert via file_options)
    sb_admin.storage.from_("opinions").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "text/markdown", "upsert": "true"},
    )

    # Insert metadata row
    opinion_row = {
        "model_id": model_id,
        "capability": opinion.get("capability"),
        "storage_path": storage_path,
        "claimant": opinion["claimant"],
        "source_type": opinion["source_type"],
    }
    result = sb.table("opinions").insert(opinion_row).execute()
    return storage_path, result.data[0]["id"]


# ---------- Pages ----------
def page_home():
    render_brand_bar()
    render_nav("Home")
    s = get_memory_stats()

    st.markdown(
        """
        <div class="raju-hero">
          <h1>Your AI-model knowledge memory.</h1>
          <p>Ask Raju captures vendor claims, practitioner pushback, and benchmark contradictions —
             then synthesizes grounded answers with citations. No speculation, no smoothed-over disagreements.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    cards = [
        (s["models"], "models tracked", "#38bdf8"),
        (s["benchmarks"], "benchmark claims", "#a855f7"),
        (s["conflicts"], "live conflicts flagged", "#fb7185"),
    ]
    for col, (n, label, accent) in zip([c1, c2, c3], cards):
        with col:
            st.markdown(
                f"""
                <div class="raju-stat-card" style="border-color:{accent}55;">
                  <div class="raju-stat-num" style="color:{accent};">{n}</div>
                  <div class="raju-stat-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<h3 style='margin-top: 36px; margin-bottom: 8px;'>Demo me</h3>", unsafe_allow_html=True)
    st.caption("Each button jumps to a pre-loaded view. Pick whatever lands the wow.")
    d1, d2, d3, d4 = st.columns(4)
    if d1.button("⚠️  See a benchmark conflict", use_container_width=True):
        st.session_state["nav"] = "Browse"
        st.session_state["browse_focus"] = "opus-4.7"
        st.rerun()
    if d2.button("🤔  Best model for code?", use_container_width=True):
        st.session_state["nav"] = "Query"
        st.session_state["query_to_run"] = "Which model is best for code refactoring?"
        st.rerun()
    if d3.button("🔬  Long-context contradictions", use_container_width=True):
        st.session_state["nav"] = "Query"
        st.session_state["query_to_run"] = "What's the real performance of Gemini 3.1 Pro on long context?"
        st.rerun()
    if d4.button("📥  Capture a new model", use_container_width=True):
        st.session_state["nav"] = "Capture"
        st.rerun()

    # Subtle footer with the spec link
    st.markdown(
        """
        <div style='margin-top: 60px; padding-top: 18px; border-top: 1px solid rgba(127,127,127,0.18);
                    font-size: 0.85em; opacity: 0.6;'>
          Hackathon prototype · Streamlit + Supabase + DeepSeek V4 (NVIDIA NIM) ·
          Three primitives: typed memory with conflict-flagging, tool self-governance,
          friction-gated schema evolution.
        </div>
        """,
        unsafe_allow_html=True,
    )


CAPTURE_EXAMPLES = {
    "Anthropic Opus 4.7": (
        "Today we're releasing Claude Opus 4.7, our most capable model yet. "
        "Opus 4.7 sets a new state of the art on SWE-bench Verified at 81%, "
        "MMLU-Pro at 87%, and HumanEval at 95%. The model has a 1 million token "
        "context window and is priced at $15/$75 per million input/output tokens. "
        "Released April 15, 2026. Best suited for multi-file refactoring, "
        "architecture-level reasoning, and agentic workflows. Available via API today."
    ),
    "DeepSeek V4 Pro": (
        "DeepSeek-V4 Pro is our flagship reasoning model, an open-weight 671B MoE "
        "(37B active) released March 30, 2026. V4 Pro achieves HumanEval 92% and "
        "Codeforces ELO 2150. It supports a 256K context window. Pricing is $2.20 "
        "per million input tokens and $2.20 per million output tokens. "
        "Available on NVIDIA NIM and via direct API."
    ),
    "Gemini 3.1 Pro": (
        "Gemini 3.1 Pro Preview extends our long-context capabilities to a "
        "2 million token window. Vendor-measured 99.5% retrieval accuracy "
        "on the standard needle-in-haystack benchmark across the full context. "
        "Pricing: $4.50 per million input/output tokens. "
        "Released March 25, 2026."
    ),
}


def _render_model_metadata_dl(model: dict) -> str:
    """Render model dict as a definition-list-style HTML block (not raw JSON)."""
    rows = [
        ("Name", model.get("display_name") or model.get("name")),
        ("Vendor", model.get("vendor")),
        ("Family", model.get("family")),
        ("Released", model.get("released_at")),
        ("Context window", f"{model['context_window']:,} tokens" if model.get("context_window") else None),
        ("Parameters", model.get("parameter_count")),
        ("Open source", "Yes" if model.get("is_open_source") else "No"),
        (
            "Pricing (in / out per 1M)",
            f"${model.get('pricing_input')} / ${model.get('pricing_output')}"
            if model.get("pricing_input") is not None or model.get("pricing_output") is not None
            else None,
        ),
        ("Source URL", f"<a href='{model['source_url']}' target='_blank' rel='noopener noreferrer'>{model['source_url']}</a>" if model.get("source_url") else None),
        ("Notes", model.get("notes")),
    ]
    rows = [(k, v) for k, v in rows if v]
    return (
        "<div style='display:grid; grid-template-columns: 180px 1fr; gap: 8px 16px;'>"
        + "".join(
            f"<div style='opacity:0.6; font-size:0.85em;'>{k}</div>"
            f"<div style='font-weight:500;'>{v}</div>"
            for k, v in rows
        )
        + "</div>"
    )


def _render_benchmarks_list(benchmarks: list[dict]) -> str:
    """Render extracted benchmarks as a clean inline list, not raw JSON."""
    if not benchmarks:
        return "<div style='opacity:0.6;'>No benchmarks extracted.</div>"
    items = []
    for b in benchmarks:
        unit = b.get("unit") or "%"
        method = (
            f" <span style='opacity:0.55; font-size:0.85em; font-style:italic;'>({b['methodology']})</span>"
            if b.get("methodology") else ""
        )
        items.append(
            f"<div style='padding: 4px 0; display:flex; align-items:center; gap:8px; flex-wrap:wrap;'>"
            f"<code style='background:rgba(127,127,127,0.1); padding:2px 8px; border-radius:6px;'>"
            f"{b['benchmark_name']}</code>"
            f"<span style='font-weight:700;'>{b['score']} {unit}</span>"
            f"<span style='opacity:0.55;'>per</span>"
            f"<span style='font-weight:500;'>{b['claimant']}</span>"
            f"{method}"
            f"</div>"
        )
    return "".join(items)


def page_capture():
    render_brand_bar()
    render_nav("Capture")
    st.markdown(
        """
        <div class="raju-page-hero">
          <h2>Capture a model card</h2>
          <p>Paste a vendor launch post. Raju extracts the model, every benchmark mentioned,
             and the vendor's framing in one pass — and flags any conflicts with what's already in memory.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Quick-paste examples
    st.markdown("<div style='margin: 8px 0 4px 0; opacity:0.7; font-size:0.9em;'>Quick paste:</div>", unsafe_allow_html=True)
    ex_cols = st.columns(len(CAPTURE_EXAMPLES))
    for col, (label, text) in zip(ex_cols, CAPTURE_EXAMPLES.items()):
        if col.button(f"📄  {label}", use_container_width=True, key=f"ex_{label}"):
            st.session_state["capture_text"] = text
            st.rerun()

    # Bordered input card
    with st.container(border=True):
        text = st.text_area(
            "Paste the vendor model card / launch post",
            value=st.session_state.get("capture_text", ""),
            height=240,
            placeholder="e.g. paste the body of Anthropic's Opus 4.7 launch announcement here...",
            label_visibility="collapsed",
            key="capture_text_area",
        )
        col1, col2 = st.columns([1, 5])
        with col1:
            extract_btn = st.button("Extract", type="primary", disabled=not text.strip())
        with col2:
            st.caption("DeepSeek V4 Flash extracts structured fields. Takes ~3-8 seconds.")

    if extract_btn:
        st.session_state["raju_thinking"] = True
        try:
            with st.status("Raju is reading the model card…", expanded=False) as status:
                status.update(label="Finding the benchmarks the vendor wants you to see…")
                try:
                    extracted = llm_extract_model_card(text)
                except json.JSONDecodeError as e:
                    status.update(label="That didn't parse as JSON. Showing the error.", state="error")
                    st.exception(e)
                    st.session_state["raju_thinking"] = False
                    return
                except Exception as e:
                    status.update(label=f"Extraction failed: {type(e).__name__}", state="error")
                    st.error(f"{type(e).__name__}: {e}")
                    st.session_state["raju_thinking"] = False
                    return
                status.update(label="Catching anything they buried below the fold…")
                status.update(label="Extracted. Review the preview below.", state="complete")
        finally:
            st.session_state["raju_thinking"] = False

        st.session_state["pending_extraction"] = extracted

    if "pending_extraction" in st.session_state:
        extracted = st.session_state["pending_extraction"]
        st.markdown(
            "<h3 style='margin-top:24px;'>Preview · review and save</h3>", unsafe_allow_html=True
        )

        # Three accent-bar cards instead of plain expanders
        st.markdown(
            styled_card(
                "Model metadata",
                _render_model_metadata_dl(extracted.get("model", {})),
                accent_color=SOURCE_TYPE_COLORS["vendor_official"],
                icon="🏢",
            ),
            unsafe_allow_html=True,
        )

        bench_count = len(extracted.get("benchmarks", []))
        st.markdown(
            styled_card(
                f"Benchmarks · {bench_count}",
                _render_benchmarks_list(extracted.get("benchmarks", [])),
                accent_color=SOURCE_TYPE_COLORS["leaderboard"],
                icon="📊",
            ),
            unsafe_allow_html=True,
        )

        op = extracted.get("opinion", {})
        opinion_body = (
            f"<div style='display:flex; gap:12px; margin-bottom:10px; flex-wrap:wrap; align-items:center;'>"
            f"<span style='opacity:0.7;'>Capability:</span> "
            f"<span style='font-weight:500;'>{op.get('capability') or '(broad)'}</span>"
            f"<span style='opacity:0.4;'>·</span>"
            f"<span style='opacity:0.7;'>Claimant:</span> "
            f"<span style='font-weight:500;'>{op.get('claimant') or '?'}</span>"
            f"</div>"
            f"<div style='border-top: 1px solid rgba(127,127,127,0.18); padding-top: 10px; "
            f"font-size: 0.95em; line-height: 1.6;'>{op.get('body_md', '')}</div>"
        )
        st.markdown(
            styled_card(
                "Vendor opinion · saved as markdown file",
                opinion_body,
                accent_color=SOURCE_TYPE_COLORS["vendor_official"],
                icon="💬",
            ),
            unsafe_allow_html=True,
        )

        # Save / Cancel
        col1, col2, _ = st.columns([1, 1, 4])
        with col1:
            save_btn = st.button("💾  Save to memory", type="primary", key="save_card", use_container_width=True)
        with col2:
            cancel_btn = st.button("Cancel", key="cancel_card", use_container_width=True)

        if save_btn:
            st.session_state["raju_thinking"] = True
            try:
                with st.status("Raju is filing the records…", expanded=False) as status:
                    status.update(label="Writing model row…")
                    model_id = upsert_model(extracted["model"])
                    status.update(label=f"Writing {len(extracted.get('benchmarks', []))} benchmark rows…")
                    benchmark_ids = insert_benchmarks(model_id, extracted.get("benchmarks", []))
                    status.update(label="Uploading opinion as a markdown file to Supabase Storage…")
                    storage_path, opinion_id = upload_opinion_file(
                        extracted["model"]["name"], extracted["opinion"], model_id
                    )
                    status.update(label="Saved. Now checking for conflicts…")

                    # Conflict check on each new benchmark
                    all_conflicts = []
                    if benchmark_ids:
                        status.update(label="Cross-checking each new benchmark against existing rows…")
                        for new_id, b in zip(benchmark_ids, extracted["benchmarks"]):
                            conflicts = check_benchmark_conflicts(
                                new_id, model_id, b["benchmark_name"]
                            )
                            for c in conflicts:
                                c["new_benchmark_name"] = b["benchmark_name"]
                                c["new_score"] = b.get("score")
                                all_conflicts.append(c)
                    status.update(label="Done.", state="complete")

                # Success messages with Raju voice
                if all_conflicts:
                    st.warning(
                        f"⚠️  Saved — and Raju spotted {len(all_conflicts)} contradiction"
                        f"{'s' if len(all_conflicts) != 1 else ''}. Check the Browse view."
                    )
                    for c in all_conflicts:
                        st.markdown(
                            f"- **{c['new_benchmark_name']}**: vendor's claim of "
                            f"`{c['new_score']}` disagrees with **{c['existing_claimant']}**. "
                            f"{c['reason']}"
                        )
                else:
                    st.success(
                        f"✓  Saved. Raju remembers. "
                        f"({len(benchmark_ids)} benchmark row(s), opinion at `{storage_path}`)"
                    )

                # Clear stats cache so brand bar reflects new data on next page
                get_memory_stats.clear()
                # Clear the editor and pending state
                st.session_state.pop("pending_extraction", None)
                st.session_state.pop("capture_text", None)
            except Exception as e:
                st.error(f"Save failed: {type(e).__name__}: {e}")
                st.exception(e)
            finally:
                st.session_state["raju_thinking"] = False

        if cancel_btn:
            st.session_state.pop("pending_extraction", None)
            st.rerun()


# ---------- Source-type styling ----------
SOURCE_TYPE_COLORS = {
    "vendor_official":   "#3b82f6",  # blue
    "leaderboard":       "#a855f7",  # purple
    "practitioner":      "#f97316",  # orange
    "personal_usage":    "#22c55e",  # green
    "independent_eval":  "#ef4444",  # red
    "self_synthesis":    "#64748b",  # slate
}
SOURCE_TYPE_ICONS = {
    "vendor_official":   "🏢",
    "leaderboard":       "📊",
    "practitioner":      "👥",
    "personal_usage":    "👤",
    "independent_eval":  "🔬",
    "self_synthesis":    "🤖",
}


def source_pill(source_type: str) -> str:
    """Return inline HTML for a colored source-type pill."""
    color = SOURCE_TYPE_COLORS.get(source_type, "#64748b")
    icon = SOURCE_TYPE_ICONS.get(source_type, "")
    label = source_type.replace("_", " ")
    return (
        f"<span style='background:{color}1a; color:{color}; border:1px solid {color}66; "
        f"padding: 2px 10px; border-radius: 999px; font-size: 0.78em; font-weight: 600; "
        f"white-space: nowrap;'>{icon} {label}</span>"
    )


def claimant_link(claimant: str, source_url: str | None) -> str:
    """Render a claimant name as a link to its source URL if present, else plain text.
    The link opens in a new tab so the user can verify the grounded source."""
    if not source_url:
        return f"<span>{claimant}</span>"
    return (
        f"<a href='{source_url}' target='_blank' rel='noopener noreferrer' "
        f"style='color: inherit; text-decoration: underline; "
        f"text-decoration-color: rgba(127,127,127,0.45); text-underline-offset: 3px;'>"
        f"{claimant} <span style='font-size: 0.7em; opacity: 0.55;'>↗</span></a>"
    )


def styled_card(title: str, body_html: str, accent_color: str = "#64748b", icon: str = "") -> str:
    """Reusable accent-bar card. Use for preview sections, opinion headers, retrieval groups.
    Caller wraps with st.markdown(..., unsafe_allow_html=True). body_html is pre-rendered HTML."""
    icon_html = f"<span style='margin-right:6px;'>{icon}</span>" if icon else ""
    return (
        f"<div style='border:1px solid rgba(127,127,127,0.22); border-left:4px solid {accent_color}; "
        f"border-radius:10px; padding:14px 18px; margin:12px 0; background:rgba(127,127,127,0.04);'>"
        f"<div style='font-size:0.78em; text-transform:uppercase; letter-spacing:0.06em; "
        f"color:{accent_color}; font-weight:700; margin-bottom:10px;'>{icon_html}{title}</div>"
        f"<div style='font-size:0.95em; line-height:1.55;'>{body_html}</div>"
        f"</div>"
    )


def page_browse():
    render_brand_bar()
    render_nav("Browse")
    st.markdown(
        """
        <div class="raju-page-hero">
          <h2>Browse models</h2>
          <p>Pick a model to see its metadata, benchmarks across sources, and opinions. Conflicts are paired in red.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Pick a model. See metadata, benchmarks (with vendor-vs-practitioner conflicts paired in red), and opinions rendered from Supabase Storage.")

    models = list_models()
    if not models:
        st.info("Memory is empty. Capture a model card to get started — Raju learns from what you give him.")
        return

    display_names = [f"{m['display_name']}  ·  {m['vendor']}" for m in models]
    # Honor preselection from a Home demo button (clear after read so it only fires once)
    initial_idx = 0
    focus_target = st.session_state.pop("browse_focus", None)
    if focus_target:
        for i, m in enumerate(models):
            if m["name"] == focus_target:
                initial_idx = i
                break
    chosen_idx = st.selectbox(
        "Model",
        range(len(models)),
        format_func=lambda i: display_names[i],
        index=initial_idx,
        label_visibility="collapsed",
    )
    chosen_model = models[chosen_idx]
    model_id = chosen_model["id"]

    sb = get_supabase_client()
    full_model = sb.table("models").select("*").eq("id", model_id).limit(1).execute().data[0]
    benchmarks = (
        sb.table("benchmarks").select("*").eq("model_id", model_id).order("benchmark_name").execute().data
    ) or []
    opinions = (
        sb.table("opinions").select("*").eq("model_id", model_id).order("effective_at", desc=True).execute().data
    ) or []

    # Count conflicts within this model's benchmarks
    bench_id_set = {b["id"] for b in benchmarks}
    conflict_count = sum(1 for b in benchmarks if b.get("conflict_link") in bench_id_set) // 2

    st.markdown("---")

    # ---- Hero header ----
    open_src_pill = (
        "<span style='background:#22c55e1a; color:#22c55e; border:1px solid #22c55e66; "
        "padding: 3px 12px; border-radius: 999px; font-size: 0.85em; font-weight: 600;'>"
        "✓ open source</span>"
        if full_model.get("is_open_source")
        else "<span style='background:#64748b1a; color:#64748b; border:1px solid #64748b66; "
        "padding: 3px 12px; border-radius: 999px; font-size: 0.85em; font-weight: 600;'>closed source</span>"
    )
    family_pill = ""
    if full_model.get("family"):
        family_pill = (
            f"<span style='background:#8b5cf61a; color:#8b5cf6; border:1px solid #8b5cf666; "
            f"padding: 3px 12px; border-radius: 999px; font-size: 0.85em; font-weight: 600;'>"
            f"{full_model['family']}</span>"
        )
    vendor_pill = (
        f"<span style='background:#3b82f61a; color:#3b82f6; border:1px solid #3b82f666; "
        f"padding: 3px 12px; border-radius: 999px; font-size: 0.85em; font-weight: 600;'>"
        f"{full_model['vendor']}</span>"
    )
    conflict_pill = ""
    if conflict_count > 0:
        conflict_pill = (
            f"<span style='background:#ef44441a; color:#ef4444; border:1px solid #ef444466; "
            f"padding: 3px 12px; border-radius: 999px; font-size: 0.85em; font-weight: 600;'>"
            f"⚠ {conflict_count} conflict{'s' if conflict_count > 1 else ''}</span>"
        )

    st.markdown(
        f"""
        <div style='margin-bottom: 16px;'>
          <h2 style='margin: 0 0 8px 0; font-size: 2.1em; line-height: 1.1;'>{full_model['display_name']}</h2>
          <div style='display: flex; gap: 8px; flex-wrap: wrap; align-items: center;'>
            {vendor_pill} {family_pill} {open_src_pill} {conflict_pill}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if full_model.get("notes"):
        st.markdown(
            f"<div style='font-size: 1.05em; color: #475569; margin-bottom: 16px;'>"
            f"{full_model['notes']}</div>",
            unsafe_allow_html=True,
        )

    # ---- Quick stats strip ----
    cw = full_model.get("context_window")
    pi, po = full_model.get("pricing_input"), full_model.get("pricing_output")
    released = full_model.get("released_at")

    stats_cols = st.columns(4)
    with stats_cols[0]:
        st.markdown(
            f"<div style='font-size: 0.78em; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;'>Context</div>"
            f"<div style='font-size: 1.4em; font-weight: 600;'>{f'{cw:,}' if cw else '—'} <span style='font-size: 0.6em; color: #64748b;'>tok</span></div>",
            unsafe_allow_html=True,
        )
    with stats_cols[1]:
        st.markdown(
            f"<div style='font-size: 0.78em; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;'>Parameters</div>"
            f"<div style='font-size: 1.4em; font-weight: 600;'>{full_model.get('parameter_count') or '—'}</div>",
            unsafe_allow_html=True,
        )
    with stats_cols[2]:
        price_text = f"${pi}<span style='color: #64748b;'> / </span>${po}" if pi is not None and po is not None else "—"
        st.markdown(
            f"<div style='font-size: 0.78em; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;'>Pricing in / out per 1M</div>"
            f"<div style='font-size: 1.4em; font-weight: 600;'>{price_text}</div>",
            unsafe_allow_html=True,
        )
    with stats_cols[3]:
        st.markdown(
            f"<div style='font-size: 0.78em; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em;'>Released</div>"
            f"<div style='font-size: 1.4em; font-weight: 600;'>{released or '—'}</div>",
            unsafe_allow_html=True,
        )

    if full_model.get("source_url"):
        st.markdown(
            f"<div style='margin-top: 8px; font-size: 0.85em;'>"
            f"<a href='{full_model['source_url']}' target='_blank' style='color:#3b82f6;'>"
            f"↗ source</a></div>",
            unsafe_allow_html=True,
        )

    # ---- Benchmarks ----
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"### Benchmarks · {len(benchmarks)}")
    if not benchmarks:
        st.caption("No benchmarks captured for this model yet.")
    else:
        from collections import defaultdict

        by_bench: dict[str, list[dict]] = defaultdict(list)
        for b in benchmarks:
            by_bench[b["benchmark_name"]].append(b)

        # Render conflicting benchmarks first (they're the wow moment)
        bench_names = sorted(by_bench.keys(), key=lambda n: (
            0 if any(r.get("conflict_link") in {x["id"] for x in by_bench[n]} for r in by_bench[n]) else 1,
            n,
        ))

        for bench_name in bench_names:
            rows = by_bench[bench_name]
            row_ids_in_group = {r["id"] for r in rows}
            conflict_ids = {r["id"] for r in rows if r.get("conflict_link") in row_ids_in_group}

            if conflict_ids:
                conflict_rows = [r for r in rows if r["id"] in conflict_ids]
                other_rows = [r for r in rows if r["id"] not in conflict_ids]

                # Build the entire conflict card as ONE HTML block (st.columns can't nest in markdown HTML)
                # Compute the gap for emphasis
                scores = [float(r["score"]) for r in conflict_rows if r.get("score") is not None]
                gap_html = ""
                if len(scores) == 2:
                    gap = abs(scores[0] - scores[1])
                    unit = conflict_rows[0].get("unit") or ""
                    gap_html = (
                        f"<div style='text-align:center; padding: 0 16px; display:flex; "
                        f"flex-direction:column; align-items:center; justify-content:center;'>"
                        f"<div style='font-size: 1.6em; color: #ef4444; font-weight: 800; line-height: 1;'>≠</div>"
                        f"<div style='font-size: 0.78em; color: #ef4444; font-weight: 600; margin-top: 6px; "
                        f"white-space: nowrap;'>{gap:g} {unit} gap</div>"
                        f"</div>"
                    )

                # Render each side as an HTML cell
                cells_html = []
                for r in conflict_rows:
                    unit = r.get("unit") or ""
                    method_html = (
                        f"<div style='font-size: 0.82em; opacity: 0.65; margin-top: 8px; font-style: italic; "
                        f"line-height: 1.4;'>{r['methodology']}</div>"
                        if r.get("methodology") else ""
                    )
                    cells_html.append(
                        f"<div style='flex: 1; padding: 16px 18px; border-radius: 10px; "
                        f"border: 1px solid rgba(127,127,127,0.22); background: rgba(127,127,127,0.04); "
                        f"min-width: 0;'>"
                        f"<div style='font-size: 0.78em; opacity: 0.6; text-transform: uppercase; "
                        f"letter-spacing: 0.05em; margin-bottom: 4px;'>claims</div>"
                        f"<div style='font-size: 2.2em; font-weight: 800; line-height: 1; margin-bottom: 10px;'>"
                        f"{r['score']}<span style='font-size: 0.45em; opacity: 0.55; margin-left: 6px; "
                        f"font-weight: 500;'>{unit}</span></div>"
                        f"<div style='font-weight: 600; font-size: 1.0em; margin-bottom: 6px;'>"
                        f"{claimant_link(r['claimant'], r.get('source_url'))}</div>"
                        f"<div>{source_pill(r['source_type'])}</div>"
                        f"{method_html}"
                        f"</div>"
                    )

                # Assemble: header + flex row of (cell, gap, cell)
                pair_html = cells_html[0]
                if gap_html:
                    pair_html += gap_html
                if len(cells_html) > 1:
                    pair_html += cells_html[1]
                for extra in cells_html[2:]:
                    pair_html += extra

                st.markdown(
                    f"<div style='border: 2px solid #ef4444; border-radius: 14px; "
                    f"padding: 16px 18px; margin: 16px 0; background: #ef44440d;'>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center; "
                    f"margin-bottom: 14px;'>"
                    f"<div style='font-size: 1.15em; font-weight: 700; color: #ef4444;'>⚠ {bench_name}</div>"
                    f"<div style='font-size: 0.78em; color: #ef4444; font-weight: 700; "
                    f"letter-spacing: 0.04em;'>SOURCES DISAGREE</div>"
                    f"</div>"
                    f"<div style='display: flex; gap: 12px; align-items: stretch;'>{pair_html}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if other_rows:
                    for r in other_rows:
                        unit = r.get("unit") or ""
                        st.markdown(
                            f"<div style='padding: 6px 12px; margin: 4px 0; display: flex; "
                            f"align-items: center; gap: 8px; flex-wrap: wrap;'>"
                            f"<span style='font-weight: 700;'>{r['score']} {unit}</span>"
                            f"<span style='opacity: 0.55;'>per</span>"
                            f"<span style='font-weight: 500;'>{claimant_link(r['claimant'], r.get('source_url'))}</span>"
                            f"{source_pill(r['source_type'])}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
            else:
                # No conflicts — clean inline display
                st.markdown(
                    f"<div style='font-weight: 700; font-size: 1.05em; margin-top: 14px;'>{bench_name}</div>",
                    unsafe_allow_html=True,
                )
                for r in rows:
                    unit = r.get("unit") or ""
                    method_html = (
                        f" <span style='font-size: 0.85em; opacity: 0.6; font-style: italic;'>"
                        f"({r['methodology']})</span>"
                        if r.get("methodology") else ""
                    )
                    st.markdown(
                        f"<div style='padding: 4px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;'>"
                        f"<span style='font-weight: 700; font-size: 1.1em; min-width: 70px;'>{r['score']} <span style='opacity: 0.6; font-size: 0.85em;'>{unit}</span></span>"
                        f"<span>{claimant_link(r['claimant'], r.get('source_url'))}</span>"
                        f"{source_pill(r['source_type'])}"
                        f"{method_html}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    # ---- Opinions ----
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"### Opinions · {len(opinions)}")
    if not opinions:
        st.caption("No opinions captured for this model yet.")
    else:
        sb_admin = get_supabase_admin_client()
        for op in opinions:
            cap_text = op.get("capability") or "general"
            date_text = ""
            if op.get("effective_at"):
                try:
                    date_text = op["effective_at"][:10]
                except (TypeError, IndexError):
                    pass

            # Card header: claimant + capability + source pill + date, all on one line
            st.markdown(
                f"<div style='border: 1px solid rgba(127,127,127,0.25); border-radius: 12px; "
                f"padding: 14px 18px 6px 18px; margin: 14px 0 0 0; background: rgba(127,127,127,0.03);'>"
                f"<div style='display:flex; gap: 10px; align-items: center; flex-wrap: wrap;'>"
                f"<span style='font-weight: 600; font-size: 1.05em;'>{op['claimant']}</span>"
                f"<span style='opacity: 0.4;'>·</span>"
                f"<span style='opacity: 0.75;'>{cap_text}</span>"
                f"{source_pill(op['source_type'])}"
                f"<span style='opacity: 0.55; font-size: 0.85em; margin-left: auto;'>{date_text}</span>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # The Streamlit markdown render lives in its own block below the card div;
            # we use a thin container to scope the styling visually
            try:
                file_bytes = sb_admin.storage.from_("opinions").download(op["storage_path"])
                content = file_bytes.decode("utf-8") if isinstance(file_bytes, bytes) else str(file_bytes)
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                with st.container():
                    st.markdown(content)
                    st.markdown(
                        f"<div style='margin-top: 8px; font-size: 0.75em; color: #cbd5e1;'>"
                        f"<code>{op['storage_path']}</code></div>",
                        unsafe_allow_html=True,
                    )
            except Exception as e:
                st.error(f"Failed to load opinion file: {e}")


# ---------- Query / synthesis (Hour 3) ----------
def llm_extract_query_intent(query: str, available_models: list[dict]) -> dict:
    """Cheap LLM call to extract scope from a natural-language query.
    Returns {model_name | None, capability | None, scope: 'specific' | 'broad' | 'comparative'}.
    """
    nv = get_nvidia_client()
    model_list = "\n".join(f"- {m['name']} ({m['display_name']})" for m in available_models)
    prompt = f"""Parse this user question about AI models. Identify scope.

Available models:
{model_list}

Return JSON:
{{
  "model_name": "match ONE registered name if the query is about a specific model, else null",
  "capability": "lowercase-hyphenated capability if query mentions one (e.g. 'code-refactoring', 'long-context-recall', 'swe-bench-verified'), else null",
  "scope": "specific | broad | comparative"
}}

scope = "specific" if query is about one model + capability
scope = "broad" if query is about a topic across models (e.g. 'show me long context info')
scope = "comparative" if query asks 'which model is best' or compares models

User query: {query}

Output ONLY the JSON, no fences."""
    completion = nv.chat.completions.create(
        model=MODEL_CHEAP,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=256,
        extra_body={"chat_template_kwargs": {"thinking": False}},
    )
    raw = completion.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def retrieve_for_query(intent: dict) -> dict:
    """Fetch relevant benchmarks + opinions based on intent.

    Key principle: 'capability' is a CONCEPT (e.g. 'code-refactoring') that maps to MANY
    benchmarks (swe-bench, humaneval, etc.). DO NOT filter benchmarks by capability name —
    fetch all benchmarks for the relevant model(s) and let the LLM synthesis reason over them.

    Filter aggressively by model when specified; filter opinions by capability if exact match
    exists; otherwise broaden so we always have data to ground in."""
    sb = get_supabase_client()
    sb_admin = get_supabase_admin_client()

    model_id: str | None = None
    if intent.get("model_name"):
        ml = sb.table("models").select("id").eq("name", intent["model_name"]).limit(1).execute()
        if ml.data:
            model_id = ml.data[0]["id"]

    # ---- Benchmarks ----
    # Fetch by model if specified, else fetch all (comparative query needs cross-model data).
    bq = sb.table("benchmarks").select("*, models(name, display_name, vendor)")
    if model_id:
        bq = bq.eq("model_id", model_id)
    benchmarks = bq.limit(120).execute().data or []

    # ---- Opinions ----
    # Try strict filter first (model + exact capability match), then relax progressively.
    cap = intent.get("capability")

    def fetch_opinions(by_model: bool, by_cap: bool) -> list[dict]:
        oq = sb.table("opinions").select("*, models(name, display_name, vendor)")
        if by_model and model_id:
            oq = oq.eq("model_id", model_id)
        if by_cap and cap:
            oq = oq.eq("capability", cap)
        return oq.limit(40).execute().data or []

    opinions = fetch_opinions(by_model=True, by_cap=True)
    if not opinions and cap:
        # Drop capability filter
        opinions = fetch_opinions(by_model=True, by_cap=False)
    if not opinions and model_id:
        # Drop model filter too (fall back to all opinions)
        opinions = fetch_opinions(by_model=False, by_cap=False)
    if not opinions:
        # Final fallback: any recent opinions
        opinions = (
            sb.table("opinions")
            .select("*, models(name, display_name, vendor)")
            .order("effective_at", desc=True)
            .limit(20)
            .execute()
            .data or []
        )

    # Hydrate opinion bodies from Storage
    for op in opinions:
        try:
            fb = sb_admin.storage.from_("opinions").download(op["storage_path"])
            content = fb.decode("utf-8") if isinstance(fb, bytes) else str(fb)
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            op["body_md"] = content
        except Exception:
            op["body_md"] = "(failed to load body)"

    return {"benchmarks": benchmarks, "opinions": opinions}


SYNTHESIS_DELIMITER = "---CONFIDENCE---"


def _build_synthesis_prompts(query: str, records: dict) -> tuple[str, str]:
    """Build the (system_prompt, user_prompt) pair shared by streaming + non-streaming synthesis."""
    records_text = "## AVAILABLE BENCHMARKS\n\n" if records["benchmarks"] else ""
    for b in records["benchmarks"]:
        unit = b.get("unit") or "%"
        model = (b.get("models") or {}).get("display_name", "(unknown)")
        method = f" — Method: {b['methodology']}" if b.get("methodology") else ""
        records_text += (
            f"[r:{b['id']}] {model} on {b['benchmark_name']}: {b['score']} {unit} "
            f"per {b['claimant']} (source_type={b['source_type']}){method}\n"
        )
        if b.get("conflict_link"):
            records_text += f"  ↳ NOTE: this row CONFLICTS with another row (id: {b['conflict_link']})\n"

    if records["opinions"]:
        records_text += "\n## AVAILABLE OPINIONS\n\n"
        for op in records["opinions"]:
            model = (op.get("models") or {}).get("display_name", "(unknown)")
            cap = f" on {op['capability']}" if op.get("capability") else ""
            records_text += (
                f"[r:{op['id']}] Opinion by {op['claimant']} (source_type={op['source_type']}) "
                f"about {model}{cap}:\n{op.get('body_md', '(no body)')}\n\n"
            )

    system_prompt = f"""You answer questions about AI models using ONLY the records provided below. You follow the GROUNDING CONTRACT:

1. Every factual claim in your answer MUST cite at least one record by ID using the format [r:RECORD_ID]. The IDs are exactly as shown in the records (e.g. [r:abc123-def4-...]).
2. Never make claims that are not supported by the provided records. If you can't ground a claim, OMIT it.
3. If the records cannot support an answer, say "I don't have data on this in my memory" — do NOT speculate or rely on training knowledge.
4. ACKNOWLEDGE conflicts. If records disagree, surface BOTH perspectives with both citations. Never silently pick a side.
5. Compute a confidence score (0.0 to 1.0) based on source quality, agreement, and breadth.

OUTPUT FORMAT — must be exact, no preamble, no thinking out loud, no "let me look through the records":

Line 1: A bold one-sentence VERDICT that directly answers the question. State the conclusion (good/bad/winner/tie/unclear) up front, with the key citation. This is the answer the user reads first.

Then a blank line.

Then a short **Why:** section — 2-4 bullets with the supporting evidence and citations.

Then, only if records disagree, a **Caveat:** section — 1-3 bullets with the conflicting evidence and what it implies.

Total length: 120-220 words. Tight, factual, no hedging language ("it seems", "perhaps").

Then on a NEW LINE: {SYNTHESIS_DELIMITER}
Then on the LAST LINE: confidence as a decimal between 0 and 1 (e.g. 0.72).

EXAMPLE for the question "How does Opus 4.7 do on SWE-bench?":

**Opus 4.7's real-world SWE-bench score is contested: vendor claims 81%, independent re-runs land near 76% [r:abc-123] [r:def-456].**

**Why:**
- Anthropic's launch post reports 81% on SWE-bench Verified [r:abc-123].
- An HN re-run by @kapil_v on the same 500-problem subset got 76%, suspecting eval contamination [r:def-456].
- Excluding the suspect problems dropped the score to 73% [r:def-456].

**Caveat:**
- Vellum's leaderboard shows 87.6% [r:ghi-789], but methodology isn't disclosed — likely a different scaffold.

{SYNTHESIS_DELIMITER}
0.65
"""
    user_prompt = f"User question: {query}\n\n---\n\n{records_text}"
    return system_prompt, user_prompt


def llm_synthesize_grounded_answer_streaming(query: str, records: dict, model: str | None = None):
    """Generator yielding the markdown answer as it streams. Robust to:
    - models that emit content in `delta.content` (normal path)
    - models with thinking ON that emit in `delta.reasoning_content`
    Whichever channel arrives, we treat it as the answer text.

    After the SYNTHESIS_DELIMITER appears, the rest is parsed for confidence and
    NOT yielded. Sets st.session_state['_synth_final_answer'/'_synth_confidence'/
    '_synth_model_used'] when the stream completes.
    """
    nv = get_nvidia_client()
    system_prompt, user_prompt = _build_synthesis_prompts(query, records)
    chosen_model = model or MODEL_CHEAP

    # Synthesis runs without explicit thinking — the grounding contract is in the
    # prompt; reasoning mode causes the model to dump output into reasoning_content
    # and emit nothing in content, breaking streaming.
    stream = nv.chat.completions.create(
        model=chosen_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=2048,
        stream=True,
        extra_body={"chat_template_kwargs": {"thinking": False}},
    )

    accumulated = ""
    delimiter_seen = False
    after_delimiter = ""

    for chunk in stream:
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta
        # Try content first; fall back to reasoning_content if model dumps there
        piece = getattr(delta, "content", None) or ""
        if not piece:
            piece = (
                getattr(delta, "reasoning_content", None)
                or getattr(delta, "reasoning", None)
                or ""
            )
        if not piece:
            continue
        accumulated += piece
        if not delimiter_seen:
            if SYNTHESIS_DELIMITER in accumulated:
                idx = accumulated.find(SYNTHESIS_DELIMITER)
                already_yielded_len = len(accumulated) - len(piece)
                answer_part = accumulated[already_yielded_len:idx]
                if answer_part:
                    yield answer_part
                delimiter_seen = True
                after_delimiter = accumulated[idx + len(SYNTHESIS_DELIMITER):]
            else:
                yield piece
        else:
            after_delimiter += piece

    # Parse confidence after stream completes
    conf_text = after_delimiter.strip().split("\n")[-1].strip() if after_delimiter else "0.5"
    try:
        m = re.search(r"(\d+(?:\.\d+)?)", conf_text)
        confidence = float(m.group(1)) if m else 0.5
        if confidence > 1.0:
            confidence = confidence / 100.0
    except (ValueError, AttributeError):
        confidence = 0.5

    if delimiter_seen:
        final_answer = accumulated[: accumulated.find(SYNTHESIS_DELIMITER)].rstrip()
    else:
        final_answer = accumulated.rstrip()

    # If the streamed answer is empty (rare edge case — model returned nothing),
    # fall back to a non-streaming call as a last resort
    if not final_answer:
        try:
            non_stream = nv.chat.completions.create(
                model=chosen_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=2048,
                extra_body={"chat_template_kwargs": {"thinking": False}},
            )
            full = non_stream.choices[0].message.content or ""
            if SYNTHESIS_DELIMITER in full:
                final_answer = full[: full.find(SYNTHESIS_DELIMITER)].rstrip()
                tail = full[full.find(SYNTHESIS_DELIMITER) + len(SYNTHESIS_DELIMITER):].strip()
                m = re.search(r"(\d+(?:\.\d+)?)", tail)
                if m:
                    confidence = float(m.group(1))
                    if confidence > 1.0:
                        confidence /= 100.0
            else:
                final_answer = full.rstrip()
            if final_answer:
                yield final_answer
        except Exception:
            pass

    st.session_state["_synth_final_answer"] = final_answer
    st.session_state["_synth_confidence"] = confidence
    st.session_state["_synth_model_used"] = chosen_model


def save_synthesis(query: str, answer_md: str, citation_ids: list[str], confidence: float) -> str:
    """Persist synthesis as a row in syntheses table."""
    sb = get_supabase_client()
    result = sb.table("syntheses").insert({
        "query": query,
        "answer_md": answer_md,
        "citations_json": citation_ids,
        "confidence": confidence,
    }).execute()
    return result.data[0]["id"]


def render_with_citation_chips(answer_md: str, records: dict) -> str:
    """Replace [r:ID] markers in answer with clickable chips that link to the source."""
    record_lookup: dict[str, dict] = {}
    for b in records["benchmarks"]:
        model = (b.get("models") or {}).get("display_name", "?")
        record_lookup[b["id"]] = {
            "label": f"{model} · {b['benchmark_name']} · {b['score']} {b.get('unit') or ''} per {b['claimant']}",
            "source_url": b.get("source_url"),
            "kind": "bench",
        }
    for op in records["opinions"]:
        model = (op.get("models") or {}).get("display_name", "?")
        record_lookup[op["id"]] = {
            "label": f"{model} · opinion by {op['claimant']}",
            "source_url": op.get("source_url"),
            "kind": "op",
        }

    def chip(match: re.Match) -> str:
        rid = match.group(1)
        rec = record_lookup.get(rid)
        if not rec:
            return f"<code style='font-size:0.75em; color:#94a3b8;'>[r:{rid[:8]}]</code>"
        short = rid[:6]
        kind_color = "#3b82f6" if rec["kind"] == "bench" else "#22c55e"
        href = rec.get("source_url") or "#"
        target_attr = " target='_blank' rel='noopener noreferrer'" if rec.get("source_url") else ""
        return (
            f"<a href='{href}'{target_attr} title='{rec['label']}' "
            f"style='display:inline-block; background:{kind_color}1a; color:{kind_color}; "
            f"border:1px solid {kind_color}55; padding: 0px 7px; border-radius: 999px; "
            f"font-size: 0.72em; text-decoration: none; margin: 0 2px; font-family: monospace; "
            f"font-weight: 600; vertical-align: 1px;'>r:{short}</a>"
        )

    return re.sub(r"\[r:([a-f0-9-]+)\]", chip, answer_md)


def page_query():
    render_brand_bar()
    render_nav("Query")

    # Hero
    st.markdown(
        """
        <div class="raju-hero">
          <div class="raju-eyebrow">Knowledge memory · grounded by default</div>
          <h1>Ask Raju about any AI model.</h1>
          <p>Answers cite the records they're built on. Disagreements between sources stay visible.
             No speculation, no smoothed-over contradictions.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Query input — large, centered, with Ask button
    with st.form("query_form", clear_on_submit=False, border=False):
        c1, c2 = st.columns([8, 1])
        with c1:
            query = st.text_input(
                "Ask Raju",
                placeholder="Ask Raju anything about AI models, benchmarks, or claims…",
                label_visibility="collapsed",
                key="query_input",
            )
        with c2:
            submit = st.form_submit_button("Ask  →", type="primary", use_container_width=True)

    # Suggestion chips — horizontal, compact
    suggestions = [
        "Best model for code refactoring?",
        "How does Opus 4.7 actually perform on SWE-bench?",
        "Real performance of Gemini 3.1 Pro on long context?",
        "Contradictions about MiniMax 2.7?",
        "What did I observe about DeepSeek V4 Pro?",
    ]
    st.markdown(
        "<div style='font-size:0.78em; opacity:0.55; text-transform:uppercase; "
        "letter-spacing:0.08em; margin: 6px 0 8px 0; font-weight:600;'>"
        "Try one</div>",
        unsafe_allow_html=True,
    )
    sugg_cols = st.columns(len(suggestions))
    for col, s in zip(sugg_cols, suggestions):
        with col:
            if st.button(s, key=f"sugg_{hash(s)}", use_container_width=True):
                st.session_state["query_to_run"] = s
                st.rerun()

    # Allow suggestion buttons or external nav to inject a query
    if "query_to_run" in st.session_state:
        query = st.session_state.pop("query_to_run")
        submit = True

    if submit and query.strip():
        st.session_state["raju_thinking"] = True

        try:
            with st.status("Raju is thinking…", expanded=True) as status:
                # Single retrieval pass — broad fetch, let the synthesis LLM filter via reasoning.
                # (Skipped the separate intent-extraction LLM call: it added 1-3s of latency and a
                # failure point; the synthesis prompt receives all records and reasons about
                # relevance directly. Cleaner and faster.)
                status.update(label="Pulling relevant records from memory…")
                intent: dict = {}
                records = retrieve_for_query(intent)
                n_b = len(records["benchmarks"])
                n_o = len(records["opinions"])
                status.update(
                    label=f"Lined up {n_b} benchmark(s) + {n_o} opinion(s). Now I'll synthesize a grounded answer below.",
                    state="complete",
                )
        finally:
            pass

        with st.expander(
            f"Retrieval plan · scope={intent.get('scope', '?')} · "
            f"{n_b} benchmark(s) + {n_o} opinion(s) considered"
        ):
            st.markdown(
                f"**Intent:** model=`{intent.get('model_name') or '(any)'}` · "
                f"capability=`{intent.get('capability') or '(any)'}` · "
                f"scope=`{intent.get('scope', '?')}`"
            )

            st.markdown(f"**Benchmarks considered ({n_b}):**")
            if records["benchmarks"]:
                # Group by model for readability
                from collections import defaultdict as _dd
                by_model: dict[str, list[dict]] = _dd(list)
                for b in records["benchmarks"]:
                    mname = (b.get("models") or {}).get("display_name") or "(unknown)"
                    by_model[mname].append(b)
                for mname in sorted(by_model.keys()):
                    rows = by_model[mname]
                    items = []
                    for b in rows:
                        unit = b.get("unit") or ""
                        url_chip = (
                            f" [↗]({b['source_url']})" if b.get("source_url") else ""
                        )
                        conflict_chip = " ⚠️" if b.get("conflict_link") else ""
                        items.append(
                            f"`{b['benchmark_name']}` = **{b['score']} {unit}** "
                            f"per *{b['claimant']}* (`{b['source_type']}`){url_chip}{conflict_chip}"
                        )
                    st.markdown(
                        f"<div style='margin: 6px 0;'>"
                        f"<div style='font-weight: 600;'>{mname}</div>"
                        f"<div style='margin-left: 14px; font-size: 0.92em; opacity: 0.9;'>"
                        + "<br>".join(items)
                        + "</div></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("(none)")

            st.markdown(f"**Opinions considered ({n_o}):**")
            if records["opinions"]:
                for op in records["opinions"]:
                    mname = (op.get("models") or {}).get("display_name") or "(unknown)"
                    cap = op.get("capability") or "general"
                    url_chip = f" [↗]({op['source_url']})" if op.get("source_url") else ""
                    st.markdown(
                        f"- **{mname}** · `{cap}` · by *{op['claimant']}* "
                        f"(`{op['source_type']}`){url_chip}"
                    )
            else:
                st.caption("(none)")

        if n_b + n_o == 0:
            st.warning(
                "Raju doesn't make things up. The records can't ground an answer to this. "
                "Try a broader question or capture more sources first."
            )
            st.session_state["raju_thinking"] = False
            return

        # ---- User question pill ----
        st.markdown(
            f"""<div class="raju-you-asked">
            <b>YOU ASKED</b>
            <span>{query}</span>
            </div>""",
            unsafe_allow_html=True,
        )

        # Clear any prior streamed state
        for k in ("_synth_final_answer", "_synth_confidence", "_synth_model_used"):
            st.session_state.pop(k, None)

        # ---- Chat bubble (verdict-first answer) ----
        bubble_html_open = (
            '<div class="raju-bubble">'
            '<div class="raju-bubble-header">'
            '<span class="raju-bubble-avatar">◆</span>'
            '<span class="raju-bubble-name">Raju</span>'
            f'<span class="raju-bubble-meta">{MODEL_HIGH_STAKES.split("/")[-1]} · grounded by contract</span>'
            '</div>'
            '<div class="raju-answer">'
        )
        bubble_html_close = '</div></div>'

        synthesis_failed = False
        bubble_slot = st.empty()
        bubble_slot.markdown(
            bubble_html_open
            + '<p style="opacity:0.55; font-style: italic;">'
              'Cross-checking sources. Refusing to make stuff up…</p>'
            + bubble_html_close,
            unsafe_allow_html=True,
        )

        try:
            stream = llm_synthesize_grounded_answer_streaming(
                query, records, model=MODEL_HIGH_STAKES
            )
            accumulated = ""
            last_render = 0.0
            for piece in stream:
                accumulated += piece
                # Throttle re-renders to ~10/sec so markdown parsing doesn't choke the stream
                now = time.time()
                if now - last_render >= 0.1:
                    bubble_slot.markdown(
                        bubble_html_open + _MD.render(accumulated) + bubble_html_close,
                        unsafe_allow_html=True,
                    )
                    last_render = now
            # Final render of full accumulated text
            bubble_slot.markdown(
                bubble_html_open + _MD.render(accumulated) + bubble_html_close,
                unsafe_allow_html=True,
            )
        except Exception as e:
            synthesis_failed = True
            bubble_slot.empty()
            st.error(f"Synthesis failed: {type(e).__name__}: {e}")
        finally:
            st.session_state["raju_thinking"] = False

        if synthesis_failed:
            return

        # Pull the final answer + confidence from session state (set by the stream generator)
        final_answer = st.session_state.get("_synth_final_answer", "")
        confidence = float(st.session_state.get("_synth_confidence", 0.5))

        cited_ids = list(set(re.findall(r"\[r:([a-f0-9-]+)\]", final_answer)))

        # Re-render the bubble: render markdown to HTML, then swap [r:ID] markers for clickable citation chips
        if final_answer:
            html_body = _MD.render(final_answer)
            html_body_with_chips = render_with_citation_chips(html_body, records)
            bubble_slot.markdown(
                bubble_html_open + html_body_with_chips + bubble_html_close,
                unsafe_allow_html=True,
            )

        try:
            synth_id = save_synthesis(query, final_answer, cited_ids, confidence)
        except Exception:
            synth_id = None

        # ---- Confidence badge below the bubble ----
        conf_label = "HIGH" if confidence >= 0.75 else "MEDIUM" if confidence >= 0.5 else "LOW"
        conf_color = "#22c55e" if confidence >= 0.75 else "#f59e0b" if confidence >= 0.5 else "#ef4444"
        model_label = MODEL_HIGH_STAKES.split("/")[-1]

        st.markdown(
            f"<div style='display:flex; gap:10px; align-items:center; margin: -8px 0 16px 0; flex-wrap: wrap;'>"
            f"<span style='background:{conf_color}1a; color:{conf_color}; "
            f"border:1px solid {conf_color}66; padding: 3px 12px; border-radius: 999px; "
            f"font-size: 0.82em; font-weight: 700;'>Confidence: {conf_label} ({confidence:.2f})</span>"
            f"<span style='opacity: 0.55; font-size: 0.82em;'>"
            f"{len(cited_ids)} citation{'s' if len(cited_ids) != 1 else ''} · "
            f"answered by {model_label} · grounded in {n_b + n_o} record(s)</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ---- Comparison charts always visible below query/answer ----
    render_comparison_charts()


def render_comparison_charts():
    """Two Altair charts visible below the query area: model intelligence ranking
    and price-vs-intelligence frontier."""
    import altair as alt
    import pandas as pd

    sb = get_supabase_client()
    # Pull AA Intelligence Index per model + model metadata
    rows = (
        sb.table("benchmarks")
        .select("score, model_id, models(display_name, vendor, pricing_input, is_open_source)")
        .eq("benchmark_name", "ai-intelligence-index-v4")
        .execute()
        .data or []
    )
    if not rows:
        return

    df = pd.DataFrame([
        {
            "model": r["models"]["display_name"],
            "vendor": r["models"]["vendor"],
            "intelligence": r["score"],
            "price": r["models"]["pricing_input"],
            "is_open_source": r["models"]["is_open_source"],
        }
        for r in rows if r.get("models")
    ])
    if df.empty:
        return

    # Header
    st.markdown(
        """<div class="raju-charts-header">
        <h3>Model comparison · live from memory</h3>
        <span>built from the records Raju is reasoning over</span>
        </div>""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    # Chart 1: horizontal bar — Intelligence Index ranking
    with c1:
        st.caption("**AI Intelligence Index** (Artificial Analysis composite, 10 evals)")
        chart_df = df.sort_values("intelligence", ascending=True)
        bar = (
            alt.Chart(chart_df)
            .mark_bar(cornerRadius=4, height=22)
            .encode(
                x=alt.X("intelligence:Q", title=None, axis=alt.Axis(grid=True, gridDash=[3, 3])),
                y=alt.Y("model:N", sort=None, title=None, axis=alt.Axis(labelLimit=200)),
                color=alt.Color(
                    "is_open_source:N",
                    scale=alt.Scale(
                        domain=[True, False],
                        range=["#22c55e", "#2563eb"],
                    ),
                    legend=alt.Legend(title=None, orient="bottom", labelExpr="datum.value ? 'open source' : 'closed source'"),
                ),
                tooltip=["model", "vendor", "intelligence", "is_open_source"],
            )
            .properties(height=max(220, 28 * len(chart_df) + 60))
        )
        text = bar.mark_text(align="left", baseline="middle", dx=4, fontSize=12, fontWeight=600).encode(
            text=alt.Text("intelligence:Q", format=".0f"),
            color=alt.value("#475569"),
        )
        st.altair_chart(bar + text, use_container_width=True)

    # Chart 2: scatter — Price vs Intelligence (value frontier)
    with c2:
        st.caption("**Price-Intelligence frontier** (input $ per 1M tokens)")
        scatter_df = df.dropna(subset=["price"]).copy()
        scatter_df["price_for_chart"] = scatter_df["price"].apply(lambda p: max(p, 0.01))  # log scale needs >0

        if scatter_df.empty:
            st.caption("(no pricing data available for charts)")
        else:
            base = alt.Chart(scatter_df).encode(
                x=alt.X(
                    "price_for_chart:Q",
                    scale=alt.Scale(type="log"),
                    title="Input $ per 1M tokens (log scale)",
                    axis=alt.Axis(grid=True, gridDash=[3, 3]),
                ),
                y=alt.Y("intelligence:Q", title="Intelligence Index", axis=alt.Axis(grid=True, gridDash=[3, 3])),
                color=alt.Color(
                    "is_open_source:N",
                    scale=alt.Scale(domain=[True, False], range=["#22c55e", "#2563eb"]),
                    legend=None,
                ),
                tooltip=["model", "vendor", "intelligence", "price"],
            )
            dots = base.mark_circle(size=240, opacity=0.85, stroke="white", strokeWidth=2)
            labels = base.mark_text(align="left", baseline="middle", dx=10, fontSize=11, fontWeight=500).encode(
                text="model:N",
                color=alt.value("#475569"),
            )
            chart = (dots + labels).properties(height=max(280, 28 * len(scatter_df) + 60))
            st.altair_chart(chart, use_container_width=True)

    st.caption(
        "Open-source models in green, closed-source in blue. "
        "All data from rows captured in your memory — no external calls."
    )


# ---------- Main app routing ----------
# Sidebar is hidden via global CSS. Navigation lives inside render_nav() at the
# top of each page (chip-style row in the brand bar area).
NAV_OPTIONS = ["Query", "Browse", "Capture", "Home"]
current_page = st.session_state.pop("nav", "Query")  # Query is the default landing
if current_page not in NAV_OPTIONS:
    current_page = "Query"

if current_page == "Query":
    page_query()
elif current_page == "Browse":
    page_browse()
elif current_page == "Capture":
    page_capture()
elif current_page == "Home":
    page_home()
