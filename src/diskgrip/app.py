"""diskgrip entry point: GUI when a display is available, CLI tree otherwise.

Auto-detect::

    diskgrip               # GUI if DISPLAY/WAYLAND_DISPLAY set, else CLI tree
    diskgrip --demo        # same auto-detect, canned demo data, nothing executed
    diskgrip --host HOST   # same auto-detect, read remote host over SSH

Force mode::

    diskgrip --gui         # always launch the canvas UI (requires PySide6)
    diskgrip --cli         # always print the CLI tree, even with a display
    diskgrip --gui --demo  # canvas with canned demo data
    diskgrip --cli --host HOST  # CLI tree of a remote host
"""

from __future__ import annotations

import argparse
import sys

from diskgrip import __version__
from diskgrip.core.demo import demo_devices
from diskgrip.core.display import choose_gui, has_display
from diskgrip.core.model import BlockDevice
from diskgrip.core.runner import CommandError, LocalRunner, Runner, SSHRunner

# Media-class glyphs for a little gparted-ish flavour in a plain terminal.
_MEDIA_GLYPH = {
    "ssd": "⚡", "hdd": "💽", "usb": "🔌", "optical": "💿",
    "virtual": "☁", "unknown": "▪",
}


def _device_line(dev: BlockDevice) -> str:
    """One line describing a device: identity, then filesystem and mount.

    Disks lead with a media glyph and model; partitions just give the name. The
    filesystem / mount tail is shown for *either* — a disk can carry a
    filesystem directly (no partition table), and that mount must not be hidden.
    """
    if dev.is_disk:
        glyph = _MEDIA_GLYPH.get(dev.media, "▪")
        bits = [f"{glyph} {dev.name}", f"({dev.size})" if dev.size else "",
                (dev.model or "").strip()]
    else:
        bits = [dev.name, f"({dev.size})" if dev.size else ""]

    if dev.fstype:
        fs = dev.fstype
        if dev.label:
            fs += f" “{dev.label}”"
        bits.append(f"[{fs}]")
    elif dev.parttype:
        bits.append(f"[{dev.parttype}]")

    if dev.mounted:
        use = f" {dev.fsuse} used" if dev.fsuse else ""
        bits.append(f"→ {', '.join(dev.mountpoints)}{use}")
    elif dev.has_filesystem:
        bits.append("→ (not mounted)")
    return " ".join(b for b in bits if b)


def render_tree(devices: list[BlockDevice]) -> str:
    """Render the device list as an indented tree. Pure and testable."""
    lines: list[str] = []

    def emit(dev: BlockDevice, depth: int) -> None:
        prefix = "  " * depth + ("└─ " if depth else "")
        lines.append(prefix + _device_line(dev))
        for child in dev.children:
            emit(child, depth + 1)

    if not devices:
        return "(no block devices found)"
    for dev in devices:
        emit(dev, 0)
    return "\n".join(lines)


def _build_runner(args: argparse.Namespace) -> Runner:
    if args.host:
        return SSHRunner(args.host)
    return LocalRunner()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="diskgrip", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"diskgrip {__version__}")
    parser.add_argument("--demo", action="store_true",
                        help="use canned demo data; touches nothing")
    parser.add_argument("--host", metavar="HOST",
                        help="read a remote host over SSH (ssh config name or user@host)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--gui", action="store_true",
                      help="force the canvas UI even when no display is detected")
    mode.add_argument("--cli", action="store_true",
                      help="force CLI tree output; skip the GUI even when a display is available")
    args = parser.parse_args(argv)

    if choose_gui(force_gui=args.gui, force_cli=args.cli):
        return _launch_gui(args)

    # Auto-detected headless: let the user know why the GUI didn't open.
    if not args.cli and not has_display():
        print(
            "diskgrip: no display detected (DISPLAY/WAYLAND_DISPLAY not set).\n"
            "Running in CLI mode. Pass --gui to force the GUI.",
            file=sys.stderr,
        )

    return _cli_main(args)


def _cli_main(args: argparse.Namespace) -> int:
    """Headless path: probe and print the block device tree."""
    if args.demo:
        print("diskgrip — demo host (read-only, nothing is executed)\n")
        print(render_tree(demo_devices()))
        return 0

    # Live read. Import here so --demo never needs lsblk present.
    from diskgrip.core.probe import probe

    runner = _build_runner(args)
    try:
        devices = probe(runner)
    except CommandError as exc:
        print(f"diskgrip: could not read block devices: {exc}", file=sys.stderr)
        return 1
    label = args.host or "localhost"
    print(f"diskgrip — {label}\n")
    print(render_tree(devices))
    return 0


def _launch_gui(args: argparse.Namespace) -> int:
    """Launch the PySide6 GUI. Imported lazily so core stays Qt-free."""
    import signal

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "diskgrip: PySide6 is required for the GUI.\n"
            "Install it with:  pip install PySide6",
            file=sys.stderr,
        )
        return 1

    app = QApplication(sys.argv[:1])
    app.setApplicationName("diskgrip")
    app.setApplicationDisplayName("diskgrip")

    from diskgrip.ui import theme
    theme.apply_theme(app, "system")

    if sys.platform != "win32":
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    from diskgrip.ui.main_window import MainWindow
    window = MainWindow(host=args.host, demo=args.demo)
    window.show()
    return app.exec()
