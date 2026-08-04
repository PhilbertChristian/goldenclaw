# SleepClaw — agent guide

SleepClaw is a zero-dependency, stdlib-only Python package (3.9+) that
measures AI subscription token utilization from local logs. Fork-and-modify
is the intended customization model — this file orients you.

## Layout

- `sleepclaw/core.py` — all real logic: log discovery (`find_log_dirs`),
  event parsing + dedup (`iter_events`), 5h window reconstruction
  (`build_windows`), metric assembly (`assemble`), env check (`doctor`).
- `sleepclaw/pricing.py` — API-rate table (prefix-matched, first match wins;
  keep specific prefixes before general ones) + `estimate_cost`. User
  override: `~/.config/sleepclaw/pricing.json`.
- `sleepclaw/render.py` — ANSI presentation only, no logic. Respects
  `NO_COLOR` and non-TTY. Bare `sleepclaw` must show live data, never help.
- `sleepclaw/cli.py` — argparse; subcommands `report` (default), `json`,
  `doctor`, `boot`, `quota`, `calibrate`, `goodnight`, `morning`, `backlog`,
  `ask`, `chat`, `menubar`.
- `sleepclaw/night.py` — the night shift: backlog parsing, repo allowlist,
  budget-capped headless `claude -p` runs, per-night JSONL journal.
- `sleepclaw/live.py` — the only networked module: resolves the local OAuth
  credential (Keychain first on macOS) and reads Anthropic's usage endpoint.
- `sleepclaw/quota.py` / `providers.py` — remaining-quota state, offline
  calibration fallback, and transcribed non-Claude readings.
- `sleepclaw/boot.py` — the sleepy-puppy boot sequence. Its status lines are
  real environment checks, not decoration; keep them honest.
- `sleepclaw/forecast.py` — Max's brain: WASTE/PACE/SHORTFALL verdicts from a
  straight-line pace projection (basis always stated), and task-cost estimates
  from real past journals only — no history, no estimate.
- `sleepclaw/ritual.py` — the 9pm goodnight experience: wake animation, day
  review, live budget, verdict, task collection, budget ask, then the guarded
  runner. Non-TTY falls back to the plain backlog flow.
- `sleepclaw/agent.py` — the conversation layer: `ask` (headless, allowed
  tools locked to `Bash(sleepclaw:*)`) and `chat` (interactive) over the
  Claude Code CLI. The agent must never invent numbers — the system prompt
  enforces run-the-sensor-first; keep it that way.

## Invariants — do not break these

1. **Local-first and read-only.** Exactly one network call exists —
   `live.py` asking Anthropic for your own quota with your own stored
   credential. Never add a second. The credential is read there and nowhere
   else, and is never printed, logged, returned, or persisted.
2. **Python 3.9 compatible**: no nested same-quote f-strings, no `match`,
   no `tomllib`.
3. **Zero runtime dependencies.** If a change needs a package, it's designed
   wrong.
4. **Conservative estimation**: any new derived metric must state its bias
   and err *against* the flattering direction. Update
   `docs/methodology.md` in the same change.
5. `sleepclaw json` output is a stable-ish interface (agents consume it) —
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
python3 -m unittest discover tests
python3 -m sleepclaw doctor
python3 -m sleepclaw
python3 -m sleepclaw json | python3 -m json.tool > /dev/null
```
