"""Dialogs: command confirmation and action-specific input forms."""

from __future__ import annotations

import shlex

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from diskgrip.core.actions import SUPPORTED_FSTYPES, valid_mountpoint
from diskgrip.ui import theme


def _error_label() -> QLabel:
    label = QLabel()
    label.setStyleSheet(f"color: {theme.error().name()};")
    label.setWordWrap(True)
    return label


def confirm_commands(parent, title: str, plan: list[list[str]]) -> bool:
    """Show the exact commands the plan would run; return True if the user
    clicks Run, False if they cancel.

    Project rule: a dialog never opens another dialog.  This is always the
    *last* dialog in a gesture sequence — the input dialog closes before this
    opens, so they are sequential, not nested.
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(500)

    layout = QVBoxLayout(dlg)

    intro = QLabel("The following commands will be run as root:")
    intro.setWordWrap(True)
    layout.addWidget(intro)

    code = "\n".join(shlex.join(argv) for argv in plan)
    code_label = QLabel(code)
    mono = QFont("Monospace")
    mono.setStyleHint(QFont.StyleHint.Monospace)
    code_label.setFont(mono)
    code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    code_label.setWordWrap(True)
    code_label.setStyleSheet(
        f"background: {theme.panel().name()}; padding: 8px; border-radius: 4px;"
    )
    layout.addWidget(code_label)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Run")
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)

    return dlg.exec() == QDialog.DialogCode.Accepted


class MountDialog(QDialog):
    """Ask for a mountpoint path."""

    def __init__(self, dev_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Mount {dev_path}")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._mp = QLineEdit()
        self._mp.setPlaceholderText("/mnt/data")
        form.addRow("Mountpoint:", self._mp)
        layout.addLayout(form)

        self._err = _error_label()
        layout.addWidget(self._err)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Mount")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._buttons = buttons

    def _validate(self) -> None:
        mp = self._mp.text().strip()
        if not valid_mountpoint(mp):
            self._err.setText("Enter an absolute path (e.g. /mnt/data).")
            return
        self._err.clear()
        self.accept()

    def mountpoint(self) -> str:
        return self._mp.text().strip()


class FormatDialog(QDialog):
    """Ask for a filesystem type and optional label, with a destructive warning."""

    def __init__(self, dev_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Format {dev_path}")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        warn = QLabel(
            f"<b>Warning:</b> formatting {dev_path} will permanently erase all data on it."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {theme.error().name()};")
        layout.addWidget(warn)

        form = QFormLayout()

        self._fstype = QComboBox()
        self._fstype.addItems(SUPPORTED_FSTYPES)
        self._fstype.setCurrentText("ext4")
        form.addRow("Filesystem:", self._fstype)

        self._label = QLineEdit()
        self._label.setPlaceholderText("optional")
        form.addRow("Label:", self._label)

        layout.addLayout(form)

        self._err = _error_label()
        layout.addWidget(self._err)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Format")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def fstype(self) -> str:
        return self._fstype.currentText()

    def label(self) -> str:
        return self._label.text().strip()
