"""ANSI terminal rendering for GoldenClaw reports.

AXI-flavored: running `goldenclaw` with no arguments shows live data, and every
report ends with concrete next steps. Colors respect NO_COLOR and non-TTYs.
"""

import os
import sys

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
RED = "\033[31m"

SHADES = " ░▒▓█"


def _use_color():
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def c(text, *codes):
    if not _use_color():
        return text
    return "".join(codes) + text + RESET


def fmt(n):
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def bar(frac, width=26):
    frac = max(0.0, min(1.0, frac))
    filled = round(frac * width)
    return "▐" + "█" * filled + "░" * (width - filled) + "▌"


def _heatmap_lines(heatmap):
    days = heatmap["days"]
    cells = heatmap["cells"]
    peak = max(cells.values(), default=0)
    lines = []
    header = "        " + "".join(f"{h:<2}" for h in range(0, 24, 2))
    lines.append(c(header, DIM))
    for day in days:
        row = ""
        for h in range(24):
            v = cells.get(f"{day}T{h:02d}", 0)
            if peak <= 0 or v == 0:
                ch = SHADES[0] if v == 0 else SHADES[1]
            else:
                idx = 1 + min(3, int((v / peak) * 4))
                ch = SHADES[idx]
            row += ch
        label = day[5:]  # MM-DD
        lines.append(f"  {c(label, DIM)} {c(row, CYAN)}")
    return lines


def render_report(r):
    lines = []
    p = lines.append
    p("")
    p(c("  🌙 GoldenClaw", BOLD, MAGENTA) + c(f" — token utilization, last {r['period_days']} days", DIM))
    p("")

    w = r["windows"]
    util = r["utilization_proxy_pct"] / 100
    cov = w["coverage_pct"] / 100
    waste = max(0.0, 1 - cov)
    util_pct = "{:.1f}%".format(r["utilization_proxy_pct"])
    win_note = "({} of {:.0f} possible 5h windows)".format(w["used"], w["possible_slots"])
    p("  " + c("Utilization", BOLD) + "  " + c(bar(util), YELLOW) + "  "
      + c(util_pct, BOLD, YELLOW) + " " + c("(proxy — true value is lower)", DIM))
    p("  " + c("Coverage   ", BOLD) + "  " + c(bar(cov), CYAN)
      + "  {:.1f}%  ".format(w["coverage_pct"]) + c(win_note, DIM))
    p("  " + c("Idle       ", BOLD) + "  " + c(bar(waste), DIM)
      + "  {:.1f}%  ".format(waste * 100) + c("window slots that expired unused", DIM))
    p("")

    p(c("  Usage heatmap", BOLD) + c("  (local time, hourly intensity)", DIM))
    lines.extend(_heatmap_lines(r["heatmap"]))
    p("")

    t = r["tokens"]
    p(c("  Totals", BOLD) + "  {} tokens · {} API responses".format(fmt(t["total"]), r["events"]))
    breakdown = "    input {} · output {} · cache write {} · cache read {}".format(
        fmt(t["input_tokens"]), fmt(t["output_tokens"]),
        fmt(t["cache_creation_input_tokens"]), fmt(t["cache_read_input_tokens"]))
    p(c(breakdown, DIM))
    night = "{:.1f}%".format(r["overnight"]["night_token_share_pct"])
    p("    overnight share ({} local): ".format(r["overnight"]["night_hours_local"]) + c(night, BOLD))
    p("")

    p(c("  Est. API-rate value consumed", BOLD) + "  "
      + c("${:,.2f}".format(r["est_api_value_usd"]), BOLD, GREEN))
    p(c("    what these tokens would cost pay-per-token — the value your subscription delivered", DIM))
    for m, usd in list(r["est_api_value_by_model"].items())[:5]:
        total = r["by_model"][m]["total"]
        p("    {:<34} {:>8}  ".format(m, fmt(total)) + c("${:,.2f}".format(usd), GREEN))
    if r["unpriced_models"]:
        p(c("    (unpriced: {})".format(", ".join(r["unpriced_models"][:3])), DIM))
    p("")

    p(c("  Next steps", BOLD))
    p(c("    goldenclaw report --days 30     longer lookback", DIM))
    p(c("    goldenclaw json                 machine-readable (pipe to your agent)", DIM))
    p(c("    goldenclaw doctor               verify data sources", DIM))
    p("")
    return "\n".join(lines)


def render_doctor(d):
    lines = ["", c("  🌙 GoldenClaw doctor", BOLD, MAGENTA), ""]
    if not d["log_dirs"]:
        lines.append(c("  ✗ No Claude Code log directories found.", YELLOW))
        lines.append(c("    Checked ~/.config/claude/projects and ~/.claude/projects.", DIM))
        lines.append(c("    Set CLAUDE_CONFIG_DIR if your logs live elsewhere.", DIM))
    else:
        for path in d["log_dirs"]:
            lines.append(f"  {c('✓', GREEN)} log dir: {path}")
        lines.append(f"  {c('✓' if d['files'] else '✗', GREEN if d['files'] else YELLOW)} "
                     f"session files: {d['files']}")
        lines.append(f"  {c('✓' if d['events_sampled'] else '✗', GREEN if d['events_sampled'] else YELLOW)} "
                     f"usage events readable: {d['events_sampled']}{'+' if d['events_sampled'] >= 500 else ''}")
    lines.append("")
    verdict = "ready — run `goldenclaw` for your report" if d["ok"] else "not ready — see above"
    lines.append("  " + (c(verdict, BOLD, GREEN) if d["ok"] else c(verdict, BOLD, YELLOW)))
    lines.append("")
    return "\n".join(lines)


def render_morning(journal_path, entries, report=None):
    lines = ["", c("  🌅 GoldenClaw morning report", BOLD, YELLOW)
             + c("  — " + journal_path.stem, DIM), ""]
    tasks = [e for e in entries if e.get("type") == "task"]
    stopped = any(e.get("type") == "budget_stop" for e in entries)
    if not tasks:
        lines.append(c("  No tasks ran last night.", DIM))
        lines.append("")
        return "\n".join(lines)

    ok = sum(1 for t in tasks if t.get("ok"))
    total_tokens = sum(int(t.get("tokens") or 0) for t in tasks)
    lines.append("  Tasks  {} run · {} ✓ · {} ✗{}".format(
        len(tasks), ok, len(tasks) - ok,
        "  (stopped at budget)" if stopped else ""))
    lines.append("  Tokens {} spent overnight".format(fmt(total_tokens)))
    lines.append("")
    for t in tasks:
        mark = c("✓", GREEN) if t.get("ok") else c("✗", YELLOW)
        lines.append("  {} [{}] {}".format(mark, t.get("repo"), (t.get("prompt") or "")[:70]))
        lines.append(c("      {} tokens · exit {}".format(
            fmt(int(t.get("tokens") or 0)), t.get("exit_code")), DIM))
    lines.append("")
    if report:
        lines.append("  Utilization (7d)  "
                     + c("{:.1f}%".format(report["utilization_proxy_pct"]), BOLD, YELLOW)
                     + c("  ·  overnight share {:.1f}%".format(
                         report["overnight"]["night_token_share_pct"]), DIM))
        lines.append("")
    lines.append(c("  Full detail: {}".format(journal_path), DIM))
    lines.append("")
    return "\n".join(lines)


def _clock(hours):
    if hours is None:
        return "—"
    if hours < 1:
        return "{:.0f}m".format(hours * 60)
    if hours < 48:
        return "{:.0f}h".format(hours)
    return "{:.0f}d {:.0f}h".format(hours // 24, hours % 24)


def _pool_line(label, pct_left, detail, warn=None, measured=True):
    left = pct_left / 100
    color = GREEN if left > .5 else (YELLOW if left > .15 else RED)
    mark = "" if measured else c("  ~", DIM)
    out = ["  " + c("{:<20}".format(label), BOLD) + c(bar(left), color)
           + "  " + c("{:.0f}% left".format(pct_left), BOLD, color) + mark]
    if detail:
        out.append(c(detail, DIM))
    if warn:
        out.append(c("    ⚠ " + warn, YELLOW))
    return out


def _reset_clock(iso):
    if not iso:
        return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    hours = (dt - datetime.now(timezone.utc)).total_seconds() / 3600
    return _clock(hours) if hours > 0 else "now"


def _live_lines(live):
    lines = []
    plan = (" · " + live["plan"].upper()) if live.get("plan") else ""
    lines.append(c("  CLAUDE", BOLD) + c("   live from your account" + plan, DIM))
    for w in live["windows"]:
        left = w["percent_left"] / 100
        color = GREEN if left > .5 else (YELLOW if left > .15 else RED)
        lines.append("  " + c("{:<20}".format(w["label"]), BOLD) + c(bar(left), color)
                     + "  " + c("{:.0f}% left".format(w["percent_left"]), BOLD, color))
        reset = _reset_clock(w.get("resets_at"))
        detail = "    {:.0f}% used".format(w["percent_used"])
        if reset:
            detail += " · resets in {}".format(reset)
        lines.append(c(detail, DIM))
    extra = live.get("extra_usage")
    if extra:
        lines.append(c("    extra usage: {} / {} {}".format(
            extra.get("used_credits"), extra.get("monthly_limit"),
            extra.get("currency") or ""), DIM))
    return lines


def render_quota(s):
    lines = ["", c("  🌙 GoldenClaw", BOLD, MAGENTA) + c("  — live quota", DIM), ""]
    provs = s.get("providers", {})
    claude = provs.get("claude", {})
    live = s.get("live")

    if live:
        lines.extend(_live_lines(live))
        lines.append("")
    else:
        err = s.get("live_error")
        if err:
            lines.append(c("  Live quota unavailable — " + err["message"], YELLOW))
            lines.append("")
        sess = claude.get("session")
        if sess and sess.get("active"):
            lines.append("  " + c("Session (5h)", BOLD)
                         + "  resets in {}".format(_clock(sess["minutes_left"] / 60))
                         + c("  ·  {} tokens this window".format(fmt(sess["used_tokens"])), DIM))
            lines.append("")
        if claude.get("calibrated"):
            lines.append(c("  CLAUDE", BOLD) + c("   estimated from calibration (offline)", DIM))
            for pool in claude["pools"].values():
                detail = "    ~${:.0f} of ~${:.0f} used · burn ${:.1f}/h · runway {}".format(
                    pool["used_units"], pool["cap_units"],
                    pool["burn_units_per_hour"], _clock(pool["runway_hours"]))
                warn = ("at this burn rate you run out before the reset"
                        if pool["exhausts_before_reset"] else None)
                lines.extend(_pool_line(pool["label"], pool["percent_left"], detail, warn))
            lines.append("")

    manuals = [p for k, p in provs.items()
               if k != "claude" and p.get("kind") == "manual"]
    if manuals:
        lines.append(c("  TRANSCRIBED", BOLD)
                     + c("   readings you entered — not measured", DIM))
        for p in manuals:
            tag = "  [{}]".format(p["plan"]) if p.get("plan") else ""
            if p["reset_passed"]:
                lines.append("  " + c("{:<20}".format(p["label"] + tag), BOLD)
                             + c("reset has passed — re-read the panel", DIM))
                continue
            detail = "    read {} ago · resets {} · in {}".format(
                _clock(p["reading_age_hours"]), p["resets_at_human"],
                _clock(p["hours_until_reset"]))
            warn = ("this reading is {} old — treat as indicative only".format(
                _clock(p["reading_age_hours"])) if p["stale"] else None)
            lines.extend(_pool_line(p["label"] + tag, p["percent_left"],
                                    detail, warn, measured=False))
        lines.append("")

    if live:
        lines.append(c("  These are your provider's own numbers, fetched with the", DIM))
        lines.append(c("  credential the Claude CLI already stores. Nothing is estimated.", DIM))
    lines.append("")
    lines.append(c("  Next steps", BOLD))
    lines.append(c("    goldenclaw            historical utilization & waste", DIM))
    lines.append(c("    goldenclaw quota --offline    skip the network call", DIM))
    lines.append(c("    claw how much is left        ask in plain English", DIM))
    lines.append("")
    return "\n".join(lines)


def render_menubar(s):
    """SwiftBar / xbar plugin format: title line, ---, then dropdown rows."""
    provs = s.get("providers", {})
    tight = s.get("tightest")
    out = []

    if tight:
        suffix = "" if tight.get("measured") else "~"
        out.append("🌙 {:.0f}%{}".format(tight["percent_left"], suffix))
    else:
        out.append("🌙 —")
    out.append("---")

    claude = provs.get("claude", {})
    sess = claude.get("session")
    if sess and sess.get("active"):
        out.append("Session resets in {} | color=#888888".format(
            _clock(sess["minutes_left"] / 60)))

    if claude.get("calibrated"):
        out.append("Claude | color=#ffffff")
        for pool in claude["pools"].values():
            color = ("#4caf50" if pool["percent_left"] > 50
                     else "#f5c451" if pool["percent_left"] > 15 else "#e05252")
            out.append("--{}  {:.0f}% left | color={}".format(
                pool["label"].replace("Weekly · ", ""), pool["percent_left"], color))
            out.append("----${:.0f} of ${:.0f} · burn ${:.1f}/h · runway {} | color=#888888".format(
                pool["used_units"], pool["cap_units"],
                pool["burn_units_per_hour"], _clock(pool["runway_hours"])))
        out.append("--resets in {} | color=#888888".format(
            _clock(claude["hours_until_reset"])))
    else:
        out.append("Claude — not calibrated | color=#f5c451")

    for name, p in provs.items():
        if name == "claude" or p.get("kind") != "manual":
            continue
        tag = " [{}]".format(p["plan"]) if p.get("plan") else ""
        if p["reset_passed"]:
            out.append("{}{} — reset passed | color=#888888".format(p["label"], tag))
            continue
        color = ("#4caf50" if p["percent_left"] > 50
                 else "#f5c451" if p["percent_left"] > 15 else "#e05252")
        out.append("{}{}  ~{:.0f}% left | color={}".format(
            p["label"], tag, p["percent_left"], color))
        out.append("--read {} ago · resets in {} | color=#888888".format(
            _clock(p["reading_age_hours"]), _clock(p["hours_until_reset"])))

    out.append("---")
    out.append("~ = transcribed reading, not measured | color=#888888")
    out.append("Refresh | refresh=true")
    return "\n".join(out)
