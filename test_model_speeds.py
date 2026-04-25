"""Benchmark NVIDIA NIM models for Ask Raju use cases.

Measures, per model + reasoning combo:
- TTFT: time to first token (initial latency)
- Total: wall time end-to-end
- Output tokens (from API usage stats)
- TPS: tokens/sec on output stream

Uses a representative model-card-extraction prompt so numbers reflect our actual workload.
"""

from __future__ import annotations

import time
import tomllib

from openai import OpenAI

with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

nv = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=secrets["NVIDIA_API_KEY"],
)

# Realistic prompt for Ask Raju: parse a model card into JSON
TEST_PROMPT = """Extract this AI model launch post into structured JSON. Output JSON only, no fences.

Text: Anthropic today announced Claude Opus 4.7, our most capable model. Opus 4.7 achieves state-of-the-art performance on SWE-bench Verified at 81%, MMLU-Pro at 87%, and HumanEval at 95%. The model has a 1 million token context window and is priced at $15/$75 per million input/output tokens. Released April 15, 2026.

JSON shape: {"model": {"name": "...", "vendor": "...", "context_window": int, "pricing_input": float, "pricing_output": float}, "benchmarks": [{"name": "...", "score": float}]}
"""

MODELS_TO_TEST = [
    ("deepseek-ai/deepseek-v4-flash", False, "V4 Flash, thinking OFF"),
    ("deepseek-ai/deepseek-v4-flash", True,  "V4 Flash, thinking ON "),
    ("deepseek-ai/deepseek-v4-pro",   False, "V4 Pro,   thinking OFF"),
    ("deepseek-ai/deepseek-v4-pro",   True,  "V4 Pro,   thinking ON "),
    ("minimax/minimax-2.7",           None,  "MiniMax 2.7           "),
]

print(f"\n{'Model':<28} {'TTFT':>8}   {'Total':>8}   {'Prompt':>7}   {'Output':>7}   {'TPS':>7}", flush=True)
print("-" * 80, flush=True)

for model_id, thinking, label in MODELS_TO_TEST:
    try:
        kwargs: dict = {
            "model": model_id,
            "messages": [{"role": "user", "content": TEST_PROMPT}],
            "max_tokens": 1024,
            "temperature": 0,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if thinking is not None:
            kwargs["extra_body"] = {"chat_template_kwargs": {"thinking": thinking}}

        start = time.time()
        first_token_time: float | None = None
        prompt_tokens = output_tokens = 0
        completion = nv.chat.completions.create(**kwargs)

        for chunk in completion:
            # Capture usage from the final chunk
            if getattr(chunk, "usage", None) is not None:
                prompt_tokens = chunk.usage.prompt_tokens
                output_tokens = chunk.usage.completion_tokens
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
            if (content or reasoning) and first_token_time is None:
                first_token_time = time.time()

        end = time.time()
        ttft = (first_token_time - start) if first_token_time else 0.0
        total = end - start
        gen_time = (end - first_token_time) if first_token_time else total
        tps = (output_tokens / gen_time) if (output_tokens and gen_time > 0) else 0.0

        print(f"{label:<28} {ttft:>7.2f}s   {total:>7.2f}s   {prompt_tokens:>7}   {output_tokens:>7}   {tps:>6.1f}/s", flush=True)

    except Exception as e:
        msg = str(e).replace("\n", " ")[:60]
        print(f"{label:<28} FAILED: {type(e).__name__}: {msg}", flush=True)

print()
