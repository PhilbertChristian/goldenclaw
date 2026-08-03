# Methodology

Every number NightClaw prints must be reconstructable from your local logs by
an independent reader. This document is the spec for that reconstruction, and
the honest accounting of where estimation enters and which direction it errs.

## Data source

Claude Code writes one JSONL file per session under `~/.claude/projects/` (or
`~/.config/claude/projects/`, or `$CLAUDE_CONFIG_DIR/projects`). Each
assistant record carries a `timestamp`, a `message.usage` block with four
token counters, and a `message.model`.

- **Deduplication:** records are deduped on `(message.id, requestId)` — the
  same convention ccusage uses — because streaming writes can log one API
  response across multiple lines.
- **Token total per event:** `input_tokens + output_tokens +
  cache_creation_input_tokens + cache_read_input_tokens`. Categories are also
  tracked separately (they price differently; see Pricing).

## Window reconstruction

Anthropic subscription rate limits operate on rolling 5-hour windows: a
window opens with your first message and closes exactly 5 hours later.
NightClaw reconstructs them from the event stream:

1. Sort events by timestamp.
2. The first event opens a window whose start is that timestamp **floored to
   the hour** (matching observed provider behavior and community convention).
3. Every event before `start + 5h` belongs to that window; the first event
   after it opens the next one.

This is a reconstruction, not the provider's ledger. Its known failure modes
(clock skew, multi-machine usage splitting logs) all *undercount* activity —
consistent with the conservative bias below.

## Metrics

Let `days` be the lookback period, `slots = days × 24 / 5` the number of
5-hour windows that fit in it, `used` the count of reconstructed windows, and
`peak` the largest token total observed in any single window.

| Metric | Definition | Bias |
|---|---|---|
| Coverage | `used / slots` | exact (given reconstruction) |
| Utilization proxy | `total_tokens / (peak × slots)` | **overstates** — see below |
| Idle | `1 − coverage` | understates waste if windows were partially used |
| Overnight share | tokens with local timestamp in 23:00–07:00 ÷ total | exact |

### Why the proxy overstates — and why that's the right direction

True utilization is `consumed / entitlement`, but the entitlement (tokens per
window) is not published. NightClaw substitutes your own observed `peak`
window. Since the provider allowed that consumption, the real per-window
limit is **at least** `peak` — so the substituted denominator is a lower
bound, and the resulting percentage is an **upper** bound on true
utilization.

The consequence: when you later claim "utilization went from X% to Y%," both
numbers were computed against the same conservative yardstick, and your true
improvement is at least as large as claimed. NightClaw never publishes a
number that flatters it.

(Weekly caps, which also exist, would make real capacity *smaller* than
`peak × slots` — a rare source of understatement. It's noted here for
completeness; the proxy remains labeled as a proxy for exactly this reason.)

## Pricing

The dollar figure answers: *what would these tokens cost at pay-per-token
API rates?* It is a value-delivered measure, not a reconstruction of your
bill.

- Rates: Anthropic first-party API prices per million tokens, prefix-matched
  by model ID (`nightclaw/pricing.py`).
- Cache writes bill at **1.25×** input rate, cache reads at **0.1×** — so a
  cache-heavy session is not naively inflated.
- Unknown models are listed as unpriced rather than guessed.
- Overrides: `~/.config/nightclaw/pricing.json` takes precedence, for
  introductory or partner pricing.

## The publishing rule

Anything published from NightClaw output follows three rules:

1. The number comes from a real run on real logs (`nightclaw json` output is
   the receipt).
2. The methodology (this document) is linked next to the claim.
3. Estimates are biased against the claim, never toward it.
