"""Seed Supabase with demo data for Ask Raju.

Inserts:
- 8 models (mix of closed and open-source frontier models from Artificial Analysis leaderboard)
- ~25 benchmark rows (AA Intelligence Index per model + per-vendor specific benchmarks
  + 3 DELIBERATE vendor-vs-practitioner CONFLICTS for the wow demo)
- ~8 opinion files (vendor framings + Vipul personal observations)
- conflict_link pairs set on the 3 deliberate conflicts

Idempotent: safe to re-run (uses upsert on models, dedup on benchmarks, upsert on storage files).
"""

from __future__ import annotations

import time
import tomllib
from datetime import date

from supabase import create_client

with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

sb = create_client(secrets["SUPABASE_URL"], secrets["SUPABASE_KEY"])
sb_admin = create_client(secrets["SUPABASE_URL"], secrets["SUPABASE_SERVICE_ROLE_KEY"])

print("=== Seeding Ask Raju ===\n")

# ---------- Models ----------
MODELS = [
    {
        "name": "opus-4.7",
        "display_name": "Claude Opus 4.7",
        "vendor": "Anthropic",
        "family": "Claude",
        "released_at": "2026-04-15",
        "context_window": 1_000_000,
        "parameter_count": "undisclosed",
        "is_open_source": False,
        "pricing_input": 15.0,
        "pricing_output": 75.0,
        "source_url": "https://www.anthropic.com/news/claude-opus-4-7",
        "notes": "Anthropic's flagship as of April 2026. Vendor claims SOTA on SWE-bench Verified.",
    },
    {
        "name": "sonnet-4.6",
        "display_name": "Claude Sonnet 4.6",
        "vendor": "Anthropic",
        "family": "Claude",
        "released_at": "2026-02-20",
        "context_window": 1_000_000,
        "parameter_count": "undisclosed",
        "is_open_source": False,
        "pricing_input": 3.0,
        "pricing_output": 15.0,
        "source_url": "https://www.anthropic.com/news/claude-sonnet-4-6",
        "notes": "Workhorse model. Often comparable quality at 1/5th the cost of Opus on routine tasks.",
    },
    {
        "name": "gpt-5.5",
        "display_name": "GPT-5.5 (xhigh)",
        "vendor": "OpenAI",
        "family": "GPT",
        "released_at": "2026-03-10",
        "context_window": 256_000,
        "parameter_count": "undisclosed",
        "is_open_source": False,
        "pricing_input": 11.3,
        "pricing_output": 11.3,
        "source_url": "https://openai.com/blog/gpt-5-5",
        "notes": "OpenAI's top frontier model. Highest AA Intelligence Index as of late April 2026.",
    },
    {
        "name": "gemini-3.1-pro",
        "display_name": "Gemini 3.1 Pro Preview",
        "vendor": "Google",
        "family": "Gemini",
        "released_at": "2026-03-25",
        "context_window": 2_000_000,
        "parameter_count": "undisclosed",
        "is_open_source": False,
        "pricing_input": 4.5,
        "pricing_output": 4.5,
        "source_url": "https://blog.google/technology/google-deepmind/gemini-3-1-pro/",
        "notes": "Google's best as of late April 2026. 2M context. Vendor claims excellent long-context recall.",
    },
    {
        "name": "deepseek-v4-pro",
        "display_name": "DeepSeek V4 Pro (Max)",
        "vendor": "DeepSeek",
        "family": "DeepSeek-V",
        "released_at": "2026-03-30",
        "context_window": 256_000,
        "parameter_count": "671B (37B active)",
        "is_open_source": True,
        "pricing_input": 2.2,
        "pricing_output": 2.2,
        "source_url": "https://github.com/deepseek-ai/DeepSeek-V4",
        "notes": "Open-weight frontier model. Comparable quality to Opus at ~1/7th the cost.",
    },
    {
        "name": "deepseek-v4-flash",
        "display_name": "DeepSeek V4 Flash",
        "vendor": "DeepSeek",
        "family": "DeepSeek-V",
        "released_at": "2026-03-30",
        "context_window": 128_000,
        "parameter_count": "16B (2B active)",
        "is_open_source": True,
        "pricing_input": 0.14,
        "pricing_output": 0.28,
        "source_url": "https://github.com/deepseek-ai/DeepSeek-V4",
        "notes": "Cheap, fast variant. Used inside Ask Raju for high-volume conflict-checks and extraction.",
    },
    {
        "name": "minimax-2.7",
        "display_name": "MiniMax 2.7 (Muse Spark)",
        "vendor": "MiniMax",
        "family": "MiniMax",
        "released_at": "2026-04-05",
        "context_window": 4_000_000,
        "parameter_count": "456B MoE",
        "is_open_source": True,
        "pricing_input": 0.4,
        "pricing_output": 1.6,
        "source_url": "https://www.minimax.io/news/minimax-2-7",
        "notes": "Industry-leading 4M context window. Vendor claims 99.5% retrieval accuracy throughout.",
    },
    {
        "name": "qwen-3-28b",
        "display_name": "Qwen 3 28B",
        "vendor": "Alibaba/Qwen",
        "family": "Qwen",
        "released_at": "2026-01-15",
        "context_window": 128_000,
        "parameter_count": "28B",
        "is_open_source": True,
        "pricing_input": 0.0,
        "pricing_output": 0.0,
        "source_url": "https://github.com/QwenLM/Qwen3",
        "notes": "Strong open-weight model. Runs on consumer GPUs (24GB after Q4 quant). Solid for retrieval and extraction.",
    },
]


def upsert_model(m: dict) -> str:
    """Upsert by name. Returns model id."""
    existing = sb.table("models").select("id").eq("name", m["name"]).limit(1).execute()
    if existing.data:
        sb.table("models").update(m).eq("name", m["name"]).execute()
        return existing.data[0]["id"]
    result = sb.table("models").insert(m).execute()
    return result.data[0]["id"]


print("[1/4] Inserting models...")
model_ids: dict[str, str] = {}
for m in MODELS:
    model_ids[m["name"]] = upsert_model(m)
    print(f"  ✓ {m['display_name']}")


# ---------- Benchmarks ----------
# Format: (model_name, benchmark_name, score, unit, source_type, claimant, methodology, conflict_partner_index)
# conflict_partner_index: index of the OTHER row (within this list) that this conflicts with, or None
# Structured this way so we can resolve conflict_links AFTER all inserts.
# Tuple shape: (model, bench_name, score, unit, source_type, claimant, methodology, source_url, partner_idx)
# partner_idx: index in this list of the OTHER row this conflicts with (None = no conflict).
# AA leaderboard URL — used for all the AA Intelligence Index rows
_AA = "https://artificialanalysis.ai/leaderboards/models"

BENCHMARKS = [
    # 0-6: AA Intelligence Index (one per model, no conflicts)
    ("opus-4.7",          "ai-intelligence-index-v4",   57,   None,    "leaderboard",       "Artificial Analysis",   "Composite of 10 evals incl. GDPval-AA, SciCode, GPQA Diamond", _AA, None),
    ("sonnet-4.6",        "ai-intelligence-index-v4",   48,   None,    "leaderboard",       "Artificial Analysis",   "Composite of 10 evals",                                        _AA, None),
    ("gpt-5.5",           "ai-intelligence-index-v4",   60,   None,    "leaderboard",       "Artificial Analysis",   "Composite of 10 evals (xhigh setting)",                        _AA, None),
    ("gemini-3.1-pro",    "ai-intelligence-index-v4",   57,   None,    "leaderboard",       "Artificial Analysis",   "Composite of 10 evals",                                        _AA, None),
    ("deepseek-v4-pro",   "ai-intelligence-index-v4",   52,   None,    "leaderboard",       "Artificial Analysis",   "Composite of 10 evals (Max setting)",                          _AA, None),
    ("minimax-2.7",       "ai-intelligence-index-v4",   52,   None,    "leaderboard",       "Artificial Analysis",   "Composite of 10 evals (Muse Spark)",                           _AA, None),
    ("qwen-3-28b",        "ai-intelligence-index-v4",   38,   None,    "leaderboard",       "Artificial Analysis",   "Composite of 10 evals",                                        _AA, None),

    # 7-10: Output speed from AA (no conflicts)
    ("opus-4.7",          "output-speed-tps",            46,   "tokens/sec", "leaderboard",  "Artificial Analysis",   None,                                                           _AA, None),
    ("gpt-5.5",           "output-speed-tps",            73,   "tokens/sec", "leaderboard",  "Artificial Analysis",   None,                                                           _AA, None),
    ("gemini-3.1-pro",    "output-speed-tps",           127,   "tokens/sec", "leaderboard",  "Artificial Analysis",   None,                                                           _AA, None),
    ("deepseek-v4-pro",   "output-speed-tps",            36,   "tokens/sec", "leaderboard",  "Artificial Analysis",   None,                                                           _AA, None),

    # 11-12: ★ CONFLICT PAIR — Opus 4.7 SWE-bench Verified
    ("opus-4.7",          "swe-bench-verified",          81,   "%",     "vendor_official",   "Anthropic launch post", "Full Verified subset, 500 problems",                          "https://www.anthropic.com/news/claude-opus-4-7", 12),
    ("opus-4.7",          "swe-bench-verified",          76,   "%",     "practitioner",      "HN re-run by @kapil_v", "Same 500-problem subset, suspected eval contamination",       "https://news.ycombinator.com/item?id=mock-opus-47-swebench-rerun", 11),

    # 13-14: Opus other vendor benchmarks
    ("opus-4.7",          "mmlu-pro",                    87,   "%",     "vendor_official",   "Anthropic launch post", None,                                                           "https://www.anthropic.com/news/claude-opus-4-7", None),
    ("opus-4.7",          "humaneval",                   95,   "%",     "vendor_official",   "Anthropic launch post", None,                                                           "https://www.anthropic.com/news/claude-opus-4-7", None),

    # 15-16: Sonnet
    ("sonnet-4.6",        "humaneval",                   91,   "%",     "vendor_official",   "Anthropic capabilities post", None,                                                    "https://www.anthropic.com/news/claude-sonnet-4-6", None),
    ("sonnet-4.6",        "swe-bench-verified",          75,   "%",     "vendor_official",   "Anthropic capabilities post", None,                                                    "https://www.anthropic.com/news/claude-sonnet-4-6", None),

    # 17-18: GPT-5.5
    ("gpt-5.5",           "swe-bench-verified",          78,   "%",     "vendor_official",   "OpenAI release notes",  None,                                                           "https://openai.com/blog/gpt-5-5", None),
    ("gpt-5.5",           "mmlu-pro-tools",              79,   "%",     "vendor_official",   "OpenAI release notes",  None,                                                           "https://openai.com/blog/gpt-5-5", None),

    # 19-20: ★ CONFLICT PAIR — Gemini 3.1 Pro long-context recall
    ("gemini-3.1-pro",    "needle-in-haystack-1m",       99.5, "%",     "vendor_official",   "Google launch post",    None,                                                           "https://blog.google/technology/google-deepmind/gemini-3-1-pro/", 20),
    ("gemini-3.1-pro",    "needle-in-haystack-1m",       89,   "%",     "independent_eval",  "Stanford long-context eval", "Recall degrades sharply past 800K tokens",                "https://crfm.stanford.edu/2026/04/long-context-eval-v2.1.html", 19),

    # 21-22: DeepSeek vendor
    ("deepseek-v4-pro",   "humaneval",                   92,   "%",     "vendor_official",   "DeepSeek release notes", None,                                                          "https://github.com/deepseek-ai/DeepSeek-V4", None),
    ("deepseek-v4-pro",   "codeforces-elo",            2150,   "elo",   "vendor_official",   "DeepSeek release notes", None,                                                          "https://github.com/deepseek-ai/DeepSeek-V4", None),

    # 23-24: ★ CONFLICT PAIR — MiniMax 2.7 4M context recall
    ("minimax-2.7",       "needle-in-haystack-4m",       99.5, "%",     "vendor_official",   "MiniMax launch post",   None,                                                           "https://www.minimax.io/news/minimax-2-7", 24),
    ("minimax-2.7",       "needle-in-haystack-4m",       84,   "%",     "practitioner",      "Independent benchmark", "Recall degraded sharply past 1.5M tokens",                     "https://github.com/long-context-evals/minimax-2-7-eval", 23),

    # 25: Qwen
    ("qwen-3-28b",        "mmlu-pro",                    78,   "%",     "vendor_official",   "Qwen tech report",      None,                                                           "https://qwenlm.github.io/blog/qwen3/", None),

    # 26-37: Vellum LLM Leaderboard (third-party aggregator) — adds richer per-benchmark data
    # for our existing models. The Vellum Opus SWE-bench (87.6%) makes the existing
    # 81% vs 76% conflict pair into a 3-way data spread that the synthesis can reason over.
    ("opus-4.7",          "gpqa-diamond",                94.2, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("opus-4.7",          "swe-bench-verified",          87.6, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("sonnet-4.6",        "arc-agi-2",                   58.3, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("sonnet-4.6",        "mmmlu",                       89.3, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("gpt-5.5",           "gpqa-diamond",                93.6, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("gpt-5.5",           "humanitys-last-exam",         41.4, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("gpt-5.5",           "arc-agi-2",                   85.0, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("gemini-3.1-pro",    "gpqa-diamond",                91.9, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("gemini-3.1-pro",    "aime-2025",                  100.0, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("gemini-3.1-pro",    "humanitys-last-exam",         45.8, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("gemini-3.1-pro",    "mmmlu",                       91.8, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),
    ("gemini-3.1-pro",    "swe-bench-verified",          74.0, "%",     "leaderboard",       "Vellum LLM Leaderboard", None,                                                          "https://www.vellum.ai/llm-leaderboard", None),

    # 38-49: LMArena (chatbot-arena) human-vote ELO scores — direct user preference signal,
    # complementary to formal benchmarks. ELO ranks reveal a different truth than benchmark scores
    # (e.g. a model can rank high on benchmarks but be ranked lower by users in head-to-head matchups).
    ("opus-4.7",          "lmarena-overall-elo",       1494,   "elo",   "leaderboard",       "LMArena (chatbot-arena)", "Human pairwise preference voting, all categories",     "https://lmarena.ai/leaderboard", None),
    ("opus-4.7",          "lmarena-coding-rank",          2,   "rank",  "leaderboard",       "LMArena (chatbot-arena)", "Coding subcategory ranking out of 641 models",         "https://lmarena.ai/leaderboard", None),
    ("opus-4.7",          "lmarena-math-rank",            6,   "rank",  "leaderboard",       "LMArena (chatbot-arena)", "Math subcategory ranking",                              "https://lmarena.ai/leaderboard", None),
    ("sonnet-4.6",        "lmarena-overall-rank",        21,   "rank",  "leaderboard",       "LMArena (chatbot-arena)", "Overall ranking out of 641 models",                     "https://lmarena.ai/leaderboard", None),
    ("sonnet-4.6",        "lmarena-coding-rank",         22,   "rank",  "leaderboard",       "LMArena (chatbot-arena)", "Coding subcategory ranking",                            "https://lmarena.ai/leaderboard", None),
    ("gemini-3.1-pro",    "lmarena-overall-elo",       1493,   "elo",   "leaderboard",       "LMArena (chatbot-arena)", "Human pairwise preference voting, all categories",     "https://lmarena.ai/leaderboard", None),
    ("gemini-3.1-pro",    "lmarena-coding-rank",          7,   "rank",  "leaderboard",       "LMArena (chatbot-arena)", "Coding subcategory ranking",                            "https://lmarena.ai/leaderboard", None),
    ("gemini-3.1-pro",    "lmarena-math-rank",            3,   "rank",  "leaderboard",       "LMArena (chatbot-arena)", "Math subcategory ranking",                              "https://lmarena.ai/leaderboard", None),
    ("minimax-2.7",       "lmarena-overall-elo",       1492,   "elo",   "leaderboard",       "LMArena (chatbot-arena)", "Human pairwise preference voting (Muse Spark variant)", "https://lmarena.ai/leaderboard", None),
    ("minimax-2.7",       "lmarena-coding-rank",          5,   "rank",  "leaderboard",       "LMArena (chatbot-arena)", "Coding subcategory ranking",                            "https://lmarena.ai/leaderboard", None),
    ("deepseek-v4-pro",   "lmarena-overall-rank",        20,   "rank",  "leaderboard",       "LMArena (chatbot-arena)", "Overall ranking — note coding rank is much lower (#50)", "https://lmarena.ai/leaderboard", None),
    ("deepseek-v4-pro",   "lmarena-coding-rank",         50,   "rank",  "leaderboard",       "LMArena (chatbot-arena)", "Coding subcategory — significantly worse than benchmark scores suggest", "https://lmarena.ai/leaderboard", None),
]

print(f"\n[2/4] Inserting {len(BENCHMARKS)} benchmark rows...")
benchmark_ids: list[str | None] = [None] * len(BENCHMARKS)
for i, (mname, bname, score, unit, src_type, claimant, methodology, source_url, _conflict_idx) in enumerate(BENCHMARKS):
    row: dict = {
        "model_id": model_ids[mname],
        "benchmark_name": bname,
        "score": score,
        "source_type": src_type,
        "claimant": claimant,
    }
    if unit is not None:
        row["unit"] = unit
    if methodology:
        row["methodology"] = methodology
    if source_url:
        row["source_url"] = source_url

    # Dedup: skip if same (model_id, benchmark_name, source_type, claimant) already exists
    existing = (
        sb.table("benchmarks")
        .select("id")
        .eq("model_id", row["model_id"])
        .eq("benchmark_name", bname)
        .eq("source_type", src_type)
        .eq("claimant", claimant)
        .execute()
    )
    if existing.data:
        benchmark_ids[i] = existing.data[0]["id"]
        # Also update source_url on existing rows (in case we added it after initial seed)
        if source_url:
            sb.table("benchmarks").update({"source_url": source_url}).eq("id", existing.data[0]["id"]).execute()
    else:
        result = sb.table("benchmarks").insert(row).execute()
        benchmark_ids[i] = result.data[0]["id"]

print(f"  ✓ {len(BENCHMARKS)} rows ensured")

# Set conflict_link pairs (and clear any stale conflict_links from prior runs)
print("\n[3/4] Setting conflict_link on deliberate vendor-vs-practitioner pairs...")
# First clear all conflict_links on rows in our seed list, so we re-establish cleanly
for bid in benchmark_ids:
    if bid:
        sb.table("benchmarks").update({"conflict_link": None}).eq("id", bid).execute()

conflict_pairs_set = 0
for i, (_, _, _, _, _, _, _, _, partner_idx) in enumerate(BENCHMARKS):
    if partner_idx is not None and benchmark_ids[i] and benchmark_ids[partner_idx]:
        sb.table("benchmarks").update({"conflict_link": benchmark_ids[partner_idx]}).eq("id", benchmark_ids[i]).execute()
        conflict_pairs_set += 1
print(f"  ✓ {conflict_pairs_set // 2} conflict pair(s) set ({conflict_pairs_set} bidirectional links)")

# Sanity check: verify each conflict_link points back at us
print("\n  Verifying conflict_link bidirectionality...")
for i, (_, _, _, _, _, _, _, _, partner_idx) in enumerate(BENCHMARKS):
    if partner_idx is None:
        continue
    my_id = benchmark_ids[i]
    expected_partner_id = benchmark_ids[partner_idx]
    actual = sb.table("benchmarks").select("conflict_link").eq("id", my_id).execute().data[0]
    if actual["conflict_link"] != expected_partner_id:
        print(f"  ✗ Index {i}: conflict_link mismatch! Expected {expected_partner_id}, got {actual['conflict_link']}")
    else:
        partner_back = sb.table("benchmarks").select("conflict_link").eq("id", expected_partner_id).execute().data[0]
        if partner_back["conflict_link"] != my_id:
            print(f"  ✗ Index {partner_idx} doesn't point back at index {i}")
        else:
            print(f"  ✓ Pair ({i}, {partner_idx}) bidirectional")


# ---------- Opinions (markdown files in Storage + metadata rows) ----------
OPINIONS = [
    {
        "model": "opus-4.7",
        "capability": "code-refactoring",
        "claimant": "Vipul",
        "source_type": "personal_usage",
        "date": "2026-04-22",
        "body": """Failed twice today on a Postgres migration that Sonnet got right on the first try.

Both attempts produced syntactically valid SQL but used PG13-style quoted identifiers instead of PG16's standard. Sonnet 4.6 understood the version constraint immediately and produced a correct migration on the first attempt.

For migration work specifically, I'm bumping back to Sonnet. Opus is still my pick for greenfield architecture work, but the reasoning-heavy code generation isn't always a win — sometimes the model "thinks itself" into wrong assumptions.

Net: Opus is great when you need careful multi-step reasoning. For straightforward translation tasks where you have ground truth (PG16 syntax in this case), simpler models win.
""",
    },
    {
        "model": "opus-4.7",
        "capability": "swe-bench-verified",
        "claimant": "HN thread @kapil_v",
        "source_type": "practitioner",
        "date": "2026-04-18",
        "body": """**Re-ran SWE-bench Verified with Opus 4.7. Got 76%, not 81%.**

Anthropic's launch post claims 81% on the full Verified subset (500 problems). I re-ran the same subset with their published prompt template and got 76% across two independent runs.

I suspect eval contamination: 4-5 of the problems Anthropic likely had in the training data. When I excluded those problems, Opus dropped to 73%.

Methodology: ran via `swebench-verified` v0.3.2 with default settings, used Anthropic's public prompt template, max 10 attempts per problem. Cost: ~$87 for one full run.

**Adjusted view:** Opus is genuinely strong on SWE-bench, but 81% may be an upper bound that doesn't reflect held-out performance. Real-world refactoring is going to land closer to the 73-76% range.
""",
    },
    {
        "model": "opus-4.7",
        "capability": None,
        "claimant": "Anthropic launch post",
        "source_type": "vendor_official",
        "date": "2026-04-15",
        "body": """**Claude Opus 4.7: Our most capable model, optimized for reasoning and complex coding.**

Opus 4.7 sets a new state of the art on SWE-bench Verified at **81%**, MMLU-Pro at **87%**, and HumanEval at **95%**. It maintains a 1M token context window and is priced at $15/$75 per million input/output tokens.

Key improvements over Opus 4.5:
- 6-point gain on SWE-bench Verified
- 4-point gain on MMLU-Pro
- Improved tool-use reliability with 22% fewer schema errors

Best suited for: multi-file refactoring, architecture-level reasoning, agentic workflows, complex policy/legal analysis, and tasks where careful step-by-step reasoning matters more than raw throughput.

Opus 4.7 is available via API today and via Claude.ai for Pro and Max subscribers.
""",
    },
    {
        "model": "sonnet-4.6",
        "capability": "code-extraction",
        "claimant": "Vipul",
        "source_type": "personal_usage",
        "date": "2026-04-10",
        "body": """Sonnet 4.6 is my new default for structured-extraction tasks (e.g., parsing model cards into JSON, extracting claims from transcripts).

Quality is comparable to Opus on these well-defined tasks at ~1/5th the cost. The wins:
- Faster (no reasoning-mode overhead for tasks that don't need it)
- Cheaper (5x lower input price)
- Same accuracy on schema-bound outputs

When I switch back to Opus: anything requiring multi-step planning, contradiction reasoning, or novel synthesis. For "given this text, fill this schema," Sonnet wins.
""",
    },
    {
        "model": "gemini-3.1-pro",
        "capability": "long-context-recall",
        "claimant": "Stanford long-context eval team",
        "source_type": "practitioner",
        "date": "2026-04-08",
        "body": """**Independent eval of Gemini 3.1 Pro long-context recall: significantly worse than Google's claim.**

Google's launch post claims 99.5% needle-in-haystack accuracy across the full 1M token context. We ran an extended version of the standard NIH benchmark with 50 needles distributed across the context, repeated for context lengths from 100K to 1M tokens.

Findings:
- 100K-500K tokens: 96-98% accuracy. Strong.
- 500K-800K tokens: 92-94%. Still good.
- 800K-1M tokens: **75-89%**. Notable degradation.

Aggregate across the full 1M range: **89% accuracy**, not the 99.5% claimed.

Methodology: Stanford long-context benchmark v2.1, default temperature, repeated 5 times per context length.

Practical implication: Gemini 3.1 Pro is reliable up to ~800K tokens. Past that, hallucinated recall increases. Don't trust it as a fact-perfect retrieval tool at the upper end of its context window.
""",
    },
    {
        "model": "deepseek-v4-pro",
        "capability": "code-refactoring",
        "claimant": "Vipul",
        "source_type": "personal_usage",
        "date": "2026-04-12",
        "body": """Tested DeepSeek V4 Pro on three real refactoring tasks from TurnoCRM. Genuinely surprised at the quality-to-cost ratio.

- Task 1 (Spring Boot service refactor, ~800 LoC): Clean output. Caught one edge case Sonnet missed.
- Task 2 (TanStack Query → SWR migration, ~400 LoC): Equivalent quality to Sonnet. Slightly more verbose.
- Task 3 (Postgres migration with version constraint): Failed similar to Opus, mixed PG14/PG16 syntax. Same failure mode.

At $2.20/M input it's ~7x cheaper than Opus and ~1.5x cheaper than Sonnet. For structured refactor work, V4 Pro is now my second-pick after Sonnet (cheaper than Sonnet but slightly more verbose; quality is close).

Caveat: NVIDIA NIM endpoint has reasoning mode on by default which adds 30-60s per call. Disable with `extra_body={"chat_template_kwargs": {"thinking": False}}` for non-reasoning tasks.
""",
    },
    {
        "model": "minimax-2.7",
        "capability": None,
        "claimant": "MiniMax launch post",
        "source_type": "vendor_official",
        "date": "2026-04-05",
        "body": """**MiniMax 2.7 (Muse Spark): 4M token context window with state-of-the-art long-context retention.**

MiniMax 2.7 introduces a 4 million token context window, the largest commercially available. We measured **99.5% retrieval accuracy** across the full 4M token range using the standard needle-in-haystack benchmark.

Key technical innovations:
- New Lightning Attention v3 mechanism enables linear scaling beyond 1M tokens
- 456B parameter MoE architecture with expert routing optimized for long-document tasks
- Open-weight release (MIT license)

Pricing: $0.40/M input tokens, $1.60/M output tokens. Available via API and as downloadable weights.

Best for: long-document analysis, codebase-wide reasoning, multi-document synthesis, and any workflow that benefits from holding everything in context rather than retrieving.
""",
    },
    {
        "model": "qwen-3-28b",
        "capability": "local-deployment",
        "claimant": "Vipul",
        "source_type": "personal_usage",
        "date": "2026-04-20",
        "body": """Running Qwen 3 28B locally on a 24GB consumer GPU after Q4 quantization.

What works well:
- Retrieval and extraction tasks (parsing structured docs, identifying entities)
- Short-form summarization
- Simple classification

What's mid:
- Multi-step reasoning (clearly inferior to V4 Pro / Sonnet)
- Long-context tasks (128K is the spec but quality drops past 60K in my testing)
- Code generation beyond ~50 LoC

For Ask Raju specifically: Qwen 3 28B is a reasonable fallback if I want to do everything locally for privacy reasons. Today I'm using NVIDIA NIM models because they're free for the hackathon. Long-term I'd consider a Qwen-or-similar local fallback for the cheap conflict-check step.

FP16 needs 56GB+ VRAM; Q4 fits in 24GB with workable quality loss. Don't bother with Q2.
""",
    },
]


def slugify(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


print(f"\n[4/4] Uploading {len(OPINIONS)} opinion files to Storage + inserting metadata rows...")
for op in OPINIONS:
    storage_path = f"opinions/{op['model']}/{op['date']}-{slugify(op['claimant'])}.md"

    # Build markdown with frontmatter
    fm = (
        f"---\n"
        f"model: {op['model']}\n"
        f"capability: {op['capability']}\n"
        f"claimant: {op['claimant']}\n"
        f"source_type: {op['source_type']}\n"
        f"date: {op['date']}\n"
        f"---\n\n"
    )
    body = fm + op["body"]

    # Upload (upsert)
    sb_admin.storage.from_("opinions").upload(
        path=storage_path,
        file=body.encode("utf-8"),
        file_options={"content-type": "text/markdown", "upsert": "true"},
    )

    # Insert/upsert metadata row
    existing = (
        sb.table("opinions")
        .select("id")
        .eq("model_id", model_ids[op["model"]])
        .eq("storage_path", storage_path)
        .limit(1)
        .execute()
    )
    if not existing.data:
        sb.table("opinions").insert({
            "model_id": model_ids[op["model"]],
            "capability": op["capability"],
            "storage_path": storage_path,
            "claimant": op["claimant"],
            "source_type": op["source_type"],
        }).execute()

    print(f"  ✓ {op['model']}/{op['date']}-{slugify(op['claimant'])}.md")

print("\n=== Seed complete ===")
print(f"  Models:     {len(MODELS)}")
print(f"  Benchmarks: {len(BENCHMARKS)} (with {conflict_pairs_set // 2} deliberate conflicts)")
print(f"  Opinions:   {len(OPINIONS)} (markdown files in Supabase Storage)")
