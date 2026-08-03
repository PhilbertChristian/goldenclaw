# NightClaw — Architecture & Design

> Phase 1 (the sensor) is built — see the repo root. This document is the
> design for the full closed loop. Metric definitions live in
> [methodology.md](methodology.md).

## Thesis

LLM subscriptions are pre-paid, perishable capacity with opaque limits and
rolling reset semantics. Nobody manages them like capacity. Monitors exist
(ccusage, Claude-Code-Usage-Monitor, quota-axi, SessionWatcher) but they are
all read-only. NightClaw closes the loop: **telemetry → forecast → schedule
→ policy-governed execution → report**. The North-Star metric is token
utilization; the primary objective is driving *waste* (expired unused
quota) toward zero without touching reserved interactive headroom.

## Architecture

```
                ┌─────────────────────────────────────────────┐
                │              NightClaw core                  │
  local JSONL ─▶│ sensor ─▶ capacity ledger ─▶ scheduler       │─▶ NanoClaw agents
  quota-axi ───▶│              ▲                  │            │   (containers)
                │            picker ◀── eval scores │           │
  backlog ─────▶│              ▲                  ▼            │─▶ morning digest
  (WhatsApp)    │           policy engine      trace store     │   (WhatsApp)
                └─────────────────────────────────────────────┘
```

### Sensor (phase 1 — built)

- Parses Claude Code JSONL (`~/.claude/projects`, `~/.config/claude/projects`,
  `CLAUDE_CONFIG_DIR`), dedupes on `(message.id, requestId)`.
- Rebuilds 5h windows: start floored to the hour of first activity; next
  event past `start+5h` opens a new window.
- Reports: token totals by category, window coverage, peak/avg window,
  utilization proxy, overnight share.

### Capacity ledger (phase 4)

Normalized per-provider record: `{provider, window_kind (rolling5h | daily |
weekly), observed_ceiling, confidence, headroom, runway, expires_at}`.
Entitlements are not published, so ceilings are *estimated* from observed
maxima and rate-limit events; confidence tightens over time. Expiry
pressure = headroom that will be forfeited at the next reset if unspent —
the scheduler spends high-pressure capacity first.

Multi-provider data comes from `quota-axi --json` (Claude, Codex, Cursor,
Copilot, Grok) rather than reimplementing per-provider parsers.

### Picker (phase 4)

Score = capability_fit × capacity_economics × policy_gate.

- **Capability fit**: per task category (tests, refactor, triage, docs), a
  small eval suite runs periodically against each available model;
  routing uses measured scores, not vibes.
- **Capacity economics**: expiry pressure first, then runway.
- **Policy gate** (hard constraints): per-repo provider allowlists (data
  governance), secret-scoping, per-night budget caps.

### Scheduler (phase 2/4)

- Backlog items: `{task, repo, category, est_tokens, value, constraints}`.
- Bin-pack into upcoming windows across providers; objective: minimize
  forfeited quota subject to (a) morning reserve per provider ("full tank
  at 9am": forecast next-morning interactive burn from history, reserve
  it), (b) budget caps, (c) policy gates.
- Failure handling: on mid-task rate limit, checkpoint a **handoff
  artifact** (task brief, progress notes, next steps, verification state)
  and resume on the provider with runway. Context does not transfer;
  the artifact is the contract.

### Guarded execution (phase 2)

NanoClaw containers, allowlisted repos/tools for unattended runs, every
turn traced (task, model, tokens, cost, outcome). PRs only open after
eval gates pass — `no-mistakes` for unattended agents.

### Digest (phase 3)

Morning WhatsApp message: tasks run, tokens/cost by provider, waste
avoided, quota state and tank level, PRs awaiting review, guardrail fires.

## Metric definitions

- **Waste rate** = forfeited_tokens / estimated_entitlement per period.
- **Utilization** = consumed / estimated_entitlement. Target band 80–90%;
  reserved headroom counts as allocated.
- **Value per token** = eval-gated accepted output units / tokens. Guards
  against Goodhart (burning tokens to pump utilization).
- Baseline proxy (phase 1) uses `total / (peak_window × possible_slots)` —
  denominator is a lower bound, so the proxy overstates true utilization;
  published improvements are therefore conservative.

## Content plan (honest-numbers rule)

1. Baseline post: methodology + real measured numbers from own logs.
2. Before/after post: only after NightClaw has actually run for a week,
   with reproducible receipts (`baseline.py --json` output committed).
3. User results: only real beta users, with permission.

No projected, simulated, or invented figures are ever published as results.
