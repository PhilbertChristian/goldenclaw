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
  nightclaw json               full 7-day report as JSON
  nightclaw json --days N      any lookback (30 = monthly, 90 = quarterly)
  nightclaw doctor             verify data sources
  nightclaw goodnight --dry-run   preview tonight's plan (never run without --dry-run
                                  unless the user explicitly asks to launch the night)

Key files (the user may ask you to read or, in interactive sessions, edit):
  ~/.config/nightclaw/backlog.md   overnight tasks, format: `- [ ] repo: task`
  ~/.config/nightclaw/night.json   night-shift config (repos allowlist,
                                   budget, permission_mode — never set
                                   permission_mode yourself; that choice is
                                   the user's alone)

Interpretation guide:
- "utilization proxy" deliberately OVERSTATES utilization (denominator is a
  lower bound on entitlement) — always say true utilization is lower.
- The official Claude usage panel (session % / weekly %) is ground truth for
  entitlement; NightClaw is the permanent historical record.
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
