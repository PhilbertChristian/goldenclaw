"""Max in the macOS menu bar — via SwiftBar (or xbar).

The whole integration is one tiny shell plugin that SwiftBar runs every five
minutes: it execs `goldenclaw menubar`, whose output IS the menu bar item.
`🐶 41%` in the strip; the dropdown shows every window with its reset clock
and two actions that open the real terminal experience.

Why SwiftBar instead of shipping an app: it's the same job baby-menu does
with a full Electron runtime, done with ~10 lines of plugin. No new process
tree, no signing, no updater — and if the user already runs SwiftBar, Max is
just one more plugin file. `max menubar --install` writes it; deleting the
file uninstalls it.
"""

import shutil
import subprocess
from pathlib import Path

PLUGIN_NAME = "max.5m.sh"

SWIFTBAR_APP = Path("/Applications/SwiftBar.app")
XBAR_APP = Path("/Applications/xbar.app")
XBAR_PLUGIN_DIR = Path.home() / "Library" / "Application Support" / "xbar" / "plugins"


def _swiftbar_plugin_dir():
    """SwiftBar's user-chosen plugin folder, from its preferences."""
    try:
        proc = subprocess.run(
            ["defaults", "read", "com.ammonia-labs.SwiftBar", "PluginDirectory"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = proc.stdout.strip()
    return Path(path).expanduser() if proc.returncode == 0 and path else None


def install(out=print):
    exe = shutil.which("goldenclaw")
    if not exe:
        out("  goldenclaw isn't on PATH — install it first.")
        return 1

    target_dir = None
    host = None
    if SWIFTBAR_APP.exists():
        host = "SwiftBar"
        target_dir = _swiftbar_plugin_dir()
        if target_dir is None:
            out("  SwiftBar is installed but hasn't chosen a plugin folder yet.")
            out("  Open SwiftBar once, pick a folder, then re-run `max menubar --install`.")
            return 1
    elif XBAR_APP.exists():
        host = "xbar"
        target_dir = XBAR_PLUGIN_DIR
    else:
        out("  Max needs a menu-bar host. SwiftBar is the good one:")
        out("")
        out("      brew install --cask swiftbar")
        out("")
        out("  Open it once (it asks where to keep plugins), then re-run:")
        out("      max menubar --install")
        return 1

    target_dir.mkdir(parents=True, exist_ok=True)
    plugin = target_dir / PLUGIN_NAME
    plugin.write_text(
        "#!/bin/bash\n"
        "# Max the Golden Token Retrieval — menu bar plugin.\n"
        "# Delete this file to remove Max from the menu bar.\n"
        'exec "{}" menubar\n'.format(exe)
    )
    plugin.chmod(0o755)
    out("  ✓ Max is in your menu bar (via {}): {}".format(host, plugin))
    out("    He refreshes every 5 minutes. Click him for the dropdown;")
    out("    'Wake Max in Terminal' opens the full experience.")
    if host == "SwiftBar":
        out("    (If he doesn't appear, click the SwiftBar icon → Refresh All.)")
    return 0


def uninstall(out=print):
    """Remove Max from the menu bar — delete the plugin, touch nothing else."""
    removed = []
    for d in filter(None, [_swiftbar_plugin_dir(), XBAR_PLUGIN_DIR]):
        plugin = d / PLUGIN_NAME
        if plugin.exists():
            plugin.unlink()
            removed.append(str(plugin))
    if removed:
        for r in removed:
            out("  ✓ removed " + r)
        out("  Max has left the menu bar. SwiftBar itself is yours to keep or")
        out("  remove (`brew uninstall --cask swiftbar`).")
    else:
        out("  Max wasn't in the menu bar.")
    return 0
