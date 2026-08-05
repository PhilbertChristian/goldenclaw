"""Max's own REPL — the Agent SDK skin.

Typing `max` used to hand you over to Claude Code's UI wearing a persona.
This is the NanoClaw-style upgrade: the same engine imported as a library
(claude-agent-sdk), returning structured messages that WE render — Max's
prompt, Max's colors, Max sniffing between tool calls. The conversation
persists across turns in one session.

The SDK is an *optional* dependency, keeping the core's zero-dependency rule
intact: `pipx inject goldenclaw claude-agent-sdk`. Without it, `max` falls
back to the subprocess chat and says how to upgrade.

Same iron rule as everywhere: Max's numbers come from running the sensor.
The REPL pre-approves exactly the goldenclaw commands and read-only file
access he needs — his tool surface is locked down, and his working noises are dog\nthoughts rather than command dumps.
"""

import sys

from .agent import SYSTEM_PROMPT
from .render import BOLD, CYAN, DIM, GREEN, YELLOW, c


# What Max "says" while working. Rotated in order, never repeated back to
# back — the raw commands stay out of sight (his tool surface is locked to
# goldenclaw + read-only access, so there's nothing scary to hide).
SNIFF_LINES = [
    "( sniffing for tokens… )",
    "( where did I bury my claws again? )",
    "( digging through the logs… )",
    "( nose to the ground… )",
    "( following the scent… )",
    "( pawing at the numbers… )",
    "( checking behind the couch… )",
    "( rrrf. one sec. )",
    "( I smell tokens. definitely tokens. )",
    "( circling three times before starting… )",
    "( head tilt… processing… )",
    "( chasing the decimal point… )",
    "( who's a good ledger? I'm a good ledger. )",
    "( ears up. something's in the cache… )",
    "( zoomies through the data… )",
    "( wait. was that a squirrel? no — focus. )",
    "( fetching. actual fetching. )",
    "( snuffling under the API… )",
    "( tail wagging at compute speed… )",
    "( almost got it… it rolled under the fridge )",
]
_sniff_i = 0


def _sniff_note(name, tool_input):
    global _sniff_i
    line = SNIFF_LINES[_sniff_i % len(SNIFF_LINES)]
    _sniff_i += 1
    return line


_TANK_WORDS = ("token", "quota", "left", "usage", "remaining", "tank", "fetch", "month", "week")


def _is_tank_ask(text):
    """A short ask about quota goes straight to the renderer — checking your
    tokens must never spend tokens, even mid-conversation."""
    low = text.lower()
    return len(low) <= 70 and any(w in low for w in _TANK_WORDS)


def _show_tank(days=7):
    """The full breakdown — plan, every live window, this week by model."""
    from datetime import datetime, timezone

    from . import boot, core, forecast, live
    from .render import GREEN, RED, bar, fmt

    try:
        snap = live.fetch()
    except Exception:
        return False
    print(c("        " + _sniff_note("tank", None), DIM))
    session_left = None
    verdict = None
    plan = (" · " + snap["plan"].upper() + " plan") if snap.get("plan") else ""
    print(c("  Max › ", BOLD, YELLOW) + c("CLAUDE" + plan, BOLD))
    for w in snap["windows"]:
        left = w["percent_left"]
        color = GREEN if left > 50 else (YELLOW if left > 15 else RED)
        reset = ""
        if w.get("resets_at"):
            try:
                dt = datetime.fromisoformat(w["resets_at"].replace("Z", "+00:00"))
                hours = (dt - datetime.now(timezone.utc)).total_seconds() / 3600
                if hours >= 1:
                    reset = " · resets in {:.0f}h".format(hours)
                elif hours > 0:
                    reset = " · resets in {:.0f}m".format(hours * 60)
            except ValueError:
                pass
        usd = ""
        if w["id"] == "seven_day":
            from .boot import _weekly_cap_usd
            cap = _weekly_cap_usd()
            if cap:
                usd = " · ≈ ${:.0f} of value left".format(cap * left / 100)
        print("        {:<18} ".format(w["label"])
              + c(bar(left / 100, width=14), color) + " "
              + c("{:.0f}% left".format(left), BOLD, color) + c(usd + reset, DIM))
        if w["id"] == "five_hour":
            session_left = left
        if w["id"] == "seven_day":
            verdict = forecast.week_verdict(w)

    rep = core.assemble(days=days)
    if rep and rep.get("est_api_value_by_model"):
        period = "this week" if days <= 7 else "this month" if days <= 31 else "last {} days".format(days)
        print()
        print(c("        {}, by model:".format(period), BOLD))
        for model, usd_v in list(rep["est_api_value_by_model"].items())[:5]:
            tokens = rep["by_model"][model]["total"]
            print("          {:<26} {:>8}   ".format(model, fmt(tokens))
                  + c("${:,.2f}".format(usd_v), GREEN))
        print(c("          total ${:,.2f} · {} tokens".format(
            rep["est_api_value_usd"], fmt(rep["tokens"]["total"])), DIM))

    print()
    print("        " + boot._max_quip(verdict, session_left))
    return True


def run(model=None):
    """Returns an exit code, or None when the SDK isn't installed."""
    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            TextBlock,
            ToolUseBlock,
        )
    except ImportError:
        return None

    import asyncio

    from . import boot

    async def _session():
        options = ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            allowed_tools=["Bash(goldenclaw:*)", "Bash(max:*)", "Read", "Grep", "Glob"],
            model=model,
        )
        async with ClaudeSDKClient(options=options) as client:
            for row in boot.DOG_SITTING.split("\n"):
                print(c("  " + row, YELLOW))
            print()
            print("  " + c("Max is listening.", BOLD, YELLOW)
                  + c("  ask about your tokens · `exit` to leave", DIM))
            print()
            while True:
                try:
                    user = input(c("  you › ", CYAN)).strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if user.lower() in ("exit", "quit", "q", "bye"):
                    break
                if not user:
                    continue
                if _is_tank_ask(user):
                    days = 30 if ("month" in user.lower() or "30" in user) else 7
                    if _show_tank(days=days):
                        print()
                        continue
                await client.query(user)
                first_text = True
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock) and block.text.strip():
                                label = c("  Max › ", BOLD, YELLOW) if first_text else "        "
                                first_text = False
                                lines = block.text.strip().split("\n")
                                print(label + lines[0])
                                for line in lines[1:]:
                                    print("        " + line)
                            elif isinstance(block, ToolUseBlock):
                                print(c("        " + _sniff_note(block.name, block.input), DIM))
                print()
            print(c("  ( Max curls back up )", DIM))
            print()
            boot.banner()
        return 0

    try:
        return asyncio.run(_session())
    except Exception as e:  # engine startup failures shouldn't strand the user
        print(c("  Max couldn't start his engine ({}).".format(
            e.__class__.__name__), YELLOW), file=sys.stderr)
        print(c("  Falling back to plain chat.", DIM), file=sys.stderr)
        return None
