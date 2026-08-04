"""API-rate pricing used to express token consumption in dollar terms.

Rates are USD per million tokens at Anthropic first-party API prices
(input, output). Cache writes bill at 1.25x input, cache reads at 0.1x.
Prefix-matched, first match wins — keep more specific prefixes first.

Override with ~/.config/sleepclaw/pricing.json:
  {"claude-sonnet-5": {"input": 2.0, "output": 10.0}}
"""

import json
from pathlib import Path

DEFAULT_PRICES = [
    ("claude-fable-5", 10.0, 50.0),
    ("claude-mythos", 10.0, 50.0),
    ("claude-opus-5", 5.0, 25.0),
    ("claude-opus-4-1", 15.0, 75.0),
    ("claude-opus-4", 5.0, 25.0),
    ("claude-sonnet-5", 3.0, 15.0),
    ("claude-sonnet-4", 3.0, 15.0),
    ("claude-haiku-4-5", 1.0, 5.0),
]

CACHE_WRITE_MULT = 1.25
CACHE_READ_MULT = 0.10

_OVERRIDE_PATH = Path.home() / ".config" / "sleepclaw" / "pricing.json"


def _price_table():
    table = list(DEFAULT_PRICES)
    if _OVERRIDE_PATH.is_file():
        try:
            overrides = json.loads(_OVERRIDE_PATH.read_text())
            table = [
                (prefix, float(v["input"]), float(v["output"]))
                for prefix, v in overrides.items()
            ] + table
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
    return table


def lookup(model):
    for prefix, inp, out in _price_table():
        if model.startswith(prefix):
            return inp, out
    return None


def estimate_cost(model_tokens):
    """model_tokens: {model: {input_tokens, output_tokens, cache_creation_input_tokens,
    cache_read_input_tokens}} -> (total_usd, per_model_usd, unpriced_models)"""
    per_model = {}
    unpriced = []
    for model, t in model_tokens.items():
        rates = lookup(model)
        if rates is None:
            unpriced.append(model)
            continue
        inp, out = rates
        usd = (
            t.get("input_tokens", 0) * inp
            + t.get("output_tokens", 0) * out
            + t.get("cache_creation_input_tokens", 0) * inp * CACHE_WRITE_MULT
            + t.get("cache_read_input_tokens", 0) * inp * CACHE_READ_MULT
        ) / 1_000_000
        per_model[model] = usd
    return sum(per_model.values()), per_model, unpriced
