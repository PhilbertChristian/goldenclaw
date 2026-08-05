"""Multi-provider quota — two tiers, because only one tier is measurable.

Surveying a real machine: Claude Code writes full per-response token usage to
local JSONL. Cursor writes transcripts with no token counts at all. Codex,
Grok, Kimi and friends write nothing usable, or aren't installed. So
"multi-provider token tracking from local logs" is, today, mostly not a thing
anyone can do honestly — which is why quota tooling in this space tracks
*percentages* rather than tokens.

GoldenClaw therefore supports two kinds of provider, and never blurs them:

  metered — local telemetry exists. Consumption is measured continuously,
            capacity is back-solved from one panel reading, and burn rate,
            runway, and projected exhaustion are all live. (Claude Code.)

  manual  — no local telemetry. You read that provider's own panel and tell
            GoldenClaw the percentage. It stores the reading with a timestamp
            and counts down to the reset, and it always shows the reading's
            age so a stale number can never masquerade as a live one.

A manual provider is not a worse metered provider; it is an honest record of
the last thing you actually saw. Anything else would be invention.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

STORE = Path.home() / ".config" / "max" / "calibration.json"

# Known providers. `metered` ones have a local-log adapter in core/quota;
# everything else is manual until someone writes an adapter for it.
PROVIDERS = {
    "claude": {"label": "Claude", "metered": True},
    "codex": {"label": "Codex", "metered": False},
    "cursor": {"label": "Cursor", "metered": False},
    "grok": {"label": "Grok", "metered": False},
    "kimi": {"label": "Kimi", "metered": False},
    "copilot": {"label": "Copilot", "metered": False},
    "gemini": {"label": "Gemini", "metered": False},
    "deepseek": {"label": "DeepSeek", "metered": False},
}

STALE_AFTER_HOURS = 24


def is_known(name):
    return name in PROVIDERS


def label(name):
    return PROVIDERS.get(name, {}).get("label", name.title())


def load_store():
    """Load the multi-provider store, migrating the v0.4 single-provider file."""
    if not STORE.is_file():
        return {"providers": {}}
    try:
        data = json.loads(STORE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"providers": {}}

    if "providers" in data:
        return data

    # v0.4 shape: a bare Claude calibration at the top level.
    if "pools" in data:
        return {"providers": {"claude": dict(data, kind="metered")}}
    return {"providers": {}}


def save_store(store):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, indent=2) + "\n")


def save_manual_reading(name, percent_used, reset_spec, plan=None, now=None):
    """Record 'the panel said X% at time T' for a provider we can't measure."""
    from . import quota  # local import: quota imports this module

    if not 0 <= float(percent_used) <= 100:
        raise ValueError("percent must be between 0 and 100")
    now = now or datetime.now(timezone.utc)
    reset_at = quota.parse_reset(reset_spec, now.astimezone())

    store = load_store()
    store["providers"][name] = {
        "kind": "manual",
        "label": label(name),
        "plan": plan,
        "percent_used": float(percent_used),
        "taken_at": now.isoformat(),
        "reset_at": reset_at.isoformat(),
        "note": ("A point-in-time reading you transcribed, not a measurement. "
                 "GoldenClaw counts down to the reset and reports the reading's "
                 "age; it does not extrapolate consumption it cannot see."),
    }
    save_store(store)
    return store["providers"][name]


def manual_state(name, entry, now=None):
    """Render-ready state for a manual provider reading."""
    now = now or datetime.now(timezone.utc)
    taken = datetime.fromisoformat(entry["taken_at"]).astimezone(timezone.utc)
    reset_at = datetime.fromisoformat(entry["reset_at"])

    age_h = (now - taken).total_seconds() / 3600
    expired = reset_at.astimezone(timezone.utc) <= now
    left_h = max(0.0, (reset_at.astimezone(timezone.utc) - now).total_seconds() / 3600)

    return {
        "kind": "manual",
        "provider": name,
        "label": entry.get("label") or label(name),
        "plan": entry.get("plan"),
        "percent_used": entry["percent_used"],
        "percent_left": round(100 - float(entry["percent_used"]), 1),
        "reading_age_hours": round(age_h, 1),
        "stale": age_h > STALE_AFTER_HOURS,
        "reset_passed": expired,
        "resets_at": entry["reset_at"],
        "resets_at_human": reset_at.strftime("%A %-d %B, %-I:%M %p"),
        "hours_until_reset": round(left_h, 1),
        "measured": False,
    }


def detect_installed():
    """Which provider CLIs are on PATH — for onboarding hints, not tracking."""
    import shutil
    binaries = {
        "claude": "claude", "codex": "codex", "cursor": "cursor-agent",
        "grok": "grok", "kimi": "kimi", "copilot": "copilot", "gemini": "gemini", "deepseek": "deepseek",
    }
    return {name: shutil.which(b) is not None for name, b in binaries.items()}
