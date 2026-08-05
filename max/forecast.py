"""Max's brain — pace forecasts and honest cost estimates.

Two jobs, both bound by the honest-numbers rule:

1. `week_verdict` — given the live weekly window, project where the week ends
   at the current average pace and classify it: WASTE (quota will expire
   unused), PACE (on track), SHORTFALL (you hit the wall before the reset).
   The projection is a straight line from this week's average burn — stated as
   such, never dressed up as anything smarter.

2. `estimate_tasks` — what a night's tasks might cost, based ONLY on this
   machine's own past overnight runs (the journals night.py writes). No
   history means no estimate: Max says "I don't know yet" rather than
   inventing a number.
"""

import json
import statistics
from datetime import datetime, timedelta, timezone

WASTE = "waste"
PACE = "pace"
SHORTFALL = "shortfall"

# Projected-unused above this is worth acting on; below it, minor slack is
# indistinguishable from healthy headroom and Max stays quiet.
WASTE_LEFTOVER_PCT = 20.0


def week_verdict(window, now=None):
    """Classify the weekly window. Returns a dict with `verdict`, or None when
    the window lacks what a projection needs (no reset time, week just began).

    window: {"percent_used": float, "resets_at": iso-str, ...} — the live
    `seven_day` entry from live.fetch().
    """
    now = now or datetime.now(timezone.utc)
    resets = window.get("resets_at")
    if not resets:
        return None
    try:
        reset_at = datetime.fromisoformat(resets.replace("Z", "+00:00"))
    except ValueError:
        return None
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)

    hours_left = (reset_at - now).total_seconds() / 3600
    if hours_left <= 0:
        return None
    week_start = reset_at - timedelta(days=7)
    elapsed_h = (now - week_start).total_seconds() / 3600
    if elapsed_h < 1:  # too little week elapsed to call anything a pace
        return None

    used = float(window.get("percent_used") or 0)
    pace_per_h = used / elapsed_h
    projected = used + pace_per_h * hours_left

    out = {
        "percent_used": round(used, 1),
        "percent_left": round(max(0.0, 100 - used), 1),
        "hours_left": round(hours_left, 1),
        "pace_pct_per_hour": round(pace_per_h, 3),
        "projected_pct_at_reset": round(min(projected, 999.0), 1),
        "basis": "straight-line projection of this week's average pace",
    }
    if projected >= 100 and pace_per_h > 0:
        out["verdict"] = SHORTFALL
        out["hours_to_wall"] = round((100 - used) / pace_per_h, 1)
    elif (100 - projected) > WASTE_LEFTOVER_PCT:
        out["verdict"] = WASTE
        out["projected_unused_pct"] = round(100 - projected, 1)
    else:
        out["verdict"] = PACE
    return out


def task_history(nights_dir):
    """Token costs of past overnight tasks, from the journals. Real runs only."""
    costs = []
    if not nights_dir.is_dir():
        return costs
    for f in sorted(nights_dir.glob("*.jsonl")):
        try:
            fh = open(f)
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") == "task":
                    tokens = entry.get("tokens")
                    if isinstance(tokens, (int, float)) and tokens > 0:
                        costs.append(int(tokens))
    return costs


def estimate_tasks(n_tasks, nights_dir):
    """Estimate tonight's token cost from past runs, or None when there is no
    history — Max never invents a number he can't back."""
    if n_tasks <= 0:
        return None
    costs = task_history(nights_dir)
    if not costs:
        return None
    med = int(statistics.median(costs))
    return {
        "runs_on_record": len(costs),
        "per_task_median": med,
        "per_task_low": min(costs),
        "per_task_high": max(costs),
        "tonight_median": med * n_tasks,
        "basis": "median of {} past overnight task(s) on this machine".format(len(costs)),
    }
