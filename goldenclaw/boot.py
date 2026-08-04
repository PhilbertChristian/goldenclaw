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


DOG_STIRRING = r"""
                                     z
        |\      _,,,---,,_
        /,`.-'`'    -.  ;-;;,_
       |,4-  ) )-,_..;\ (  `'-'
      '---''(_/--'  `-'\_)
              ...mmh?
"""


DOG_SITTING = r"""
          .--.
         ( ^ ^\
          ) ᵕ  \_
         /       `-.
        |     ,--,  )
        (,___(   (,'
          ''    ''
"""


def wake_animation(stream=None, delay=0.55):
    """Max wakes up: sleeping -> stirring -> stretching, redrawn in place.
    Non-TTY streams get only the final frame (no cursor tricks in pipes)."""
    stream = stream or sys.stdout
    frames = [(DOG_SLEEPING, CYAN), (DOG_STIRRING, CYAN), (DOG_WAKING, YELLOW), (DOG_SITTING, YELLOW)]
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
