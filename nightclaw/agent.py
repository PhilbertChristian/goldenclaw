"""Talk to NightClaw — a NanoClaw-style harness over the Claude Code CLI.

NightClaw stays data-only (`nightclaw json`); the conversation layer is
Claude Code itself, launched with a system prompt that teaches it the tool.
`ask` is one-shot and headless, pre-approved to run ONLY `nightclaw`
commands — it cannot edit files or touch anything else without asking.
`chat` is a full interactive session where normal Claude Code permission
prompts apply, so you can also have it edit your backlog conversationally.
"""

import os
import shutil
import subprocess
import sys

SYSTEM_PROMPT = """\
You are NightClaw's agent: a token-utilization copilot for AI subscriptions.

Ground truth comes ONLY from running the `nightclaw` CLI with Bash — never
invent or estimate a number yourself:
  nightclaw quota --json       LIVE remaining quota, burn rate, time to reset
  nightclaw json               full 7-day historical report as JSON
  nightclaw json --days N      any lookback (30 = monthly, 90 = quarterly)
  nightclaw doctor             verify data sources

"How much is left?" / "am I going to run out?" / "can I afford this?" are
answered from `nightclaw quota --json` — percent_left, runway_hours, and
exhausts_before_reset per pool. If it reports calibrated=false, tell the user
to read their provider's usage panel and run:
  nightclaw calibrate --weekly <pct> --fable <pct> --resets "<Wed 3:00 PM>"
Never guess an entitlement, and never run `calibrate` with made-up numbers —
only the user can read the panel.
  nightclaw goodnight --dry-run   preview tonight's plan (never run without --dry-run
                                  unless the user explicitly asks to launch the night)

Key files (the user may ask you to read or, in interactive sessions, edit):
  ~/.config/nightclaw/backlog.md   overnight tasks, format: `- [ ] repo: task`
  ~/.config/nightclaw/night.json   night-shift config (repos allowlist,
                                   budget, permission_mode — never set
                                   permission_mode yourself; that choice is
                                   the user's alone)

Interpretation guide:
- Prefer CALIBRATED quota numbers (`nightclaw quota`) over the historical
  "utilization proxy" whenever the user asks about their real position.
- The "utilization proxy" in `nightclaw json` deliberately OVERSTATES
  utilization (its denominator is a theoretical throughput ceiling, not your
  plan's quota) — always say true utilization is lower, and point to
  `nightclaw quota` for the real number.
- The provider's usage panel is ground truth for entitlement; NightClaw
  calibrates against it once, then tracks remaining quota offline.
- Quota units are cost-weighted USD-equivalents, not raw tokens.
- Raw token totals are dominated by cache reads, which cost ~0.1x input rate;
  the est_api_value_usd field is the fairer "value consumed" measure.

Style: lead with the number the user asked for, in one sentence. Keep answers
short and concrete. Quote real figures from real runs only.
"""

ASK_ALLOWED_TOOLS = "Bash(nightclaw:*)"


def _require_claude():
    if shutil.which("claude") is None:
        print("`claude` CLI not found on PATH — install Claude Code first.",
              file=sys.stderr)
        return False
    return True


def ask(question, model=None):
    """One-shot question, headless. Only `nightclaw` commands are pre-approved."""
    if not _require_claude():
        return 1
    cmd = [
        "claude", "-p", question,
        "--append-system-prompt", SYSTEM_PROMPT,
        "--allowedTools", ASK_ALLOWED_TOOLS,
    ]
    if model:
        cmd += ["--model", model]
    return subprocess.call(cmd)


def chat(model=None):
    """Interactive session; hands the terminal over to Claude Code."""
    if not _require_claude():
        return 1
    cmd = ["claude", "--append-system-prompt", SYSTEM_PROMPT]
    if model:
        cmd += ["--model", model]
    os.execvp(cmd[0], cmd)
