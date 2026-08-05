"""The night shift — run your backlog while you sleep, inside guardrails.

`goldenclaw goodnight` reads unchecked tasks from the backlog, validates every
task against the repo allowlist, then runs each one headlessly via the
`claude` CLI. Between tasks it re-reads the local sensor to enforce a hard
per-night token budget. Everything is journaled to a per-night JSONL file
that `goldenclaw morning` renders.

Guardrails (deliberate, documented):
  - only repos named in night.json's allowlist can be touched
  - NO default permission mode: you must explicitly choose one in night.json
    before any unattended run — `acceptEdits` means overnight agents can edit
    allowlisted repos without per-action approval, and that choice is yours
    to make, in writing. `bypassPermissions` is refused outright.
  - launching requires typed confirmation of the plan (or an explicit --yes
    after reviewing it with --dry-run)
  - a hard token budget: the night stops when it's spent
  - per-task wall-clock timeout
  - full journal of what ran, what it cost, and how it exited
  - nothing is pushed anywhere unless your task prompt says to
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import core

CONFIG_DIR = Path.home() / ".config" / "max"
NIGHT_CONFIG = CONFIG_DIR / "night.json"
BACKLOG = CONFIG_DIR / "backlog.md"
NIGHTS_DIR = CONFIG_DIR / "nights"

DEFAULT_CONFIG = {
    "_note": (
        "permission_mode has NO default and must be set before goodnight will "
        "run: 'default' (agents can only use pre-approved tools), 'plan' "
        "(read-only planning), or 'acceptEdits' (agents may edit allowlisted "
        "repos WITHOUT per-action approval — an informed opt-in). "
        "'bypassPermissions' is refused."
    ),
    "repos": {},
    "night_budget_tokens": 30_000_000,
    "task_timeout_minutes": 45,
    "weekly_reserve_pct": 15,
    "permission_mode": None,
    "model": None,
    "extra_args": [],
}

ALLOWED_MODES = ("default", "plan", "acceptEdits")

BACKLOG_TEMPLATE = """\
# GoldenClaw backlog — one task per line, format: `- [ ] repo: task`
# `repo` must be a key in night.json's "repos" allowlist.
# GoldenClaw checks tasks off as they succeed.

# - [ ] goldenclaw: add unit tests for window reconstruction in core.py
"""


def _ensure_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    created = []
    if not NIGHT_CONFIG.is_file():
        NIGHT_CONFIG.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")
        created.append(str(NIGHT_CONFIG))
    if not BACKLOG.is_file():
        BACKLOG.write_text(BACKLOG_TEMPLATE)
        created.append(str(BACKLOG))
    return created


def load_config():
    _ensure_config()
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(NIGHT_CONFIG.read_text()))
    except (json.JSONDecodeError, OSError):
        pass
    return cfg


def parse_backlog():
    """Return (lines, tasks) where tasks = [(line_index, repo, prompt)]."""
    if not BACKLOG.is_file():
        return [], []
    lines = BACKLOG.read_text().splitlines()
    tasks = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("- [ ]"):
            continue
        body = s[5:].strip()
        if ":" not in body:
            continue
        repo, prompt = body.split(":", 1)
        tasks.append((i, repo.strip(), prompt.strip()))
    return lines, tasks


def _check_off(lines, index):
    lines[index] = lines[index].replace("- [ ]", "- [x]", 1)
    BACKLOG.write_text("\n".join(lines) + "\n")


def tokens_between(dirs, t0, t1):
    total = 0
    for when, usage, _model in core.iter_events(dirs):
        if t0 <= when <= t1:
            total += core.event_tokens(usage)
    return total


def _runner_prefix():
    if sys.platform == "darwin" and shutil.which("caffeinate"):
        return ["caffeinate", "-is"]
    return []


def _build_command(cfg, prompt):
    cmd = _runner_prefix() + [
        "claude", "-p", prompt,
        "--permission-mode", str(cfg["permission_mode"]),
    ]
    if cfg.get("model"):
        cmd += ["--model", str(cfg["model"])]
    cmd += [str(a) for a in cfg.get("extra_args") or []]
    return cmd


def plan(cfg, tasks):
    """Validate tasks against the allowlist. Returns (runnable, problems)."""
    repos = {k: Path(str(v)).expanduser() for k, v in (cfg.get("repos") or {}).items()}
    runnable, problems = [], []
    for idx, repo, prompt in tasks:
        if repo not in repos:
            problems.append("'{}' is not in the night.json repo allowlist".format(repo))
        elif not repos[repo].is_dir():
            problems.append("repo '{}' path does not exist: {}".format(repo, repos[repo]))
        else:
            runnable.append({"index": idx, "repo": repo, "path": repos[repo], "prompt": prompt})
    return runnable, problems


def _live_week_left():
    """Weekly percent-left from the live usage API, or None when unreachable.
    A network failure never blocks the night — the token budget still caps it —
    but a *successful* read below the reserve stops spending immediately."""
    try:
        from . import live
        snap = live.fetch()
    except Exception:
        return None
    for w in snap.get("windows", []):
        if w.get("id") == "seven_day":
            return w.get("percent_left")
    return None


def run_night(cfg, budget_override=None, dry_run=False, assume_yes=False, out=print):
    created = _ensure_config()
    for path in created:
        out("  created {}".format(path))

    mode = cfg.get("permission_mode")
    if not dry_run:
        if not mode:
            out("  ✗ No permission_mode set in {}".format(NIGHT_CONFIG))
            out("    Unattended agents need an explicit, written choice from you:")
            out("      \"default\"     agents can only use tools you've pre-approved")
            out("      \"plan\"        read-only planning runs")
            out("      \"acceptEdits\" agents may edit allowlisted repos without asking")
            out("    Set one, then re-run. This is deliberate — see README § The night shift.")
            return 1
        if mode not in ALLOWED_MODES:
            out("  ✗ permission_mode '{}' is not allowed (choose from: {}).".format(
                mode, ", ".join(ALLOWED_MODES)))
            out("    'bypassPermissions' will never be supported here.")
            return 1
        if shutil.which("claude") is None:
            out("  ✗ `claude` CLI not found on PATH — install Claude Code first.")
            return 1

    lines, tasks = parse_backlog()
    if not tasks:
        out("  Backlog is empty. Add tasks to {}".format(BACKLOG))
        out("  Format: - [ ] repo: task description")
        return 1

    runnable, problems = plan(cfg, tasks)
    for p in problems:
        out("  ! skipping: {}".format(p))
    if not runnable:
        out("  Nothing runnable. Add your repos to {} first.".format(NIGHT_CONFIG))
        return 1

    reserve_cfg = float(cfg.get("weekly_reserve_pct", 15))
    week_left = _live_week_left()
    if week_left is not None:
        # Ground truth beats any estimate — stale calibration must never veto
        # (or authorize) a night when the live number is available.
        guard_ok = week_left > reserve_cfg
        guard_msg = "live — {:.0f}% of the week left (reserve {:.0f}%)".format(
            week_left, reserve_cfg)
    else:
        from . import quota
        guard_ok, guard_msg = quota.night_budget_guard(reserve_cfg)
    out("")
    out("  Quota check: {}".format(guard_msg))
    if not guard_ok:
        out("  ⛔ Not enough weekly quota left to run the night safely.")
        out("     Your morning session needs a full tank. Lower "
            "weekly_reserve_pct in night.json to override.")
        return 1

    budget = int(budget_override or cfg["night_budget_tokens"])
    timeout_s = int(cfg["task_timeout_minutes"]) * 60
    out("")
    out("  🌙 Night plan — {} task(s), budget {} tokens, timeout {}m/task, mode: {}".format(
        len(runnable), "{:,}".format(budget), cfg["task_timeout_minutes"],
        mode or "(unset)"))
    for t in runnable:
        out("     • [{}] {}".format(t["repo"], t["prompt"][:90]))
    if dry_run:
        out("  (dry run — nothing executed)")
        return 0

    if not assume_yes:
        if not sys.stdin.isatty():
            out("  ✗ Not an interactive terminal. Review the plan with --dry-run,")
            out("    then re-run with --yes to confirm the launch explicitly.")
            return 1
        try:
            answer = input("  Should Max hold the fort? Type 'run' to confirm: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() != "run":
            out("  Aborted — nothing was executed.")
            return 0

    dirs = core.find_log_dirs()
    NIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    night_start = datetime.now(timezone.utc)
    journal_path = NIGHTS_DIR / (night_start.astimezone().strftime("%Y-%m-%d") + ".jsonl")

    spent = 0
    out("")
    with open(journal_path, "a") as journal:
        reserve = float(cfg.get("weekly_reserve_pct", 15))
        for t in runnable:
            week_left = _live_week_left()
            if week_left is not None and week_left <= reserve:
                out("  ⛔ live check: weekly quota at {:.0f}% — at your reserve "
                    "({:.0f}%). Max stops here; your morning tank comes first.".format(
                        week_left, reserve))
                journal.write(json.dumps({
                    "type": "reserve_stop", "week_left_pct": week_left,
                    "reserve_pct": reserve,
                    "at": datetime.now(timezone.utc).isoformat(),
                }) + "\n")
                break
            if spent >= budget:
                out("  ⛔ budget spent ({:,} tokens) — stopping. Remaining tasks stay in the backlog.".format(spent))
                journal.write(json.dumps({
                    "type": "budget_stop", "spent": spent, "budget": budget,
                    "at": datetime.now(timezone.utc).isoformat(),
                }) + "\n")
                break
            out("  ▶ [{}] {}".format(t["repo"], t["prompt"][:70]))
            t0 = datetime.now(timezone.utc)
            try:
                proc = subprocess.run(
                    _build_command(cfg, t["prompt"]),
                    cwd=str(t["path"]), capture_output=True, text=True,
                    timeout=timeout_s,
                )
                exit_code, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
            except subprocess.TimeoutExpired:
                exit_code, output = -1, "timed out after {}m".format(cfg["task_timeout_minutes"])
            t1 = datetime.now(timezone.utc)
            burned = tokens_between(dirs, t0, t1)
            spent += burned
            ok = exit_code == 0
            if ok:
                _check_off(lines, t["index"])
            journal.write(json.dumps({
                "type": "task", "repo": t["repo"], "prompt": t["prompt"],
                "started": t0.isoformat(), "ended": t1.isoformat(),
                "exit_code": exit_code, "ok": ok, "tokens": burned,
                "output_tail": output[-800:],
            }) + "\n")
            journal.flush()
            out("    {} {} tokens · exit {}".format("✓" if ok else "✗", "{:,}".format(burned), exit_code))

    out("")
    out("  Night complete — {:,} tokens spent. Journal: {}".format(spent, journal_path))
    out("  Run `goldenclaw morning` when you wake up. 🌅")
    return 0


def latest_journal():
    if not NIGHTS_DIR.is_dir():
        return None, []
    files = sorted(NIGHTS_DIR.glob("*.jsonl"))
    if not files:
        return None, []
    entries = []
    with open(files[-1]) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return files[-1], entries
