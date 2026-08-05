"""`goldenclaw init` — Max initializes himself, conversationally.

A stranger's first five minutes should be Max explaining Max, not a README.
The flow: wake him, he introduces himself, then he walks the requirements in
order — agent CLI, sign-in, logs — re-sniffing after each fix instead of
failing, ends with the payoff (their first live tank reading), and offers to
install the one-word commands. Everything he reports is a real check; the
only file he writes is the shell rc block, and only after an explicit yes.
"""

import os
import shutil
import sys
from pathlib import Path

from . import boot, core
from .render import BOLD, CYAN, DIM, GREEN, YELLOW, c

ALIAS_MARKER = "# Max the Golden Token Retrieval"
ALIAS_BLOCK = """
# Max the Golden Token Retrieval 🐶
alias wakeup="goldenclaw wakeup" wake="goldenclaw wakeup"
alias goodnight="goldenclaw goodnight" morning="goldenclaw morning" backlog="goldenclaw backlog"
tokens() { goldenclaw report --days "${1:-7}"; }
left()   { goldenclaw quota "$@"; }
claw()   { if [ $# -eq 0 ]; then goldenclaw chat; else goldenclaw ask "$*"; fi; }
"""


def _say(text=""):
    print(text)


def _max(text):
    print("  " + c("Max:", BOLD, YELLOW) + " " + text)


def _ask(prompt):
    try:
        return input(c("  > ", CYAN)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "skip"


def _rc_file():
    shell = os.environ.get("SHELL", "")
    if shell.endswith("bash"):
        return Path.home() / ".bashrc"
    return Path.home() / ".zshrc"


def _aliases_installed(rc):
    try:
        text = rc.read_text()
    except OSError:
        return False
    return ALIAS_MARKER in text or "goldenclaw wakeup" in text


def _check_cli():
    return shutil.which("claude") is not None


def _check_credential():
    from . import live
    return live.available()


def _check_logs():
    dirs = core.find_log_dirs()
    return any(True for d in dirs for _ in d.rglob("*.jsonl"))


def _wait_and_recheck(check, fix_lines, skip_hint):
    """Tell the human the fix, then re-sniff until it works or they skip."""
    for line in fix_lines:
        _say(c("      " + line, DIM))
    while True:
        _say(c("    (press enter when done, or type 'skip')", DIM))
        if _ask("") == "skip":
            _max(skip_hint)
            return False
        if check():
            return True
        _max("still can't find it — one more try?")


def run():
    interactive = sys.stdin.isatty() and sys.stdout.isatty()

    boot.wake_animation()
    _say("  " + c("Max is up.", BOLD, YELLOW)
         + c("  🐾  Max the Golden Token Retrieval", DIM))
    _say()
    _max("hi. I fetch your AI token quota so you always know what's left.")
    _max("let me sniff around and get myself set up — three checks.")
    _say()

    # 1. The agent CLI — Max's nose.
    if _check_cli():
        _say("  " + c("✓", GREEN) + " Claude Code CLI found")
        cli_ok = True
    else:
        _say("  " + c("✗", YELLOW) + " Claude Code CLI not found")
        _max("I read the credential your Claude CLI stores — I never ask for "
             "keys myself. Install it and sign in:")
        cli_ok = (interactive and _wait_and_recheck(
            _check_cli,
            ["npm install -g @anthropic-ai/claude-code", "claude   # sign in once"],
            "no problem — run `max init` again when it's installed."))

    # 2. The stored sign-in.
    cred_ok = False
    if cli_ok:
        if _check_credential():
            _say("  " + c("✓", GREEN) + " signed in — credential found")
            cred_ok = True
        else:
            _say("  " + c("✗", YELLOW) + " no usable sign-in yet")
            _max("run `claude` once and sign in — then I can read your live quota.")
            cred_ok = (interactive and _wait_and_recheck(
                _check_credential, ["claude   # sign in, then come back"],
                "I'll work offline-only until then (history still works)."))

    # 3. Local usage history.
    if _check_logs():
        _say("  " + c("✓", GREEN) + " usage history found — I can show where your tokens went")
    else:
        _say("  " + c("·", YELLOW) + " no usage history yet "
             + c("(it appears as you use Claude Code — nothing to do)", DIM))

    # The payoff: their first live reading.
    if cred_ok:
        _say()
        try:
            from . import forecast, live
            snap = live.fetch()
            _max("here's your first sniff:")
            _say()
            session_left = None
            verdict = None
            from .render import RED, bar
            for w in snap["windows"]:
                left = w["percent_left"]
                color = GREEN if left > 50 else (YELLOW if left > 15 else RED)
                _say("    {:<18} ".format(w["label"])
                     + c(bar(left / 100, width=14), color) + " "
                     + c("{:.0f}% left".format(left), BOLD, color))
                if w["id"] == "five_hour":
                    session_left = left
                if w["id"] == "seven_day":
                    verdict = forecast.week_verdict(w)
            _say()
            _max(boot._max_quip(verdict, session_left))
        except Exception:
            _max("hm — couldn't fetch just now. `goldenclaw wakeup` will retry.")

    # The one-word commands.
    rc = _rc_file()
    _say()
    if _aliases_installed(rc):
        _say("  " + c("✓", GREEN) + " one-word commands already in " + rc.name)
    elif interactive:
        _max("want the one-word commands? `wakeup`, `tokens`, "
             "`goodnight`... I'd add a small block to {}. (y/n)".format(rc.name))
        if _ask("") in ("y", "yes"):
            with open(rc, "a") as fh:
                fh.write(ALIAS_BLOCK)
            _say("  " + c("✓", GREEN) + " added — open a new terminal to use them")
        else:
            _max("fair — `goldenclaw <command>` always works.")

    _say()
    _max("that's me set up. `goldenclaw` and I'll be sleeping; "
         "`wakeup` when you want the numbers. 🐾")
    _say()
    return 0
