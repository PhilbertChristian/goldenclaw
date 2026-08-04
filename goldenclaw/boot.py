"""Boot sequence — a sleepy dog, because the whole product is about nights.

Cosmetic only. It never invents a number: the status lines it prints are real
checks against the local environment, so the boot screen doubles as a
one-glance `doctor`. Honest even in the ASCII art.
"""

import sys
import time

from .render import BOLD, CYAN, DIM, GREEN, MAGENTA, RED, RESET, YELLOW, bar, c, fmt

DOG_SLEEPING = r"""
                                          z
                                     z
                                Z
        |\      _,,,---,,_
        /,`.-'`'    -.  ;-;;,_
       |,4-  ) )-,_..;\ (  `'-'
      '---''(_/--'  `-'\_)
           ( Max is sleeping )
"""

DOG_WAKING = r"""
                                    * ~ *
        |\__/,|   _,,,---,,_
        /,`.-'`'    -.  ;-;;,_
       |,4-  ) )-,_..;\ (  `'-'
      '---''(_/--'  `-'\_)
             ( stretch )
"""


DOG_SITTING = r"""
        |\__/,|   (`\
      _.|o o  |_   ) )
    -(((---(((--------
      ( Max wakes up )
"""


def wake_animation(stream=None, delay=0.55):
    """Max wakes up: sleeping -> stirring -> stretching, redrawn in place.
    Non-TTY streams get only the final frame (no cursor tricks in pipes)."""
    stream = stream or sys.stdout
    frames = [(DOG_SLEEPING, CYAN), (DOG_SITTING, YELLOW)]
    if not stream.isatty():
        for row in DOG_SITTING.strip("\n").split("\n"):
            stream.write("  " + row + "\n")
        stream.flush()
        return
    prev_height = 0
    for i, (art, color) in enumerate(frames):
        rows = art.strip("\n").split("\n")
        if prev_height:
            stream.write("\033[{}F\033[J".format(prev_height))
        for row in rows:
            stream.write(c("  " + row, color) + "\n")
        stream.flush()
        prev_height = len(rows)
        if i < len(frames) - 1:
            time.sleep(delay)
    stream.write("\n")
    stream.flush()


def _line(text, delay=0.06, stream=None):
    stream = stream or sys.stdout
    try:
        stream.write(text + "\n")
        stream.flush()
    except BrokenPipeError:
        # `goldenclaw boot | head` closes the pipe early; that is not an error.
        raise SystemExit(0)
    if delay and stream.isatty():
        time.sleep(delay)


def _checks():
    """Real environment checks — nothing here is decorative."""
    from . import core, live

    results = []
    dirs = core.find_log_dirs()
    files = sum(1 for d in dirs for _ in d.rglob("*.jsonl"))
    results.append(("local logs", bool(dirs and files),
                    "{} session files".format(files) if files else "none found"))
    results.append(("credential", live.available(),
                    "found" if live.available() else "run `claude` to sign in"))

    from . import providers
    store = providers.load_store()["providers"]
    extra = [k for k in store if k != "claude"]
    results.append(("providers", True,
                    "claude" + (" + " + ", ".join(extra) if extra else "")))
    return results


def sequence(stream=None, delay=0.06):
    stream = stream or sys.stdout
    _line("", delay, stream)
    for row in DOG_SLEEPING.strip("\n").split("\n"):
        _line(c("  " + row, CYAN), delay * 0.5, stream)
    _line("", delay, stream)
    _line("  " + c("G O L D E N C L A W", BOLD, MAGENTA)
          + c("   your subscription works the night shift", DIM), delay, stream)
    _line("", delay, stream)

    for label, ok, detail in _checks():
        mark = c("✓", GREEN) if ok else c("·", YELLOW)
        _line("  {} {:<12} {}".format(mark, label, c(detail, DIM)), delay, stream)

    _line("", delay, stream)
    _line(c("  goldenclaw quota    what's left right now (live)", DIM), delay, stream)
    _line(c("  goldenclaw          where it went, and what expired unused", DIM), delay, stream)
    _line(c("  goodnight          put the idle hours to work", DIM), delay, stream)
    _line("", 0, stream)


def banner(waking=False, stream=None):
    """Compact art for goodnight / morning."""
    stream = stream or sys.stdout
    art = DOG_WAKING if waking else DOG_SLEEPING
    for row in art.strip("\n").split("\n"):
        stream.write(c("  " + row, YELLOW if waking else CYAN) + "\n")
    stream.write("\n")
    stream.flush()


def _max_quip(verdict, session_left):
    """Max's one-liner — personality on top of REAL numbers, never instead of
    them. The quip is presentation; every figure in it comes from the data."""
    from . import forecast
    if verdict is None:
        return "fresh week — the bowl's full. 🐾"
    if verdict["verdict"] == forecast.SHORTFALL:
        return ("easy, chief — at this pace you hit the wall in ~{:.0f}h, "
                "before the reset. I'd slow down.".format(verdict["hours_to_wall"]))
    if verdict["verdict"] == forecast.WASTE:
        return ("plenty in the tank — but ~{:.0f}% of the week expires unused "
                "at this pace. throw me a bone tonight? (`goodnight`)".format(
                    verdict["projected_unused_pct"]))
    if session_left is not None and session_left < 15:
        return "on pace for the week — but this session's nearly out. short break? 🐾"
    return "right on pace. good human. 🐾"


def wakeup(stream=None, skip_sleep_frame=False):
    """The front door: wake Max, he tells you what's left. Fast, free, fun.

    No agent session is launched — checking your quota must never spend your
    quota. Max's numbers come from the live usage API; his commentary is
    keyed off the real forecast verdict.
    """
    import shutil as _sh

    from . import core, forecast

    stream = stream or sys.stdout
    if skip_sleep_frame:
        for row in DOG_SITTING.strip("\n").split("\n"):
            _line(c("  " + row, YELLOW), 0.02, stream)
        _line("", 0, stream)
    else:
        wake_animation(stream)
    _line("  " + c("Max is up.", BOLD, YELLOW) + c("  🐾  GoldenClaw", DIM), 0.05, stream)
    _line("", 0, stream)

    # What's left — the whole point.
    snap = None
    session_left = None
    verdict = None
    try:
        from . import live
        snap = live.fetch()
    except Exception:
        pass

    if snap:
        plan = ("  ·  " + snap["plan"].upper() + " plan") if snap.get("plan") else ""
        _line("  " + c("Max checked the tank" + plan + ":", BOLD), 0.04, stream)
        for w in snap["windows"]:
            left = w["percent_left"]
            color = GREEN if left > 50 else (YELLOW if left > 15 else RED)
            reset = ""
            if w.get("resets_at"):
                from datetime import datetime, timezone
                try:
                    dt = datetime.fromisoformat(w["resets_at"].replace("Z", "+00:00"))
                    hours = (dt - datetime.now(timezone.utc)).total_seconds() / 3600
                    if hours > 0:
                        reset = " · resets in {:.0f}h".format(hours) if hours >= 1 \
                            else " · resets in {:.0f}m".format(hours * 60)
                except ValueError:
                    pass
            _line("    {:<18} ".format(w["label"])
                  + c(bar(left / 100, width=14), color) + " "
                  + c("{:.0f}% left".format(left), BOLD, color)
                  + c(reset, DIM), 0.05, stream)
            if w["id"] == "five_hour":
                session_left = left
            if w["id"] == "seven_day":
                verdict = forecast.week_verdict(w)
        _line("", 0, stream)
        _line("  " + c("Max says:", BOLD, YELLOW) + " "
              + _max_quip(verdict, session_left), 0.05, stream)
    else:
        _line("  " + c("Max can't reach your quota.", YELLOW), 0, stream)
        if _sh.which("claude") is None:
            _line(c("    He reads the credential your Claude CLI stores — install", DIM), 0, stream)
            _line(c("    Claude Code and sign in once, then wake him again:", DIM), 0, stream)
            _line(c("      npm install -g @anthropic-ai/claude-code && claude", DIM), 0, stream)
        else:
            _line(c("    Sign in with `claude`, then wake him again.", DIM), 0, stream)

    # The week so far, per model — small print under the headline.
    rep = core.assemble(days=7)
    if rep and rep.get("est_api_value_by_model"):
        _line("", 0, stream)
        _line(c("  This week: {} tokens · ${:,.2f} at API rates".format(
            fmt(rep["tokens"]["total"]), rep["est_api_value_usd"]), DIM), 0.03, stream)
        for model, usd in list(rep["est_api_value_by_model"].items())[:4]:
            _line(c("    {:<26} {:>8}   ${:,.2f}".format(
                model, fmt(rep["by_model"][model]["total"]), usd), DIM), 0.02, stream)

    _line("", 0, stream)
    _line(c("  more: `max` talk to him · `tokens` history · `goodnight` night shift", DIM), 0, stream)
    _line("", 0, stream)
    return 0


def sleep_loop(stream=None):
    """Bare `goldenclaw`: Max sleeps in the terminal and WAITS. Typing
    `wakeup` (or `wake`) wakes him right there — one contained session, no
    bouncing back to the shell. Non-TTY prints the sleeping dog and exits,
    so pipes and scripts stay sane."""
    stream = stream or sys.stdout
    banner(stream=stream)
    if not (stream.isatty() and sys.stdin.isatty()):
        return 0
    while True:
        try:
            cmd = input(c("  > ", CYAN)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            stream.write("\n" + c("  ( Max sleeps on )", DIM) + "\n\n")
            return 0
        if cmd in ("wakeup", "wake", "wake up", "w"):
            stream.write("\n")
            return wakeup(stream=stream, skip_sleep_frame=True)
        if cmd in ("exit", "quit", "q"):
            stream.write(c("  ( Max sleeps on )", DIM) + "\n\n")
            return 0
        if not cmd:
            continue
        stream.write(c("  ( Max twitches an ear — try `wakeup` )", DIM) + "\n")
