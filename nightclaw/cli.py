"""NightClaw CLI — boots from the terminal, shows live data by default."""

import argparse
import json
import sys

from . import __version__, core, render


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(
        prog="nightclaw",
        description="Measure your AI subscription token utilization from local logs.",
    )
    parser.add_argument("--version", action="version", version="nightclaw " + __version__)
    sub = parser.add_subparsers(dest="cmd")

    p_report = sub.add_parser("report", help="visual utilization report (default)")
    p_report.add_argument("--days", type=int, default=7, help="lookback period (default 7)")

    p_json = sub.add_parser("json", help="machine-readable report")
    p_json.add_argument("--days", type=int, default=7, help="lookback period (default 7)")

    sub.add_parser("doctor", help="verify NightClaw can find your usage data")

    p_night = sub.add_parser("goodnight", help="run your backlog overnight, inside guardrails")
    p_night.add_argument("--dry-run", action="store_true", help="show the plan without running")
    p_night.add_argument("--budget", type=int, default=None, help="override night token budget")
    p_night.add_argument("--yes", action="store_true",
                         help="skip the confirmation prompt (after reviewing with --dry-run)")

    sub.add_parser("morning", help="digest of what ran last night")
    sub.add_parser("backlog", help="show the overnight task backlog")

    # AXI principle: no arguments shows live data, not help text.
    if not argv:
        argv = ["report"]
    args = parser.parse_args(argv)

    if args.cmd == "doctor":
        d = core.doctor()
        print(render.render_doctor(d))
        return 0 if d["ok"] else 1

    if args.cmd == "goodnight":
        from . import night
        cfg = night.load_config()
        return night.run_night(
            cfg, budget_override=args.budget, dry_run=args.dry_run,
            assume_yes=args.yes,
        )

    if args.cmd == "morning":
        from . import night
        journal_path, entries = night.latest_journal()
        if journal_path is None:
            print("No nights on record yet. Run `nightclaw goodnight` first.", file=sys.stderr)
            return 1
        print(render.render_morning(journal_path, entries, core.assemble(days=7)))
        return 0

    if args.cmd == "backlog":
        from . import night
        night._ensure_config()
        print(night.BACKLOG.read_text())
        return 0

    report = core.assemble(days=args.days)
    if report is None:
        print(
            "No usage data found in the last {} days.\n"
            "Run `nightclaw doctor` to check data sources.".format(
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
