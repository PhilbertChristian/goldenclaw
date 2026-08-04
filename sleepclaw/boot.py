"""Boot sequence — a sleepy dog, because the whole product is about nights.

Cosmetic only. It never invents a number: the status lines it prints are real
checks against the local environment, so the boot screen doubles as a
one-glance `doctor`. Honest even in the ASCII art.
"""

import sys
import time

from .render import BOLD, CYAN, DIM, GREEN, MAGENTA, RESET, YELLOW, c

DOG_SLEEPING = r"""
                                          z
                                     z
                                Z
        |\      _,,,---,,_
        /,`.-'`'    -.  ;-;;,_
       |,4-  ) )-,_..;\ (  `'-'
      '---''(_/--'  `-'\_)
"""

DOG_WAKING = r"""
                                    * ~ *
        |\      _,,,---,,_
        /,`.-'`'    -.  ;-;;,_
       |,4-  ) )-,_..;\ (  `'-'
      '---''(_/--'  `-'\_)
             ( stretch )
"""


def _line(text, delay=0.06, stream=None):
    stream = stream or sys.stdout
    stream.write(text + "\n")
    stream.flush()
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
    _line("  " + c("S L E E P C L A W", BOLD, MAGENTA)
          + c("   your subscription works the night shift", DIM), delay, stream)
    _line("", delay, stream)

    for label, ok, detail in _checks():
        mark = c("✓", GREEN) if ok else c("·", YELLOW)
        _line("  {} {:<12} {}".format(mark, label, c(detail, DIM)), delay, stream)

    _line("", delay, stream)
    _line(c("  sleepclaw quota    what's left right now (live)", DIM), delay, stream)
    _line(c("  sleepclaw          where it went, and what expired unused", DIM), delay, stream)
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
