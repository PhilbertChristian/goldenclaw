"""True quota, straight from Anthropic — the numbers your usage panel shows.

Local logs record consumption; they cannot know your entitlement. Rather than
inferring it (see quota.py's calibration), this reads the OAuth credential the
Claude Code CLI already stores on this machine and asks Anthropic directly:

    GET https://api.anthropic.com/api/oauth/usage

That is the same data behind `/usage`, returned per window as a percentage
used plus a reset timestamp — no estimation, no proxy, no calibration.

Credential handling rules, and they are not negotiable:
  - read from here only, never from a code path that prints or logs
  - the token is never returned, echoed, written to disk, or included in an
    error message
  - on macOS the Keychain is authoritative: Claude Code refreshes it in place,
    while ~/.claude/.credentials.json is frequently a stale leftover that would
    otherwise mask a perfectly good sign-in
  - a rejected token (401/403) falls through to the next candidate rather than
    declaring you signed out

This is the one part of SleepClaw that touches the network, and it only ever
talks to api.anthropic.com with your own credential about your own account.
Everything else stays offline.
"""

import json
import platform
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
OAUTH_BETA = "oauth-2025-04-20"
KEYCHAIN_SERVICE = "Claude Code-credentials"
TIMEOUT_S = 10

CREDENTIAL_FILE = Path.home() / ".claude" / ".credentials.json"

WINDOW_LABELS = {
    "five_hour": "session (5h)",
    "seven_day": "week · all models",
    "seven_day_sonnet": "week · sonnet",
    "seven_day_opus": "week · opus",
    "seven_day_fable": "week · fable",
}
WINDOW_ORDER = list(WINDOW_LABELS)


class LiveUnavailable(Exception):
    """Raised with a user-facing reason. Never carries credential material."""

    def __init__(self, message, signed_out=False):
        super().__init__(message)
        self.signed_out = signed_out


def _parse_credential(raw, origin):
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    oauth = data.get("claudeAiOauth") or {}
    token = None
    for candidate in (oauth.get("accessToken"), data.get("accessToken"), data.get("access_token")):
        if isinstance(candidate, str) and candidate:
            token = candidate
            break
    if not token:
        return None

    expires = oauth.get("expiresAt")
    return {
        "token": token,
        "expires_at": expires if isinstance(expires, (int, float)) else None,
        "plan": oauth.get("subscriptionType") if isinstance(oauth.get("subscriptionType"), str) else None,
        "origin": origin,
    }


def _read_keychain():
    if platform.system() != "Darwin":
        return None
    try:
        proc = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return _parse_credential(proc.stdout.strip(), "keychain")


def _read_file():
    try:
        return _parse_credential(CREDENTIAL_FILE.read_text(), "file")
    except OSError:
        return None


def _candidates():
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    found = [c for c in (_read_keychain(), _read_file()) if c]
    usable = [c for c in found if c["expires_at"] is None or c["expires_at"] > now_ms]
    if platform.system() == "Darwin":
        usable.sort(key=lambda c: 0 if c["origin"] == "keychain" else 1)
    else:
        usable.sort(key=lambda c: -(c["expires_at"] or 0))
    return usable, bool(found)


def _request(token):
    req = urllib.request.Request(
        USAGE_URL,
        headers={"Authorization": "Bearer " + token, "anthropic-beta": OAUTH_BETA},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _normalize(payload):
    windows = []
    for key, value in payload.items():
        if key == "extra_usage" or not isinstance(value, dict):
            continue
        used = value.get("utilization")
        # A window with no numeric utilization is omitted, never defaulted to
        # 0 — "0% used" for an unknown window hides the real answer.
        if not isinstance(used, (int, float)):
            continue
        resets = value.get("resets_at")
        windows.append({
            "id": key,
            "label": WINDOW_LABELS.get(key, key.replace("_", " ")),
            "percent_used": round(float(used), 1),
            "percent_left": round(max(0.0, 100 - float(used)), 1),
            "resets_at": resets if isinstance(resets, str) else None,
        })
    windows.sort(key=lambda w: WINDOW_ORDER.index(w["id"]) if w["id"] in WINDOW_ORDER else 99)
    return windows


def _extra_usage(payload):
    extra = payload.get("extra_usage")
    if not isinstance(extra, dict) or not extra.get("is_enabled"):
        return None
    return {
        "used_credits": extra.get("used_credits"),
        "monthly_limit": extra.get("monthly_limit"),
        "currency": extra.get("currency"),
    }


def fetch():
    """Return the live quota snapshot, or raise LiveUnavailable."""
    candidates, any_found = _candidates()
    if not candidates:
        raise LiveUnavailable(
            "No usable Claude credential found. Sign in with `claude` first."
            if not any_found else
            "Your stored Claude credential has expired. Run `claude` to refresh it.",
            signed_out=True,
        )

    last = "Could not reach the usage API."
    for cred in candidates:
        try:
            payload = _request(cred["token"])
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                # Don't trust a stale token to mean signed-out; try the next.
                last = "Claude rejected the stored credential. Run `claude` to sign in again."
                continue
            last = "Usage API returned HTTP {}.".format(e.code)
            continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            last = "Could not reach the usage API."
            continue

        if not isinstance(payload, dict):
            last = "Usage API returned an unexpected response."
            continue
        windows = _normalize(payload)
        if not windows:
            last = "Usage API returned no readable windows."
            continue

        return {
            "source": "oauth",
            "plan": cred["plan"],
            "windows": windows,
            "extra_usage": _extra_usage(payload),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    raise LiveUnavailable(last, signed_out="sign in" in last.lower())


def available():
    """Whether a credential exists at all — for hints, without a network call."""
    candidates, _ = _candidates()
    return bool(candidates)
