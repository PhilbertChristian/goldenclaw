# NightClaw — agent guide

NightClaw is a zero-dependency, stdlib-only Python package (3.9+) that
measures AI subscription token utilization from local logs. Fork-and-modify
is the intended customization model — this file orients you.

## Layout

- `nightclaw/core.py` — all real logic: log discovery (`find_log_dirs`),
  event parsing + dedup (`iter_events`), 5h window reconstruction
  (`build_windows`), metric assembly (`assemble`), env check (`doctor`).
- `nightclaw/pricing.py` — API-rate table (prefix-matched, first match wins;
  keep specific prefixes before general ones) + `estimate_cost`. User
  override: `~/.config/nightclaw/pricing.json`.
- `nightclaw/render.py` — ANSI presentation only, no logic. Respects
  `NO_COLOR` and non-TTY. Bare `nightclaw` must show live data, never help.
- `nightclaw/cli.py` — argparse; subcommands `report` (default), `json`,
  `doctor`, `goodnight`, `morning`, `backlog`.
- `nightclaw/night.py` — the night shift: backlog parsing, repo allowlist,
  budget-capped headless `claude -p` runs, per-night JSONL journal.
- `nightclaw/agent.py` — the conversation layer: `ask` (headless, allowed
  tools locked to `Bash(nightclaw:*)`) and `chat` (interactive) over the
  Claude Code CLI. The agent must never invent numbers — the system prompt
  enforces run-the-sensor-first; keep it that way.

## Invariants — do not break these

1. **Local-first, read-only, no network calls.** Ever.
2. **Python 3.9 compatible**: no nested same-quote f-strings, no `match`,
   no `tomllib`.
3. **Zero runtime dependencies.** If a change needs a package, it's designed
   wrong.
4. **Conservative estimation**: any new derived metric must state its bias
   and err *against* the flattering direction. Update
   `docs/methodology.md` in the same change.
5. `nightclaw json` output is a stable-ish interface (agents consume it) —
   add keys freely, rename/remove reluctantly.
6. **The night runner's permission model is opt-in only.** Never give
   `permission_mode` a default, never accept `bypassPermissions`, never
   remove the launch confirmation. Unattended editing must always be an
   explicit, written choice by the user.

## Adding a provider adapter (the most-wanted contribution)

Write a generator that yields `(utc_datetime, usage_dict, model)` from the
provider's local logs — same shape as `iter_events` — where `usage_dict` uses
the four token keys in `core.TOKEN_FIELDS` (zero-fill what the provider
doesn't report). Add its rates to `pricing.py`, wire it into `assemble` and
`doctor`, and document the log location in the README.

## Testing changes

```bash
python3 -m nightclaw doctor
python3 -m nightclaw
python3 -m nightclaw json | python3 -m json.tool > /dev/null
```
