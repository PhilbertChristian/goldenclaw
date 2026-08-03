# NightClaw 🌙

**Stop paying for tokens you never use.**

Your AI subscription is perishable capacity: every 5-hour window that resets
with unused quota is inventory that expired on the shelf. NightClaw measures
your **real token utilization** from your own local logs — no accounts, no
API keys, no network calls — and shows you exactly how much of what you pay
for actually gets used, in tokens *and* dollars.

Most people's first baseline is a shock. Mine was **under 9% utilization**
with **0% overnight usage** — 90%+ of paid capacity expiring unused.

```
  🌙 NightClaw — token utilization, last 7 days

  Utilization  ▐█░░░░░░░░░░░░░░░░░░░░░░░░▌  5.2% (proxy — true value is lower)
  Coverage     ▐██░░░░░░░░░░░░░░░░░░░░░░░▌  8.9%  (3 of 34 possible 5h windows)
  Idle         ▐███████████████████████░░▌  91.1%  window slots that expired unused

  Usage heatmap  (local time, hourly intensity)
        00 02 04 06 08 10 12 14 16 18 20 22
  07-28     ░▒░
  07-29                 ░░▒█▓░
  ...

  Est. API-rate value consumed  $58.51
```

## Quick start

```bash
pipx install git+https://github.com/PhilbertChristian/nightclaw
nightclaw            # your report — no config, no arguments needed
```

Or without installing anything:

```bash
git clone https://github.com/PhilbertChristian/nightclaw && cd nightclaw
python3 -m nightclaw
```

Commands:

| Command | What it does |
|---|---|
| `nightclaw` | Visual utilization report (last 7 days) |
| `nightclaw report --days 30` | Longer lookback |
| `nightclaw json` | Machine-readable output — data-only, pipe it to your agent |
| `nightclaw doctor` | Verify NightClaw can find your usage data |

Currently reads **Claude Code** local session logs (`~/.claude/projects`,
`~/.config/claude/projects`, or `CLAUDE_CONFIG_DIR`). Multi-provider support
(via [quota-axi](https://github.com/kunchenguid/axi)) is on the roadmap.

## What it measures

- **Window coverage** — how many of the possible 5-hour rate-limit windows you
  actually used. Windows are reconstructed from your logs (start floored to
  the hour of first activity, same heuristics as ccusage).
- **Utilization proxy** — total consumption vs. running every possible window
  at your own observed peak. The denominator is a *lower bound* on your true
  entitlement, so this proxy **overstates** utilization — improvements you
  measure against it are conservative.
- **Overnight share** — how much runs from 23:00–07:00 local. For most people:
  approximately zero. That's the recoverable capacity.
- **Dollar value** — what your consumed tokens would cost at first-party API
  rates (cache writes 1.25×, cache reads 0.1× input). Override rates in
  `~/.config/nightclaw/pricing.json`.

## Honest numbers, always

Every figure NightClaw prints is reconstructable from your own local logs, and
the methodology is printed next to the number (`nightclaw json` includes it).
Nothing leaves your machine.

## Roadmap — the full harness

Measurement is phase 1. The goal is the closed loop: **telemetry → forecast →
schedule → policy-governed execution → morning report.**

- [x] **Sensor** — baseline utilization, coverage, heatmap, dollar value
- [ ] **Night shift** — a "goodnight" trigger (via [NanoClaw](https://github.com/qwibitai/nanoclaw))
      that runs your task backlog overnight with guardrails and budget caps
- [ ] **Morning digest** — what ran, what it cost, quota state, PRs to review
- [ ] **Full tank at 9am** — reserve forecasted morning headroom, spend the rest
- [ ] **Multi-provider ledger** — quota-axi integration; drain expiring quota first
- [ ] **Eval-informed picker** — route tasks to the model that measurably does
      them best per token

Metrics north star: **waste rate → 0**, utilization in the 80–90% band (never
100% — your interactive headroom is allocated, not wasted), and value per
token gated on accepted output.

## License

MIT
