"""NightClaw sensor core — parse local Claude Code logs into utilization metrics.

Everything here is local-first and read-only: no network calls, no telemetry.
Windows are reconstructed with the same heuristics the community monitors use
(5-hour rolling windows, start floored to the hour of first activity), and the
utilization proxy deliberately overstates true utilization (its denominator is
a lower bound on real entitlement) so published improvements are conservative.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import pricing

WINDOW_HOURS = 5
NIGHT_START = 23  # local hour, inclusive
NIGHT_END = 7     # local hour, exclusive

TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def find_log_dirs():
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        candidates = [Path(p.strip()) / "projects" for p in env.split(",")]
    else:
        candidates = [
            Path.home() / ".config" / "claude" / "projects",
            Path.home() / ".claude" / "projects",
        ]
    return [d for d in candidates if d.is_dir()]


def iter_events(dirs):
    """Yield (utc_datetime, usage_dict, model) per API response, deduped."""
    seen = set()
    for d in dirs:
        for f in d.rglob("*.jsonl"):
            try:
                fh = open(f, errors="replace")
            except OSError:
                continue
            with fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = rec.get("message") or {}
                    usage = msg.get("usage")
                    ts = rec.get("timestamp")
                    if not isinstance(usage, dict) or not ts:
                        continue
                    key = (msg.get("id"), rec.get("requestId"))
                    if key != (None, None):
                        if key in seen:
                            continue
                        seen.add(key)
                    try:
                        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                    yield when, usage, msg.get("model") or "unknown"


def event_tokens(usage):
    return sum(int(usage.get(f) or 0) for f in TOKEN_FIELDS)


def build_windows(events):
    """Group time-sorted events into rolling 5h windows (start floored to hour)."""
    windows = []
    cur = None
    for when, usage, _model in events:
        if cur is None or when >= cur["end"]:
            start = when.replace(minute=0, second=0, microsecond=0)
            cur = {
                "start": start,
                "end": start + timedelta(hours=WINDOW_HOURS),
                "total": 0,
                "events": 0,
            }
            windows.append(cur)
        cur["total"] += event_tokens(usage)
        cur["events"] += 1
    return windows


def is_night(local_dt):
    return local_dt.hour >= NIGHT_START or local_dt.hour < NIGHT_END


def assemble(days=7, now=None):
    """Build the full report dict, or None if no data was found."""
    dirs = find_log_dirs()
    if not dirs:
        return None
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    events = sorted(
        (e for e in iter_events(dirs) if e[0] >= since), key=lambda e: e[0]
    )
    if not events:
        return None

    windows = build_windows(events)

    totals = dict.fromkeys(TOKEN_FIELDS, 0)
    by_model = {}
    heat = {}  # (iso_date, hour) -> tokens, local time
    night_tokens = 0
    grand_total = 0
    for when, usage, model in events:
        t = event_tokens(usage)
        grand_total += t
        local = when.astimezone()
        heat_key = (local.date().isoformat(), local.hour)
        heat[heat_key] = heat.get(heat_key, 0) + t
        if is_night(local):
            night_tokens += t
        mt = by_model.setdefault(model, dict.fromkeys(TOKEN_FIELDS, 0))
        for f in TOKEN_FIELDS:
            v = int(usage.get(f) or 0)
            totals[f] += v
            mt[f] += v

    slots = days * 24 / WINDOW_HOURS
    used = len(windows)
    peak = max(w["total"] for w in windows)
    avg = grand_total / used if used else 0
    coverage = used / slots
    utilization = grand_total / (peak * slots) if peak else 0.0

    cost_total, cost_per_model, unpriced = pricing.estimate_cost(by_model)

    local_today = now.astimezone().date()
    day_list = [
        (local_today - timedelta(days=i)).isoformat()
        for i in range(min(days, 14) - 1, -1, -1)
    ]

    return {
        "period_days": days,
        "since": since.isoformat(),
        "events": len(events),
        "tokens": {**totals, "total": grand_total},
        "by_model": {
            m: {**t, "total": sum(t.values())}
            for m, t in sorted(
                by_model.items(), key=lambda kv: -sum(kv[1].values())
            )
        },
        "windows": {
            "used": used,
            "possible_slots": round(slots, 1),
            "coverage_pct": round(coverage * 100, 1),
            "peak_window_tokens": peak,
            "avg_window_tokens": round(avg),
        },
        "utilization_proxy_pct": round(utilization * 100, 1),
        "overnight": {
            "night_hours_local": f"{NIGHT_START}:00-{NIGHT_END:02d}:00",
            "night_token_share_pct": round(
                night_tokens / grand_total * 100 if grand_total else 0, 1
            ),
        },
        "est_api_value_usd": round(cost_total, 2),
        "est_api_value_by_model": {
            m: round(v, 2) for m, v in sorted(cost_per_model.items(), key=lambda kv: -kv[1])
        },
        "unpriced_models": unpriced,
        "heatmap": {"days": day_list, "cells": {f"{d}T{h:02d}": v for (d, h), v in heat.items()}},
        "methodology": (
            "Local JSONL only; 5h windows floored to the hour. Utilization proxy "
            "= total / (peak_window x possible_slots); peak is a lower bound on "
            "the true limit, so true utilization is LOWER. Dollar value is what "
            "these tokens would cost at first-party API rates (cache write 1.25x, "
            "cache read 0.1x input)."
        ),
    }


def doctor():
    """Environment check: where the data is and whether NightClaw can see it."""
    dirs = find_log_dirs()
    checks = {"log_dirs": [str(d) for d in dirs], "files": 0, "events_sampled": 0}
    for d in dirs:
        checks["files"] += sum(1 for _ in d.rglob("*.jsonl"))
    if dirs:
        for i, _e in enumerate(iter_events(dirs)):
            checks["events_sampled"] = i + 1
            if i >= 499:
                break
    checks["ok"] = bool(dirs) and checks["files"] > 0 and checks["events_sampled"] > 0
    return checks
