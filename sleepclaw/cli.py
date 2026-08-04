"""SleepClaw CLI — boots from the terminal, shows live data by default."""

import argparse
import json
import sys

from . import __version__, core, render


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(
        prog="sleepclaw",
        description="Measure your AI subscription token utilization from local logs.",
    )
    parser.add_argument("--version", action="version", version="sleepclaw " + __version__)
    sub = parser.add_subparsers(dest="cmd")

    p_report = sub.add_parser("report", help="visual utilization report (default)")
    p_report.add_argument("--days", type=int, default=7, help="lookback period (default 7)")

    p_json = sub.add_parser("json", help="machine-readable report")
    p_json.add_argument("--days", type=int, default=7, help="lookback period (default 7)")

    sub.add_parser("doctor", help="verify SleepClaw can find your usage data")
    sub.add_parser("boot", help="wake the dog — banner and environment check")

    p_quota = sub.add_parser("quota", help="live quota: how much is left, when it resets")
    p_quota.add_argument("--json", action="store_true", dest="as_json",
                         help="machine-readable")
    p_quota.add_argument("--offline", action="store_true",
                         help="skip the live usage API and use local data only")

    p_cal = sub.add_parser(
        "calibrate",
        help="teach SleepClaw your entitlement from the provider's usage panel")
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

    sub.add_parser("menubar", help="SwiftBar/xbar plugin output for the menu bar")

    p_night = sub.add_parser("goodnight", help="run your backlog overnight, inside guardrails")
    p_night.add_argument("--dry-run", action="store_true", help="show the plan without running")
    p_night.add_argument("--budget", type=int, default=None, help="override night token budget")
    p_night.add_argument("--yes", action="store_true",
                         help="skip the confirmation prompt (after reviewing with --dry-run)")

    sub.add_parser("morning", help="digest of what ran last night")
    sub.add_parser("backlog", help="show the overnight task backlog")

    p_ask = sub.add_parser("ask", help="ask the SleepClaw agent a question (one-shot)")
    p_ask.add_argument("question", nargs="+", help="your question, plain English")
    p_ask.add_argument("--model", default=None, help="model override for the agent")

    p_chat = sub.add_parser("chat", help="talk to the SleepClaw agent interactively")
    p_chat.add_argument("--model", default=None, help="model override for the agent")

    # AXI principle: no arguments shows live data, not help text.
    if not argv:
        argv = ["report"]
    args = parser.parse_args(argv)

    if args.cmd == "boot":
        from . import boot
        boot.sequence()
        return 0

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
                      '  sleepclaw calibrate --provider codex --used 66 '
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
                  "SleepClaw will\n    show its age so it can't pass for live data.\n")
            return 0

        pools = {k: v for k, v in (("weekly", args.weekly), ("fable", args.fable),
                                   ("opus", args.opus)) if v is not None}
        if not pools or not args.resets:
            print(
                "Open Claude Code's usage panel (/usage), then pass what it shows:\n"
                '  sleepclaw calibrate --weekly 49 --fable 85 --resets "Wed 3:00 PM"\n'
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
        print("\n  Run `sleepclaw quota` to see what's left.\n")
        return 0

    if args.cmd == "goodnight":
        from . import boot, night
        boot.banner()
        cfg = night.load_config()
        return night.run_night(
            cfg, budget_override=args.budget, dry_run=args.dry_run,
            assume_yes=args.yes,
        )

    if args.cmd == "morning":
        from . import boot, night
        boot.banner(waking=True)
        journal_path, entries = night.latest_journal()
        if journal_path is None:
            print("No nights on record yet. Run `sleepclaw goodnight` first.", file=sys.stderr)
            return 1
        print(render.render_morning(journal_path, entries, core.assemble(days=7)))
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
            "Run `sleepclaw doctor` to check data sources.".format(
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


if __name__ == "__main__":
    sys.exit(main())
