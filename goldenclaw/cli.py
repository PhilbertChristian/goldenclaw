"""GoldenClaw CLI — boots from the terminal, shows live data by default."""

import argparse
import json
import sys

from . import __version__, core, render


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(
        prog="goldenclaw",
        description="Measure your AI subscription token utilization from local logs.",
    )
    parser.add_argument("--version", action="version", version="goldenclaw " + __version__)
    sub = parser.add_subparsers(dest="cmd")

    p_report = sub.add_parser("report", help="visual utilization report (default)")
    p_report.add_argument("--days", type=int, default=7, help="lookback period (default 7)")

    p_json = sub.add_parser("json", help="machine-readable report")
    p_json.add_argument("--days", type=int, default=7, help="lookback period (default 7)")

    sub.add_parser("doctor", help="verify GoldenClaw can find your usage data")
    sub.add_parser("boot", help="banner and environment check")
    sub.add_parser("wakeup", help="wake Max — he tells you what is left")
    sub.add_parser("init", help="Max sets himself up — checks, sign-in, one-word commands")

    p_quota = sub.add_parser("quota", help="live quota: how much is left, when it resets")
    p_quota.add_argument("--json", action="store_true", dest="as_json",
                         help="machine-readable")
    p_quota.add_argument("--offline", action="store_true",
                         help="skip the live usage API and use local data only")

    p_cal = sub.add_parser(
        "calibrate",
        help="teach GoldenClaw your entitlement from the provider's usage panel")
    p_cal.add_argument("--weekly", type=float, default=None,
                       help="percent used, all-models weekly pool (e.g. 49)")
    p_cal.add_argument("--fable", type=float, default=None,
                       help="percent used, Fable weekly pool")
    p_cal.add_argument("--opus", type=float, default=None,
                       help="percent used, Opus weekly pool")
    p_cal.add_argument("--resets", default=None,
                       help='weekly reset as shown in the panel, e.g. "Wed 3:00 PM"')
    p_cal.add_argument("--provider", default="claude",
                       help="provider to record (claude is measured; others are "
                            "transcribed readings)")
    p_cal.add_argument("--used", type=float, default=None,
                       help="percent used, for a transcribed (non-Claude) provider")
    p_cal.add_argument("--plan", default=None, help="plan label, e.g. PRO / MAX")

    p_mb = sub.add_parser("menubar", help="Max in the macOS menu bar")
    p_mb.add_argument("--install", action="store_true",
                      help="install the SwiftBar/xbar plugin")

    p_night = sub.add_parser("goodnight", help="run your backlog overnight, inside guardrails")
    p_night.add_argument("--dry-run", action="store_true", help="show the plan without running")
    p_night.add_argument("--budget", type=int, default=None, help="override night token budget")
    p_night.add_argument("--yes", action="store_true",
                         help="skip the confirmation prompt (after reviewing with --dry-run)")

    sub.add_parser("morning", help="digest of what ran last night")
    sub.add_parser("backlog", help="show the overnight task backlog")

    p_ask = sub.add_parser("ask", help="ask the GoldenClaw agent a question (one-shot)")
    p_ask.add_argument("question", nargs="+", help="your question, plain English")
    p_ask.add_argument("--model", default=None, help="model override for the agent")

    p_chat = sub.add_parser("chat", help="talk to the GoldenClaw agent interactively")
    p_chat.add_argument("--model", default=None, help="model override for the agent")

    # Bare `goldenclaw` shows exactly one thing: Max, asleep. Waking him
    # (`wakeup`) is what fetches the data. The report lives at `report`.
    if not argv:
        from . import boot
        return boot.sleep_loop() or 0
    args = parser.parse_args(argv)

    if args.cmd == "boot":
        from . import boot
        boot.sequence()
        return 0

    if args.cmd == "wakeup":
        from . import boot
        return boot.wakeup()

    if args.cmd == "init":
        from . import init
        return init.run()

    if args.cmd == "doctor":
        d = core.doctor()
        print(render.render_doctor(d))
        return 0 if d["ok"] else 1

    if args.cmd == "quota":
        from . import quota
        s = quota.state(allow_live=not args.offline)
        print(json.dumps(s, indent=2) if args.as_json else render.render_quota(s))
        return 0

    if args.cmd == "menubar":
        if args.install:
            from . import menubar
            return menubar.install()
        from . import quota
        print(render.render_menubar(quota.state()))
        return 0

    if args.cmd == "calibrate":
        from . import quota, providers

        if args.provider != "claude":
            if not providers.is_known(args.provider):
                print("Unknown provider '{}'. Known: {}".format(
                    args.provider, ", ".join(sorted(providers.PROVIDERS))),
                    file=sys.stderr)
                return 1
            if args.used is None or not args.resets:
                print("Transcribed providers need --used and --resets, e.g.\n"
                      '  goldenclaw calibrate --provider codex --used 66 '
                      '--resets "Fri 9:00 AM" --plan PRO',
                      file=sys.stderr)
                return 1
            try:
                providers.save_manual_reading(
                    args.provider, args.used, args.resets, args.plan)
            except ValueError as e:
                print("Failed: {}".format(e), file=sys.stderr)
                return 1
            print("\n  ✓ Recorded {} at {:.0f}% used.".format(
                providers.label(args.provider), args.used))
            print("    This is a transcribed reading, not a measurement — "
                  "GoldenClaw will\n    show its age so it can't pass for live data.\n")
            return 0

        pools = {k: v for k, v in (("weekly", args.weekly), ("fable", args.fable),
                                   ("opus", args.opus)) if v is not None}
        if not pools or not args.resets:
            print(
                "Open Claude Code's usage panel (/usage), then pass what it shows:\n"
                '  goldenclaw calibrate --weekly 49 --fable 85 --resets "Wed 3:00 PM"\n'
                "\nAt least one pool percentage and --resets are required.",
                file=sys.stderr)
            return 1
        try:
            data = quota.save_reading(pools, args.resets)
        except ValueError as e:
            print("Calibration failed: {}".format(e), file=sys.stderr)
            return 1
        print("\n  ✓ Calibrated against your panel reading.\n")
        for name, entry in data["pools"].items():
            if entry["cap_units"]:
                print("    {:<8} {:.0f}% used  →  weekly capacity ≈ ${:.0f} of "
                      "API-rate value".format(name, entry["percent_used"],
                                              entry["cap_units"]))
            else:
                print("    {:<8} no measured usage in this window — cannot "
                      "back-solve a cap yet".format(name))
        print("\n  Run `goldenclaw quota` to see what's left.\n")
        return 0

    if args.cmd == "goodnight":
        from . import night, ritual
        cfg = night.load_config()
        return ritual.goodnight(
            cfg, budget_override=args.budget, dry_run=args.dry_run,
            assume_yes=args.yes,
        )

    if args.cmd == "morning":
        from . import boot, night
        boot.banner(waking=True)
        journal_path, entries = night.latest_journal()
        if journal_path is None:
            print("Max hasn't worked a night yet. Run `goldenclaw goodnight` before bed.",
                  file=sys.stderr)
            return 1
        print(render.render_morning(journal_path, entries, core.assemble(days=7)))
        # End the morning report on what you have NOW — today's tank, live.
        try:
            from . import live
            snap = live.fetch()
            parts = ["{} {:.0f}% left".format(w["label"], w["percent_left"])
                     for w in snap["windows"]]
            print("  " + render.c("Max:", render.BOLD, render.YELLOW)
                  + " today's tank — " + " · ".join(parts) + "\n")
        except Exception:
            pass
        return 0

    if args.cmd == "backlog":
        from . import night
        night._ensure_config()
        print(night.BACKLOG.read_text())
        return 0

    if args.cmd == "ask":
        from . import agent
        return agent.ask(" ".join(args.question), model=args.model)

    if args.cmd == "chat":
        from . import agent
        return agent.chat(model=args.model)

    report = core.assemble(days=args.days)
    if report is None:
        print(
            "No usage data found in the last {} days.\n"
            "Run `goldenclaw doctor` to check data sources.".format(
                getattr(args, "days", 7)
            ),
            file=sys.stderr,
        )
        return 1

    if args.cmd == "json":
        print(json.dumps(report, indent=2))
    else:
        print(render.render_report(report))
    return 0


def max_main(argv=None):
    """The `max` command — the dog himself. Bare `max` opens his own REPL
    (Agent SDK skin) when available, falling back to subprocess chat;
    `max init` sets him up; every goldenclaw subcommand works too."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        from . import maxrepl
        rc = maxrepl.run()
        if rc is not None:
            return rc
        print("  (for Max's full skin: pipx inject goldenclaw claude-agent-sdk)",
              file=sys.stderr)
        from . import agent
        return agent.chat()
    return main(argv)


if __name__ == "__main__":
    sys.exit(main())
