"""ANSI terminal rendering for NightClaw reports.

AXI-flavored: running `nightclaw` with no arguments shows live data, and every
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
    p(c("  🌙 NightClaw", BOLD, MAGENTA) + c(f" — token utilization, last {r['period_days']} days", DIM))
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
    p(c("    nightclaw report --days 30     longer lookback", DIM))
    p(c("    nightclaw json                 machine-readable (pipe to your agent)", DIM))
    p(c("    nightclaw doctor               verify data sources", DIM))
    p("")
    return "\n".join(lines)


def render_doctor(d):
    lines = ["", c("  🌙 NightClaw doctor", BOLD, MAGENTA), ""]
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
    verdict = "ready — run `nightclaw` for your report" if d["ok"] else "not ready — see above"
    lines.append("  " + (c(verdict, BOLD, GREEN) if d["ok"] else c(verdict, BOLD, YELLOW)))
    lines.append("")
    return "\n".join(lines)


def render_morning(journal_path, entries, report=None):
    lines = ["", c("  🌅 NightClaw morning report", BOLD, YELLOW)
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


def render_quota(s):
    lines = ["", c("  🌙 NightClaw", BOLD, MAGENTA) + c("  — live quota", DIM), ""]

    sess = s.get("session")
    if sess and sess.get("active"):
        lines.append("  " + c("Session (5h)", BOLD)
                     + "  resets in {}".format(_clock(sess["minutes_left"] / 60))
                     + c("  ·  {} tokens this window".format(fmt(sess["used_tokens"])), DIM))
        lines.append("")

    if not s.get("calibrated"):
        lines.append(c("  Remaining quota is not calibrated yet.", YELLOW))
        lines.append("")
        lines.append("  Your logs know what you " + c("consumed", BOLD)
                     + "; only the provider knows your " + c("entitlement", BOLD) + ".")
        lines.append("  Teach NightClaw yours once — open Claude's usage panel and run:")
        lines.append("")
        lines.append(c("    nightclaw calibrate --weekly 49 --fable 85 --resets \"Wed 3:00 PM\"", CYAN))
        lines.append("")
        lines.append(c("  From then on NightClaw tracks what's left, offline, with no credentials.", DIM))
        lines.append("")
        return "\n".join(lines)

    if s.get("stale"):
        lines.append(c("  ⚠ calibration is {} week(s) old — percentages drift; re-run "
                       "`nightclaw calibrate`".format(s["weeks_since_calibration"]), YELLOW))
        lines.append("")

    for pool in s["pools"].values():
        left = pool["percent_left"] / 100
        color = GREEN if left > .5 else (YELLOW if left > .15 else RED)
        lines.append("  " + c("{:<20}".format(pool["label"]), BOLD) + c(bar(left), color)
                     + "  " + c("{:.0f}% left".format(pool["percent_left"]), BOLD, color))
        detail = "    ~${:.0f} of ~${:.0f} used · burn ${:.1f}/h · runway {}".format(
            pool["used_units"], pool["cap_units"], pool["burn_units_per_hour"],
            _clock(pool["runway_hours"]))
        lines.append(c(detail, DIM))
        if pool["exhausts_before_reset"]:
            lines.append(c("    ⚠ at this burn rate you run out before the reset", YELLOW))
    lines.append("")

    resets = s.get("resets_at_human") or s["resets_at"][:16].replace("T", " ")
    lines.append("  Weekly reset  " + c(resets, BOLD)
                 + c("  ·  in {}".format(_clock(s["hours_until_reset"])), DIM))
    lines.append("")
    lines.append(c("  Units are cost-weighted (USD-equivalent at API rates), not raw", DIM))
    lines.append(c("  tokens — cache reads bill at ~0.1x and would distort a raw count.", DIM))
    lines.append("")
    lines.append(c("  Next steps", BOLD))
    lines.append(c("    nightclaw calibrate ...   re-sync with the panel (do this weekly)", DIM))
    lines.append(c("    claw how much is left     ask in plain English", DIM))
    lines.append("")
    return "\n".join(lines)
