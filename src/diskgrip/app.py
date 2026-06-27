"""diskgrip entry point: CLI tree viewer and PySide6 GUI.

CLI (default)::

    diskgrip               # probe and print a tree of this machine's disks
    diskgrip --demo        # canned demo host, no root, touches nothing
    diskgrip --host HOST   # read a remote host over SSH (~/.ssh/config)

GUI (requires PySide6)::

    diskgrip --gui         # launch the canvas UI on the local machine
    diskgrip --gui --demo  # launch the canvas with the canned demo host
    diskgrip --gui --host HOST
"""

from __future__ import annotations

import argparse
import sys

from diskgrip import __version__
from diskgrip.core.demo import demo_devices
from diskgrip.core.model import BlockDevice
from diskgrip.core.runner import CommandError, LocalRunner, Runner, SSHRunner

# Media-class glyphs for a little gparted-ish flavour in a plain terminal.
_MEDIA_GLYPH = {
    "ssd": "⚡", "hdd": "💽", "usb": "🔌", "optical": "💿",
    "virtual": "☁", "unknown": "▪",
}


def _device_line(dev: BlockDevice) -> str:
    """One line describing a device: name, size, fs/label and mount."""
    bits = [f"{dev.name}", f"({dev.size})" if dev.size else ""]
    if dev.is_disk:
        glyph = _MEDIA_GLYPH.get(dev.media, "▪")
        model = f" {dev.model}" if dev.model else ""
        bits = [f"{glyph} {dev.name}", f"({dev.size})", model.strip()]
    else:
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
    parser = argparse.ArgumentParser(prog="diskgrip", description=__doc__)
    parser.add_argument("--version", action="version", version=f"diskgrip {__version__}")
    parser.add_argument("--demo", action="store_true",
                        help="show the canned demo host; touches nothing")
    parser.add_argument("--host", metavar="HOST",
                        help="read a remote host over SSH (ssh config name or user@host)")
    parser.add_argument("--gui", action="store_true",
                        help="launch the PySide6 canvas UI (requires PySide6)")
    args = parser.parse_args(argv)

    if args.gui:
        return _launch_gui(args)

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


def _launch_gui(args) -> int:
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
