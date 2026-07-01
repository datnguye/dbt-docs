#!/usr/bin/env python3
"""Status-line renderer for Claude Code: model | tokens | session cost.

Claude Code invokes this on every status-line refresh, passing a JSON object on
stdin that includes at least ``session_id``, ``transcript_path``, ``model``, and
``cwd``. Cost is computed *locally* from the token counts already recorded in the
session transcript (one JSON object per line, each carrying a ``message.usage``
block) — no provider API call is made. Per-million-token rates load from
``.claude/pricing.yml`` (first-party Claude API rates); cache-write is 1.25x base
input for the 5-minute TTL and 2x for the 1-hour TTL, cache-read is 0.1x.

Per-million-token rates load from ``.claude/llm_price_tag.yml`` — edit that file
to update pricing.
"""

import json
import sys
from pathlib import Path

import yaml

PRICING_PATH = Path(__file__).resolve().parent.parent / "llm_price_tag.yml"

CACHE_WRITE_5M_MULT = 1.25
CACHE_WRITE_1H_MULT = 2.0
CACHE_READ_MULT = 0.1

RESET = "\033[0m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"

_config = yaml.safe_load(PRICING_PATH.read_text(encoding="utf-8"))
PRICING = _config["models"]
DEFAULT_PRICE = _config["default"]


def _price_for(model):
    if not model:
        return DEFAULT_PRICE
    for key, price in PRICING.items():
        if key in model:
            return price
    return DEFAULT_PRICE


def _cost_for_usage(usage, price):
    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    creation = usage.get("cache_creation") or {}
    write_5m = creation.get("ephemeral_5m_input_tokens")
    write_1h = creation.get("ephemeral_1h_input_tokens")
    if write_5m is None and write_1h is None:
        write_5m = usage.get("cache_creation_input_tokens", 0) or 0
        write_1h = 0
    write_5m = write_5m or 0
    write_1h = write_1h or 0

    per_million = price["input"] / 1_000_000
    out_per_million = price["output"] / 1_000_000
    input_cost = (
        input_tokens * per_million
        + cache_read * per_million * CACHE_READ_MULT
        + write_5m * per_million * CACHE_WRITE_5M_MULT
        + write_1h * per_million * CACHE_WRITE_1H_MULT
    )
    output_cost = output_tokens * out_per_million
    input_tokens_billable = input_tokens + cache_read + write_5m + write_1h
    return input_cost, output_cost, input_tokens_billable, output_tokens


def _tally(transcript_path, fallback_model):
    totals = {"in_cost": 0.0, "out_cost": 0.0, "in_tokens": 0, "out_tokens": 0}
    seen_model = fallback_model
    try:
        text = Path(transcript_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return totals, seen_model
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = record.get("message") or {}
        usage = message.get("usage")
        if not usage:
            continue
        model = message.get("model") or seen_model
        seen_model = model
        in_cost, out_cost, in_tokens, out_tokens = _cost_for_usage(usage, _price_for(model))
        totals["in_cost"] += in_cost
        totals["out_cost"] += out_cost
        totals["in_tokens"] += in_tokens
        totals["out_tokens"] += out_tokens
    return totals, seen_model


def _humanize_tokens(tokens):
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    if tokens >= 1_000:
        return f"{tokens / 1_000:.1f}k"
    return str(tokens)


def _short_model(model):
    if not model:
        return "?"
    return model.replace("claude-", "").replace("[1m]", "")


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    raw_model = payload.get("model")
    model = raw_model.get("id") if isinstance(raw_model, dict) else raw_model
    transcript_path = payload.get("transcript_path", "")

    totals, model = _tally(transcript_path, model)
    in_cost = totals["in_cost"]
    out_cost = totals["out_cost"]
    total_cost = in_cost + out_cost

    parts = [
        f"{CYAN}{_short_model(model)}{RESET}",
        f"{DIM}in {_humanize_tokens(totals['in_tokens'])} ${in_cost:.2f}{RESET}",
        f"{DIM}out {_humanize_tokens(totals['out_tokens'])} ${out_cost:.2f}{RESET}",
        f"{GREEN}${total_cost:.2f}{RESET}",
    ]
    sys.stdout.write(f" {DIM}|{RESET} ".join(parts))


if __name__ == "__main__":
    main()
