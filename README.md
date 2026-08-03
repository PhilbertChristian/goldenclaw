# NightClaw 🌙

**Stop paying for tokens you never use.**

```
  🌙 NightClaw — token utilization, last 7 days

  Utilization  ▐█░░░░░░░░░░░░░░░░░░░░░░░░░▌  5.3% (proxy — true value is lower)
  Coverage     ▐██░░░░░░░░░░░░░░░░░░░░░░░░▌  8.9%  (3 of 34 possible 5h windows)
  Idle         ▐████████████████████████░░▌  91.1%  window slots that expired unused

  Usage heatmap  (local time, hourly intensity)
        00 02 04 06 08 10 12 14 16 18 20 22
  07-29                   ░
  07-30            ▓
  08-03            █

  Totals  7.8M tokens · 99 API responses
    overnight share (23:00-07:00 local): 0.0%

  Est. API-rate value consumed  $17.45
```

## Why I built NightClaw

An AI subscription is perishable capacity. Every 5-hour window that resets
with unused quota is inventory that expired on the shelf — and nobody manages
it like capacity. Plenty of tools *monitor* usage; none of them answer the
question that actually matters: **how much of what I pay for do I actually
use, and what would it take to stop wasting the rest?**

So I measured mine. The answer was **under 9% window coverage, 0% overnight
usage** — more than 90% of paid capacity expiring unused, every week. If your
first baseline doesn't shock you, you're the exception.

NightClaw is the sensor first, and eventually the whole loop: measure the
waste, then put the idle hours — mostly the ones you spend asleep — to work.

## Quick start

```bash
pipx install git+https://github.com/PhilbertChristian/nightclaw
nightclaw
```

Or without installing anything:

```bash
git clone https://github.com/PhilbertChristian/nightclaw && cd nightclaw
python3 -m nightclaw
```

No accounts. No API keys. No config. Your first report renders in seconds.

## Philosophy

- **Small enough to understand.** A handful of files, zero dependencies,
  stdlib Python. You can read the entire codebase before trusting it with
  anything — and you should.
- **Local-first, read-only.** NightClaw parses logs your tools already write.
  It makes no network calls and mutates nothing.
- **Honest numbers.** Every figure is reconstructable from your own logs, and
  the methodology prints next to the number. Where estimation is required,
  NightClaw is deliberately conservative: the utilization proxy *overstates*
  utilization, so any improvement you measure against it is understated.
  See [docs/methodology.md](docs/methodology.md).
- **Measurement before optimization.** The scheduler, the picker, the night
  shift — none of it means anything without a trustworthy baseline. Sensor
  first.
- **Headroom is allocated, not wasted.** The target is never 100% utilization.
  Your interactive morning session deserves a full tank; the metric that goes
  to zero is *waste*, not slack.
- **Data over dashboards.** `nightclaw json` exists so agents can consume the
  numbers directly — in the spirit of [AXI](https://axi.md) and
  [quota-axi](https://github.com/kunchenguid/axi): data-only, composable.

## What it measures

| Metric | Meaning |
|---|---|
| **Window coverage** | How many of the possible 5-hour rate-limit windows you actually used |
| **Utilization proxy** | Consumption vs. running every window at your own observed peak (a deliberate overstatement — see methodology) |
| **Idle** | Window slots that expired unused — the waste NightClaw exists to eliminate |
| **Overnight share** | Usage between 23:00–07:00 local. For most people: ~0%. That's the recoverable capacity |
| **Dollar value** | What your consumed tokens would cost at first-party API rates (cache writes 1.25×, reads 0.1× input) |

Currently reads **Claude Code** local session logs (`~/.claude/projects`,
`~/.config/claude/projects`, or `CLAUDE_CONFIG_DIR`). Multi-provider support
is on the roadmap.

## What leaves your machine

**Nothing.** NightClaw reads local JSONL files and prints to your terminal.
No telemetry, no analytics, no phone-home, no account. The `pipx install`
contacts GitHub to fetch the code; after that, NightClaw never touches the
network.

## Usage

```bash
nightclaw                     # visual report, last 7 days
nightclaw report --days 30    # longer lookback
nightclaw json                # machine-readable — pipe it to your agent
nightclaw doctor              # verify NightClaw can find your usage data
```

### The night shift

```bash
nightclaw backlog                 # your overnight task list (~/.config/nightclaw/backlog.md)
nightclaw goodnight --dry-run     # validate the plan: repos, budget, timeouts
nightclaw goodnight               # run it — confirmation required
nightclaw morning                 # digest: what ran, what it cost, how it exited
```

Tasks are one line each — `- [ ] repo: task description` — and only repos you
name in `~/.config/nightclaw/night.json`'s allowlist can be touched. The
night stops when the token budget is spent; every run is journaled.

**The safety model is opt-in by design.** There is *no default* permission
mode: before anything runs unattended you must explicitly write one into
`night.json` — `"default"` (only pre-approved tools), `"plan"` (read-only),
or `"acceptEdits"` (agents may edit allowlisted repos without per-action
approval — understand what that means before choosing it).
`"bypassPermissions"` is refused and always will be. Launching additionally
requires typed confirmation of the plan (or `--yes` after a `--dry-run`
review). On macOS, tasks run under `caffeinate` so sleep doesn't kill the
night.

Feed it to an agent:

```bash
nightclaw json | claude -p "Where am I wasting the most quota, and what
  should I schedule overnight to use it?"
```

Override pricing (e.g. introductory rates, partner pricing) in
`~/.config/nightclaw/pricing.json`:

```json
{ "claude-sonnet-5": { "input": 2.0, "output": 10.0 } }
```

## Customizing

NightClaw has exactly one config file (the pricing override above) and no
plans for more. Want different behavior — another night-hours definition, a
different report layout, a new metric? **Fork it and change the code.** The
codebase is small enough that Claude Code can make any change you can
describe:

```
"Change night hours to 22:00–06:00"
"Add a per-project breakdown to the report"
"Write an adapter that reads Codex CLI session logs"
```

[CLAUDE.md](CLAUDE.md) tells your agent how the code is laid out.

## Roadmap — the full harness

Measurement is phase 1. The goal is the closed loop: **telemetry → forecast →
schedule → policy-governed execution → morning report.**

- [x] **Sensor** — baseline utilization, coverage, heatmap, dollar value
- [x] **Night shift** — `goodnight` runs your backlog overnight: repo
      allowlist, hard token budget, per-task timeouts, journaled, and an
      opt-in-only permission model (v0.2)
- [x] **Morning digest** — `morning`: what ran, what it cost, how it exited (v0.2)
- [ ] **Full tank at 9am** — reserve forecasted morning headroom, spend the rest
- [ ] **Multi-provider ledger** — quota-axi integration; drain expiring quota first
- [ ] **Eval-informed picker** — route tasks to the model that measurably does
      them best per token

North-star metrics: **waste rate → 0**, utilization in the 80–90% band, value
per token gated on accepted output. See
[docs/architecture.md](docs/architecture.md) for the full design.

## Architecture

```
local JSONL logs ──▶ sensor (core.py) ──▶ report dict ──▶ render (ANSI) / json
                          │
                     pricing.py (API rates, user-overridable)
```

Key files:

- `nightclaw/core.py` — log discovery, event parsing/dedup, 5h window
  reconstruction, metric assembly. The only file with real logic.
- `nightclaw/pricing.py` — API-rate table + dollar estimation, override hook.
- `nightclaw/render.py` — ANSI report and heatmap. No logic, just presentation.
- `nightclaw/cli.py` — argument handling. Bare `nightclaw` shows live data,
  never help text.

## Contributing

**Don't add features. Add sensors.** The highest-value contribution is a
provider adapter — a function that reads another tool's local logs (Codex
CLI, Gemini CLI, Cursor, Kimi CLI, ...) and yields the same
`(timestamp, usage, model)` events `core.py` already consumes. One adapter ≈
one focused PR. Report-layout opinions and niche metrics belong in your fork;
that's what forks are for.

## Requirements

- Python 3.9+ (stdlib only, no dependencies)
- Claude Code with local session logs (the default — if you've used it,
  they're already there)

## FAQ

**How accurate is the window reconstruction?**
Same heuristics the established monitors (ccusage and friends) use: rolling
5-hour windows, start floored to the hour of first activity, events deduped
by message + request ID. It's a reconstruction, not the provider's ledger —
which is why every derived number is labeled and biased conservative.

**Why does the utilization proxy "overstate"? Isn't that backwards?**
The true limit of a window isn't published, so NightClaw uses your own
observed peak window as the denominator's stand-in. Your real entitlement is
at least that big — probably bigger — so real utilization is *lower* than
the proxy. Improvements measured against it are therefore understated, never
inflated. Full math in [docs/methodology.md](docs/methodology.md).

**Is the dollar figure what I'd have been billed?**
No — it's what the same tokens would cost at pay-per-token API rates: a
value-delivered measure, not a bill. Cached reads are priced at cache-read
rates, so it's not naively inflated either.

**Is it safe to run?**
Read the code — it's small enough that you actually can. It opens local files
read-only and prints. `nightclaw doctor` shows exactly which directories it
looks at.

**How do I uninstall?**
`pipx uninstall nightclaw`. It leaves nothing behind except
`~/.config/nightclaw/pricing.json` if you created one.

## License

MIT
