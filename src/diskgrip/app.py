"""diskgrip CLI: render a host's block-storage topology as a tree.

This is the headless *viewer* — the first slice of diskgrip, deliberately
Qt-free. It reuses the vendored :class:`~diskgrip.core.runner.Runner` for
local/SSH reads and the same probe/model the future GUI will, so the canvas can
later sit straight on top.

Usage::

    diskgrip               # probe and show this machine's disks
    diskgrip --demo        # canned demo host, no root, touches nothing
    diskgrip --host HOST   # read a remote host over SSH (~/.ssh/config)
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
    args = parser.parse_args(argv)

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
