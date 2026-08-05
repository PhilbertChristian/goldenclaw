"""The 9pm ritual — wake Max, review the day, close down, hold the fort.

Interactive flow (TTY):
  1. Max wakes (animation)
  2. Today's review — what you used today, in tokens and API-rate value
  3. Budget check — live quota, plus Max's pace verdict for the week
  4. "What should I fetch before you sleep?" — queue tasks, one per line
  5. Cost estimate (from real past runs only) + token budget for the night
  6. Final confirmation, then the existing guarded night runner takes over

Non-interactive (`--yes`, `--dry-run`, or piped): falls back to the plain
backlog-file flow so scripts and cron keep working.

Max's rules: he never invents a number, he labels every estimate with its
basis, and on a SHORTFALL verdict he refuses to spend at all — a user on a
tight plan must never wake up to an empty tank.
"""

import sys
from datetime import datetime, time as dtime, timezone

from . import boot, core, forecast, night, pricing, quota
from .render import BOLD, CYAN, DIM, GREEN, RED, YELLOW, c, fmt


def _say(text=""):
    print(text)


def _max_says(text):
    print("  " + c("Max:", BOLD, YELLOW) + " " + text)


def _today_review():
    """What today actually cost — from local logs, since local midnight."""
    dirs = core.find_log_dirs()
    local_midnight = datetime.combine(datetime.now().date(), dtime.min).astimezone()
    since = local_midnight.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)

    tokens = 0
    by_model = {}
    for when, usage, model in core.iter_events(dirs):
        if when >= since:
            t = core.event_tokens(usage)
            tokens += t
            mt = by_model.setdefault(model, dict.fromkeys(core.TOKEN_FIELDS, 0))
            for f in core.TOKEN_FIELDS:
                mt[f] += int(usage.get(f) or 0)
    value, _, _ = pricing.estimate_cost(by_model)
    return {"tokens": tokens, "value_usd": value}


def _live_snapshot():
    from . import live
    try:
        return live.fetch(), None
    except live.LiveUnavailable as e:
        return None, str(e)


def _week_window(snapshot):
    if not snapshot:
        return None
    for w in snapshot["windows"]:
        if w["id"] == "seven_day":
            return w
    return None


def _print_budget(snapshot, err):
    if snapshot is None:
        _say(c("  (live budget unavailable — {})".format(err), DIM))
        return
    _say(c("  Max sniffed for tokens:", BOLD))
    for w in snapshot["windows"]:
        left = w["percent_left"] / 100
        color = GREEN if left > .5 else (YELLOW if left > .15 else RED)
        reset = _reset_phrase(w.get("resets_at"))
        _say("    {:<18} ".format(w["label"]) + c("{:.0f}% left".format(w["percent_left"]), BOLD, color)
             + c(" · {}".format(reset) if reset else "", DIM))


def _reset_phrase(iso):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    hours = (dt - datetime.now(timezone.utc)).total_seconds() / 3600
    if hours <= 0:
        return "resetting now"
    if hours < 1:
        return "resets in {:.0f}m".format(hours * 60)
    if hours < 48:
        return "resets in {:.0f}h".format(hours)
    return "resets in {:.0f}d {:.0f}h".format(hours // 24, hours % 24)


def _print_verdict(verdict):
    if verdict is None:
        return
    if verdict["verdict"] == forecast.SHORTFALL:
        _max_says(c("🔴 heads up — at this week's average pace you hit the wall in "
                    "~{}h, before the reset.".format(verdict["hours_to_wall"]), RED)
                  + c(" I won't spend anything tonight.", DIM))
    elif verdict["verdict"] == forecast.WASTE:
        _max_says(c("🟡 at this week's average pace, ~{:.0f}% of your weekly quota "
                    "expires unused at the reset.".format(verdict["projected_unused_pct"]), YELLOW)
                  + " That's the part I can put to work.")
    else:
        _max_says(c("🟢 you're on pace for the week. Nothing urgent.", GREEN))
    _say(c("       ({})".format(verdict["basis"]), DIM))


def _collect_tasks(cfg):
    repos = sorted((cfg.get("repos") or {}).keys())
    _say("")
    _max_says("What should I fetch before you sleep?")
    _say(c("  One per line, `repo: task`. Empty line when you're done."
           " Repos I may touch: {}".format(", ".join(repos) if repos else
           "(none yet — add some to night.json)"), DIM))
    tasks = []
    while True:
        try:
            line = input(c("  > ", CYAN)).strip()
        except EOFError:
            break
        if not line:
            break
        if ":" not in line:
            _say(c("    (format is `repo: task` — try again)", DIM))
            continue
        repo = line.split(":", 1)[0].strip()
        if repos and repo not in repos:
            _say(c("    ('{}' isn't in the allowlist: {})".format(repo, ", ".join(repos)), DIM))
            continue
        tasks.append(line)
    return tasks


def _append_to_backlog(tasks):
    night._ensure_config()
    text = night.BACKLOG.read_text()
    if not text.endswith("\n"):
        text += "\n"
    for t in tasks:
        text += "- [ ] {}\n".format(t)
    night.BACKLOG.write_text(text)


def _print_estimate(n_tasks):
    est = forecast.estimate_tasks(n_tasks, night.NIGHTS_DIR)
    if est is None:
        _max_says("I haven't run enough nights to estimate cost yet — "
                  "the token budget is the only cap tonight.")
        return
    _max_says("cost guess for {} task(s): ~{} tokens".format(n_tasks, fmt(est["tonight_median"]))
              + c(" (past tasks ran {}–{}, median {})".format(
                  fmt(est["per_task_low"]), fmt(est["per_task_high"]),
                  fmt(est["per_task_median"])), DIM))
    _say(c("       ({})".format(est["basis"]), DIM))


def _parse_tokens(raw):
    raw = raw.strip().upper().replace(",", "")
    if not raw:
        return None
    mult = 1
    if raw.endswith("M"):
        mult, raw = 1_000_000, raw[:-1]
    elif raw.endswith("K"):
        mult, raw = 1_000, raw[:-1]
    try:
        return int(float(raw) * mult)
    except ValueError:
        return None


def _ask_budget(default_tokens):
    _max_says("how many tokens can I use tonight? "
              + c("[enter for {}]".format(fmt(default_tokens)), DIM))
    while True:
        try:
            raw = input(c("  > ", CYAN))
        except EOFError:
            return default_tokens
        if not raw.strip():
            return default_tokens
        parsed = _parse_tokens(raw)
        if parsed and parsed > 0:
            return parsed
        _say(c("    (a number, or shorthand like 25M / 500K)", DIM))


def goodnight(cfg, budget_override=None, dry_run=False, assume_yes=False):
    """The ritual. Interactive on a TTY; otherwise defers to the plain runner."""
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not (dry_run or assume_yes)

    if not interactive:
        boot.banner()
        return night.run_night(cfg, budget_override=budget_override,
                               dry_run=dry_run, assume_yes=assume_yes)

    boot.wake_animation()
    _say("  " + c("Max is up.", BOLD, YELLOW) + c("  golden retriever · night watch", DIM))
    _say("")

    today = _today_review()
    _say(c("  Today's review:", BOLD))
    _say("    {} tokens".format(fmt(today["tokens"]))
         + c(" (~${:.2f} at API rates)".format(today["value_usd"]), DIM))
    _say("")

    snapshot, err = _live_snapshot()
    _print_budget(snapshot, err)
    _say("")

    week = _week_window(snapshot)
    verdict = forecast.week_verdict(week) if week else None
    _print_verdict(verdict)

    mode = cfg.get("permission_mode")
    if not mode:
        _say("")
        _max_says("before I can work nights, you have to choose my permission "
                  "mode in {} — that choice is yours, in writing.".format(night.NIGHT_CONFIG))
        _say(c('    "plan" (read-only) · "default" (pre-approved tools) · '
               '"acceptEdits" (edit allowlisted repos unattended)', DIM))
        return 1

    if verdict and verdict["verdict"] == forecast.SHORTFALL:
        _say("")
        _max_says("quota's too tight to spend tonight. I'll just hold the fort — "
                  "see you in the morning. 🐾")
        return 0

    tasks = _collect_tasks(cfg)
    _, existing = night.parse_backlog()
    if not tasks and not existing:
        _say("")
        _max_says("nothing to fetch. I'll keep an eye on things — goodnight. 🐾")
        return 0
    if tasks:
        _append_to_backlog(tasks)
        _max_says("{} task(s) queued.".format(len(tasks)))

    _say("")
    _, all_tasks = night.parse_backlog()
    _print_estimate(len(all_tasks))
    _say("")

    budget = budget_override or _ask_budget(int(cfg["night_budget_tokens"]))
    _say("")
    return night.run_night(cfg, budget_override=budget, assume_yes=False)
