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
access he needs — nothing else runs without appearing in the transcript.
"""

import sys

from .agent import SYSTEM_PROMPT
from .render import BOLD, CYAN, DIM, GREEN, YELLOW, c


def _sniff_note(name, tool_input):
    if name == "Bash":
        cmd = str((tool_input or {}).get("command", ""))[:60]
        return "( sniffs — {} )".format(cmd) if cmd else "( sniffs around )"
    if name in ("Read", "Grep", "Glob"):
        return "( nose in the files )"
    return "( {} )".format(name.lower())


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
        return 0

    try:
        return asyncio.run(_session())
    except Exception as e:  # engine startup failures shouldn't strand the user
        print(c("  Max couldn't start his engine ({}).".format(
            e.__class__.__name__), YELLOW), file=sys.stderr)
        print(c("  Falling back to plain chat.", DIM), file=sys.stderr)
        return None
