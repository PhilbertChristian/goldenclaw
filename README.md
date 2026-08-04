# SleepClaw 🌙

**Stop paying for tokens you never use.**

```
  🌙 SleepClaw — token utilization, last 7 days

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

## Why I built SleepClaw

An AI subscription is perishable capacity. Every 5-hour window that resets
with unused quota is inventory that expired on the shelf — and nobody manages
it like capacity. Plenty of tools *monitor* usage; none of them answer the
question that actually matters: **how much of what I pay for do I actually
use, and what would it take to stop wasting the rest?**

So I measured mine. The answer was **under 9% window coverage, 0% overnight
usage** — more than 90% of paid capacity expiring unused, every week. If your
first baseline doesn't shock you, you're the exception.

SleepClaw is the sensor first, and eventually the whole loop: measure the
waste, then put the idle hours — mostly the ones you spend asleep — to work.

## Quick start

```bash
pipx install git+https://github.com/PhilbertChristian/sleepclaw
sleepclaw
```

Or without installing anything:

```bash
git clone https://github.com/PhilbertChristian/sleepclaw && cd sleepclaw
python3 -m sleepclaw
```

No accounts. No API keys. No config. Your first report renders in seconds.

## Philosophy

- **Small enough to understand.** A handful of files, zero dependencies,
  stdlib Python. You can read the entire codebase before trusting it with
  anything — and you should.
- **Local-first, read-only.** SleepClaw parses logs your tools already write
  and mutates nothing. Exactly one feature reaches the network — `quota`, which
  asks your provider for your own quota using the credential its CLI already
  stored. `--offline` disables even that.
- **Honest numbers.** Every figure is reconstructable from your own logs, and
  the methodology prints next to the number. Where estimation is required,
  SleepClaw is deliberately conservative: the utilization proxy *overstates*
  utilization, so any improvement you measure against it is understated.
  See [docs/methodology.md](docs/methodology.md).
- **Measurement before optimization.** The scheduler, the picker, the night
  shift — none of it means anything without a trustworthy baseline. Sensor
  first.
- **Headroom is allocated, not wasted.** The target is never 100% utilization.
  Your interactive morning session deserves a full tank; the metric that goes
  to zero is *waste*, not slack.
- **Data over dashboards.** `sleepclaw json` exists so agents can consume the
  numbers directly — in the spirit of [AXI](https://axi.md) and
  [quota-axi](https://github.com/kunchenguid/axi): data-only, composable.

## What it measures

| Metric | Meaning |
|---|---|
| **Window coverage** | How many of the possible 5-hour rate-limit windows you actually used |
| **Utilization proxy** | Consumption vs. running every window at your own observed peak (a deliberate overstatement — see methodology) |
| **Idle** | Window slots that expired unused — the waste SleepClaw exists to eliminate |
| **Overnight share** | Usage between 23:00–07:00 local. For most people: ~0%. That's the recoverable capacity |
| **Dollar value** | What your consumed tokens would cost at first-party API rates (cache writes 1.25×, reads 0.1× input) |

Currently reads **Claude Code** local session logs (`~/.claude/projects`,
`~/.config/claude/projects`, or `CLAUDE_CONFIG_DIR`). Multi-provider support
is on the roadmap.

## What leaves your machine

**One request, to your own provider.** `sleepclaw quota` sends your stored
Claude credential to `api.anthropic.com/api/oauth/usage` and reads back your
own quota percentages. That is the entire network surface.

No telemetry, no analytics, no phone-home, no account, and no third party ever
sees anything. Your logs, prompts, and token counts never leave the machine.
`sleepclaw quota --offline` and every other command are fully offline.

## Usage

```bash
sleepclaw boot                # wake the dog: banner + environment check
sleepclaw                     # visual report, last 7 days
sleepclaw report --days 30    # longer lookback
sleepclaw json                # machine-readable — pipe it to your agent
sleepclaw doctor              # verify SleepClaw can find your usage data
```

### How much is left? (live quota)

```bash
sleepclaw quota
```

```
  CLAUDE   live from your account · MAX
  session (5h)        ▐█████████████████████░░░░░▌  82% left
    18% used · resets in 9m
  week · all models   ▐████████████░░░░░░░░░░░░░░▌  46% left
    54% used · resets in 40h
```

**These are your provider's own numbers, not an estimate.** SleepClaw reads
the OAuth credential the Claude CLI already stores on your machine (macOS
Keychain, or `~/.claude/.credentials.json`) and asks Anthropic's own usage
endpoint — the same data behind `/usage`. Nothing is inferred.

This is the **only** part of SleepClaw that touches the network, and it only
ever talks to `api.anthropic.com`, with your own credential, about your own
account. The token is read in one module, never printed, never logged, never
written anywhere. Skip it entirely with `sleepclaw quota --offline`.

<details>
<summary>Offline fallback: calibration</summary>

Without a credential, SleepClaw can still estimate remaining quota. You read
your panel's percentages once and it back-solves your capacity from
consumption it measured independently over the same window:

```bash
sleepclaw calibrate --weekly 49 --fable 85 --resets "Wed 3:00 PM"
sleepclaw quota --offline
```

Other providers have no local telemetry at all, so they're transcribed
readings — stored with a timestamp and always shown with their age, so a
stale number can never pass for a live one:

```bash
sleepclaw calibrate --provider codex --used 66 --resets "Fri 9:00 AM" --plan PRO
```
</details>

### Just talk to it

In the NanoClaw spirit — no monitoring dashboard, ask the agent — SleepClaw
ships a conversation layer over the data:

```bash
sleepclaw ask "how's my utilization this month?"
sleepclaw chat        # full interactive session
```

`ask` launches a headless Claude Code session that is pre-approved to run
**only** `sleepclaw` commands — it answers from real sensor runs and can't
touch anything else without asking. `chat` is a full interactive session
where normal permission prompts apply, so you can also manage your backlog
conversationally ("queue up test-writing for the api repo tonight").
Requires the `claude` CLI.

### Meet Max 🐕 (experimental)

Max is a golden retriever who guards your token budget. The ritual: **wake
him before bed.**

```bash
sleepclaw goodnight
```

Max wakes up (there's an animation), reviews your day, checks your live
budget, and gives you a verdict at this week's average pace:

```
  Max is up.  golden retriever · night watch

  Today's review:
    39.0M tokens (~$49.09 at API rates)

  Max checked your budget:
    session (5h)       86% left · resets in 2h
    week · all models  42% left · resets in 23h

  Max: 🟡 at this week's average pace, ~33% of your weekly quota
       expires unused at the reset. That's the part I can put to work.
```

Then he asks **"What should I fetch before you sleep?"** — you queue tasks
one per line, he estimates the cost from your own past runs (no history
means no estimate, never an invented number), asks how many tokens he may
spend, and holds the fort overnight using the guarded runner below. In the
morning, `sleepclaw morning`: what ran, what it cost, and today's tank.

Max adapts to your plan. On a tight week he tells you when you'll hit the
wall — and **refuses to spend anything overnight**. On a loose week he tells
you what's about to expire unused. Same dog, opposite advice, both honest.

**The night shift is experimental**: the runner below works and is tested at
the seams, but it has not yet run a real production night. Treat it
accordingly.

### The night runner (what Max drives)

Tasks are one line each — `- [ ] repo: task description` — and only repos you
name in `~/.config/sleepclaw/night.json`'s allowlist can be touched. The
night stops when the token budget is spent — and between every task Max
re-checks your **live** weekly quota, stopping the moment it touches your
morning reserve (`weekly_reserve_pct`, default 15%). Every run is journaled.

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
sleepclaw json | claude -p "Where am I wasting the most quota, and what
  should I schedule overnight to use it?"
```

Override pricing (e.g. introductory rates, partner pricing) in
`~/.config/sleepclaw/pricing.json`:

```json
{ "claude-sonnet-5": { "input": 2.0, "output": 10.0 } }
```

## Customizing

SleepClaw has exactly one config file (the pricing override above) and no
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
- [ ] **Multi-provider ledger** (next) — quota-axi integration; drain expiring quota first
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

- `sleepclaw/core.py` — log discovery, event parsing/dedup, 5h window
  reconstruction, metric assembly. The only file with real logic.
- `sleepclaw/pricing.py` — API-rate table + dollar estimation, override hook.
- `sleepclaw/render.py` — ANSI report and heatmap. No logic, just presentation.
- `sleepclaw/cli.py` — argument handling. Bare `sleepclaw` shows live data,
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
The true limit of a window isn't published, so SleepClaw uses your own
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
read-only and prints. `sleepclaw doctor` shows exactly which directories it
looks at.

**How do I uninstall?**
`pipx uninstall sleepclaw`. It leaves nothing behind except
`~/.config/sleepclaw/pricing.json` if you created one.

## License

MIT
