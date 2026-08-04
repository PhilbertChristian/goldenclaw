"""Live quota — how much is left, and when it resets.

Local logs record what you *consumed*; they don't know your *entitlement*.
The provider's usage panel knows the entitlement but forgets history. This
module joins them: you enter a panel reading once ("weekly: 49% used, resets
Wed 3:00 PM"), NightClaw back-solves your cap from what it independently
measured over that same window, and from then on it tracks remaining quota,
burn rate, and time-to-exhaustion continuously — offline, no credentials,
no undocumented endpoints.

Consumption is measured in **cost-weighted units** (dollars at API rates),
not raw tokens. Raw totals are dominated by cache reads, which bill at ~0.1x
input; a raw-token cap would swing wildly with your cache-hit mix. Whatever
the provider actually meters, the cap is back-solved in the same unit the
consumption is measured in, so the ratio holds as long as your workload mix
is roughly stable. Re-calibrate whenever the panel and NightClaw disagree —
`nightclaw calibrate` is cheap and self-correcting.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import core, pricing

CALIBRATION = Path.home() / ".config" / "nightclaw" / "calibration.json"

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"]

# Pools the panel reports separately. `match` is a model-ID prefix; None = all.
POOLS = {
    "weekly": {"label": "Weekly · all models", "match": None},
    "fable": {"label": "Weekly · Fable", "match": "claude-fable"},
    "opus": {"label": "Weekly · Opus", "match": "claude-opus"},
}


def parse_reset(spec, now=None):
    """Parse a panel reset string into the next reset datetime (local, aware).

    Accepts "Wed 2:59 PM", "wednesday 15:00", or a full ISO timestamp.
    """
    now = now or datetime.now().astimezone()
    spec = (spec or "").strip()
    if not spec:
        raise ValueError("empty reset spec")

    try:
        dt = datetime.fromisoformat(spec)
        return dt if dt.tzinfo else dt.replace(tzinfo=now.tzinfo)
    except ValueError:
        pass

    parts = spec.replace(",", " ").split()
    if len(parts) < 2:
        raise ValueError(
            "reset must look like 'Wed 2:59 PM' or an ISO timestamp, got: " + spec)

    day_token = parts[0].lower()
    target_day = None
    for i, name in enumerate(WEEKDAYS):
        if name.startswith(day_token[:3]):
            target_day = i
            break
    if target_day is None:
        raise ValueError("unrecognized weekday: " + parts[0])

    time_str = " ".join(parts[1:]).upper().replace(".", "")
    hour = minute = None
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            t = datetime.strptime(time_str, fmt)
            hour, minute = t.hour, t.minute
            break
        except ValueError:
            continue
    if hour is None:
        raise ValueError("unrecognized time: " + " ".join(parts[1:]))

    ahead = (target_day - now.weekday()) % 7
    candidate = (now + timedelta(days=ahead)).replace(
        hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def _weighted(usage, model):
    """Cost-weighted consumption for one event, in USD at API rates."""
    rates = pricing.lookup(model)
    if rates is None:
        return 0.0
    inp, out = rates
    return (
        int(usage.get("input_tokens") or 0) * inp
        + int(usage.get("output_tokens") or 0) * out
        + int(usage.get("cache_creation_input_tokens") or 0) * inp * pricing.CACHE_WRITE_MULT
        + int(usage.get("cache_read_input_tokens") or 0) * inp * pricing.CACHE_READ_MULT
    ) / 1_000_000


def consumed(dirs, t0, t1, match=None):
    """Cost-weighted units consumed in [t0, t1], optionally for one model pool."""
    total = 0.0
    for when, usage, model in core.iter_events(dirs):
        if t0 <= when <= t1 and (match is None or model.startswith(match)):
            total += _weighted(usage, model)
    return total


def load():
    """The Claude (metered) calibration, if any."""
    from . import providers
    return providers.load_store()["providers"].get("claude")


def save_reading(pools, reset_spec, now=None):
    """Record a Claude panel reading. pools: {pool_name: percent_used}."""
    from . import providers
    now = now or datetime.now(timezone.utc)
    reset_at = parse_reset(reset_spec, now.astimezone())
    dirs = core.find_log_dirs()
    week_start = reset_at - timedelta(days=7)

    entries = {}
    for name, pct in pools.items():
        if name not in POOLS:
            raise ValueError("unknown pool: " + name)
        if not 0 < float(pct) <= 100:
            raise ValueError(
                "{}: percent must be between 0 and 100 (got {})".format(name, pct))
        used = consumed(dirs, week_start.astimezone(timezone.utc), now,
                        POOLS[name]["match"])
        entries[name] = {
            "percent_used": float(pct),
            "measured_units": round(used, 4),
            "cap_units": round(used / (float(pct) / 100), 4) if used > 0 else None,
        }

    data = {
        "kind": "metered",
        "label": "Claude",
        "taken_at": now.isoformat(),
        "reset_at": reset_at.isoformat(),
        "week_start": week_start.isoformat(),
        "pools": entries,
        "note": ("cap_units are back-solved: measured consumption over this "
                 "week's window divided by the panel's percent-used. Units are "
                 "USD-equivalent at API rates, not raw tokens."),
    }
    store = providers.load_store()
    store["providers"]["claude"] = data
    providers.save_store(store)
    return data


def session_window(dirs, now=None):
    """Current 5h session window state, computed from logs alone."""
    now = now or datetime.now(timezone.utc)
    events = sorted(
        (e for e in core.iter_events(dirs) if e[0] >= now - timedelta(days=2)),
        key=lambda e: e[0])
    if not events:
        return None
    windows = core.build_windows(events)
    last = windows[-1]
    if now >= last["end"]:
        return {"active": False, "resets_at": None, "used_units": 0.0}
    return {
        "active": True,
        "started_at": last["start"].isoformat(),
        "resets_at": last["end"].isoformat(),
        "minutes_left": max(0, int((last["end"] - now).total_seconds() // 60)),
        "used_units": round(consumed(dirs, last["start"], now), 4),
        "used_tokens": last["total"],
    }


def claude_state(now=None):
    """Live, measured quota for Claude — the one provider with local telemetry."""
    cal = load()
    now = now or datetime.now(timezone.utc)
    dirs = core.find_log_dirs()
    if cal is None:
        return {"calibrated": False, "kind": "metered", "label": "Claude",
                "provider": "claude", "measured": True,
                "session": session_window(dirs, now)}

    reset_at = datetime.fromisoformat(cal["reset_at"])
    week_start = datetime.fromisoformat(cal["week_start"])
    taken_at = datetime.fromisoformat(cal["taken_at"])

    # Roll the window forward if the calibrated week has already reset.
    weeks_elapsed = 0
    while reset_at <= now.astimezone(reset_at.tzinfo):
        reset_at += timedelta(days=7)
        week_start += timedelta(days=7)
        weeks_elapsed += 1

    ws_utc = week_start.astimezone(timezone.utc)
    elapsed_h = max(0.01, (now - ws_utc).total_seconds() / 3600)
    left_h = max(0.0, (reset_at.astimezone(timezone.utc) - now).total_seconds() / 3600)

    pools = {}
    for name, entry in cal["pools"].items():
        cap = entry.get("cap_units")
        if not cap:
            continue
        used = consumed(dirs, ws_utc, now, POOLS[name]["match"])
        pct = min(999.0, used / cap * 100)
        burn = used / elapsed_h
        runway_h = (cap - used) / burn if burn > 0 else None
        pools[name] = {
            "label": POOLS[name]["label"],
            "cap_units": round(cap, 2),
            "used_units": round(used, 2),
            "remaining_units": round(max(0.0, cap - used), 2),
            "percent_used": round(pct, 1),
            "percent_left": round(max(0.0, 100 - pct), 1),
            "burn_units_per_hour": round(burn, 3),
            "runway_hours": round(runway_h, 1) if runway_h is not None else None,
            "exhausts_before_reset": (
                runway_h is not None and runway_h < left_h),
        }

    return {
        "calibrated": True,
        "kind": "metered",
        "provider": "claude",
        "label": "Claude",
        "measured": True,
        "calibrated_at": cal["taken_at"],
        "calibration_age_days": round((now - taken_at.astimezone(timezone.utc)).days),
        "stale": weeks_elapsed > 0,
        "weeks_since_calibration": weeks_elapsed,
        "week_start": week_start.isoformat(),
        "resets_at": reset_at.isoformat(),
        # Spelled out so downstream agents never have to derive the weekday
        # from an ISO string — they get it wrong.
        "resets_at_human": reset_at.strftime("%A %-d %B, %-I:%M %p"),
        "hours_until_reset": round(left_h, 1),
        "pools": pools,
        "session": session_window(dirs, now),
        "unit": "USD-equivalent at API rates (cost-weighted, not raw tokens)",
    }


def state(now=None, allow_live=True):
    """Every provider's position.

    Claude is answered by the live OAuth usage API when a credential is
    available — that is ground truth, not an estimate. Calibration remains the
    offline fallback, and other providers stay transcribed readings.
    """
    from . import providers

    now = now or datetime.now(timezone.utc)
    store = providers.load_store()
    out = {"providers": {"claude": claude_state(now)}}

    if allow_live:
        from . import live
        try:
            snapshot = live.fetch()
            out["live"] = snapshot
            out["providers"]["claude"]["live"] = snapshot
        except live.LiveUnavailable as e:
            out["live_error"] = {"message": str(e), "signed_out": e.signed_out}

    for name, entry in store["providers"].items():
        if name == "claude":
            continue
        if entry.get("kind") == "manual":
            out["providers"][name] = providers.manual_state(name, entry, now)

    # Tightest pool across everything — what the menu bar title should show.
    tightest = None
    live_snapshot = out.get("live")
    if live_snapshot:
        for w in live_snapshot["windows"]:
            cand = {"provider": "claude", "label": w["label"],
                    "percent_left": w["percent_left"], "measured": True, "live": True}
            if tightest is None or cand["percent_left"] < tightest["percent_left"]:
                tightest = cand
    for name, p in out["providers"].items():
        if p.get("kind") == "metered":
            if live_snapshot or not p.get("calibrated"):
                continue
            for pool in p["pools"].values():
                cand = {"provider": name, "label": pool["label"],
                        "percent_left": pool["percent_left"],
                        "measured": True}
                if tightest is None or cand["percent_left"] < tightest["percent_left"]:
                    tightest = cand
        elif not p.get("reset_passed"):
            cand = {"provider": name, "label": p["label"],
                    "percent_left": p["percent_left"], "measured": False}
            if tightest is None or cand["percent_left"] < tightest["percent_left"]:
                tightest = cand
    out["tightest"] = tightest
    out["unit"] = "cost-weighted USD-equivalent at API rates (metered providers only)"
    return out


def night_budget_guard(reserve_pct=15.0):
    """Should the night shift run? Returns (ok, message).

    Only measured providers can gate the night — a transcribed reading is not
    a live number and must never silently authorize spending.
    """
    s = claude_state()
    if not s.get("calibrated"):
        return True, ("not calibrated — run `nightclaw calibrate` so the night "
                      "shift can protect your weekly quota")
    tight = [p for p in s["pools"].values() if p["percent_left"] < reserve_pct]
    if tight:
        worst = min(tight, key=lambda p: p["percent_left"])
        return False, "{} has only {:.1f}% left (reserve is {:.0f}%)".format(
            worst["label"], worst["percent_left"], reserve_pct)
    thin = min(s["pools"].values(), key=lambda p: p["percent_left"], default=None)
    if thin:
        return True, "{:.1f}% left on {}, resets in {:.0f}h".format(
            thin["percent_left"], thin["label"], s["hours_until_reset"])
    return True, "no pools calibrated"
