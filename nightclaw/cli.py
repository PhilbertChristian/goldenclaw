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

    # AXI principle: no arguments shows live data, not help text.
    if not argv:
        argv = ["report"]
    args = parser.parse_args(argv)

    if args.cmd == "doctor":
        d = core.doctor()
        print(render.render_doctor(d))
        return 0 if d["ok"] else 1

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
