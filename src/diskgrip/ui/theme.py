"""Theme: one place that decides every colour the canvas paints.

Colours follow the OS theme: this module resolves a light/dark scheme and hands
out matching colours, so the canvas sits naturally on a light or dark desktop.
Never hardcode hex colours outside this module.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QPen
from PySide6.QtWidgets import QApplication

_scheme: str | None = None

_LIGHT = {
    "background": "#f5f6f8",
    "panel": "#ffffff",
    "text": "#1b2430",
    "text_dim": "#5b6672",
    "edge": "#aab2bb",
    "error": "#c0392b",
    # disk nodes keyed by media class
    "disk_hdd": ("#e4eaf3", "#4a6fa3"),
    "disk_ssd": ("#e2edf5", "#3a7ab8"),
    "disk_usb": ("#f3ead9", "#b07030"),
    "disk_optical": ("#f0e9f5", "#7a52a8"),
    "disk_virtual": ("#e8edf5", "#5060a0"),
    "disk_unknown": ("#ebebeb", "#888888"),
    # partition / child nodes
    "part": ("#e8f5e9", "#3f8a44"),        # healthy partition with or without fs
    "part_mounted": ("#d6efdb", "#2e7d32"),  # mounted — a touch more vivid
    "part_crypt": ("#f9e9e9", "#b03030"),    # LUKS / crypto container
    "part_lvm": ("#eee5f8", "#6a44a8"),      # LVM physical / logical volume
    "part_swap": ("#ebebeb", "#808080"),
    "part_loop": ("#edf5fb", "#4080a8"),
}

_DARK = {
    "background": "#1e2228",
    "panel": "#262b32",
    "text": "#e6e9ee",
    "text_dim": "#9aa4b0",
    "edge": "#525a63",
    "error": "#e06a5a",
    "disk_hdd": ("#1f2d3f", "#5b8cb5"),
    "disk_ssd": ("#1c2e3f", "#4a8fc8"),
    "disk_usb": ("#312a1a", "#c0843a"),
    "disk_optical": ("#291e3a", "#9060c0"),
    "disk_virtual": ("#1e2540", "#6878c0"),
    "disk_unknown": ("#282828", "#909090"),
    "part": ("#1a2e1b", "#5fae5f"),
    "part_mounted": ("#152618", "#4aa84a"),
    "part_crypt": ("#301818", "#d04040"),
    "part_lvm": ("#251a38", "#9060d8"),
    "part_swap": ("#282828", "#888888"),
    "part_loop": ("#1a2b38", "#5090b8"),
}


def _detect_scheme() -> str:
    override = os.environ.get("DISKGRIP_THEME")
    if override in ("light", "dark"):
        return override
    app = QApplication.instance()
    if app is not None:
        try:
            hint = app.styleHints().colorScheme()
            if hint == Qt.ColorScheme.Dark:
                return "dark"
            if hint == Qt.ColorScheme.Light:
                return "light"
        except (AttributeError, RuntimeError):
            pass
        if app.palette().window().color().lightness() < 128:
            return "dark"
    return "light"


def scheme() -> str:
    global _scheme
    if _scheme is None:
        _scheme = _detect_scheme()
    return _scheme


def is_dark() -> bool:
    return scheme() == "dark"


def _table() -> dict:
    return _DARK if is_dark() else _LIGHT


def background() -> QColor:
    return QColor(_table()["background"])


def panel() -> QColor:
    return QColor(_table()["panel"])


def text() -> QColor:
    return QColor(_table()["text"])


def text_dim() -> QColor:
    return QColor(_table()["text_dim"])


def edge() -> QColor:
    return QColor(_table()["edge"])


def error() -> QColor:
    return QColor(_table()["error"])


def disk_node(media: str) -> tuple[QColor, QColor]:
    """(fill, border) for a disk node keyed by its media class."""
    key = f"disk_{media}" if f"disk_{media}" in _table() else "disk_unknown"
    fill, border = _table()[key]
    return QColor(fill), QColor(border)


def part_node(kind: str, mounted: bool = False, fstype: str | None = None) -> tuple[QColor, QColor]:
    """(fill, border) for a partition/child node."""
    if kind == "crypt":
        key = "part_crypt"
    elif kind in ("lvm", "raid0", "raid1", "raid5", "raid6", "raid10"):
        key = "part_lvm"
    elif fstype == "swap":
        key = "part_swap"
    elif kind == "loop":
        key = "part_loop"
    elif mounted:
        key = "part_mounted"
    else:
        key = "part"
    fill, border = _table()[key]
    return QColor(fill), QColor(border)


def edge_pen() -> QPen:
    return QPen(edge(), 1.4)


def apply_theme(app: QApplication, mode: str = "system") -> str:
    global _scheme
    if mode in ("light", "dark"):
        _scheme = mode
    else:
        _scheme = _detect_scheme()
    if _scheme == "dark":
        app.setPalette(_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())
    return _scheme


def _dark_palette() -> QPalette:
    t = _DARK
    base = QColor(t["background"])
    panel_c = QColor(t["panel"])
    txt = QColor(t["text"])
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, base)
    pal.setColor(QPalette.ColorRole.WindowText, txt)
    pal.setColor(QPalette.ColorRole.Base, QColor("#23272e"))
    pal.setColor(QPalette.ColorRole.AlternateBase, panel_c)
    pal.setColor(QPalette.ColorRole.ToolTipBase, panel_c)
    pal.setColor(QPalette.ColorRole.ToolTipText, txt)
    pal.setColor(QPalette.ColorRole.Text, txt)
    pal.setColor(QPalette.ColorRole.Button, panel_c)
    pal.setColor(QPalette.ColorRole.ButtonText, txt)
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#3d6ea5"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["text_dim"]))
    disabled = QColor(t["text_dim"])
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return pal
