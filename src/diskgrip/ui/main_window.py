"""Main window: toolbar, canvas, and handlers that turn context-menu gestures
into confirmed command plans."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QToolBar,
)

import diskgrip
from diskgrip.core import actions
from diskgrip.core.demo import demo_devices
from diskgrip.core.model import BlockDevice
from diskgrip.core.runner import DemoRunner, LocalRunner, Runner, SSHRunner
from diskgrip.ui.canvas import Canvas
from diskgrip.ui.dialogs import FormatDialog, MountDialog, confirm_commands
from diskgrip.ui.items import DiskNode, PartNode
from diskgrip.ui.worker import run_in_background


class MainWindow(QMainWindow):
    def __init__(self, host: str | None = None, demo: bool = False):
        super().__init__()
        self.setWindowTitle("diskgrip")
        self.resize(1100, 720)

        self._demo = demo
        self._devices: list[BlockDevice] = []
        self._busy = False

        if demo:
            self.runner: Runner = DemoRunner()
        elif host:
            self.runner = SSHRunner(host)
        else:
            self.runner = LocalRunner()

        self._canvas = Canvas(self)
        self.setCentralWidget(self._canvas)
        self._canvas.node_menu_requested.connect(self._show_node_menu)

        self._build_toolbar()

        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._status_label = QLabel()
        self._status.addWidget(self._status_label)

        # Initial probe
        self._refresh()

    # ------------------------------------------------------------------ #
    # toolbar
    # ------------------------------------------------------------------ #
    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        refresh_act = QAction("Refresh", self)
        refresh_act.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_act.triggered.connect(self._refresh)
        tb.addAction(refresh_act)

        tb.addSeparator()

        host_label = QLabel(
            "  demo host  " if self._demo
            else f"  {self.runner.label}  "
        )
        tb.addWidget(host_label)

        tb.addSeparator()

        ver_label = QLabel(f"  diskgrip {diskgrip.__version__}  ")
        from diskgrip.ui import theme
        ver_label.setStyleSheet(f"color: {theme.text_dim().name()};")
        tb.addWidget(ver_label)

    # ------------------------------------------------------------------ #
    # probe / refresh
    # ------------------------------------------------------------------ #
    def _refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_status("Probing…")

        if self._demo:
            self._on_probe_done(demo_devices())
            return

        def do_probe():
            from diskgrip.core.probe import probe
            return probe(self.runner)

        run_in_background(do_probe, self._on_probe_done, self._on_probe_error)

    def _on_probe_done(self, devices: list[BlockDevice]) -> None:
        self._busy = False
        self._devices = devices
        self._canvas.populate(devices)
        n = sum(1 for _ in self._iter_all(devices))
        self._set_status(f"{len(devices)} disk(s), {n} device(s) total")

    def _on_probe_error(self, message: str) -> None:
        self._busy = False
        self._set_status(f"Probe failed: {message}")
        QMessageBox.critical(self, "Probe failed", message)

    @staticmethod
    def _iter_all(devices: list[BlockDevice]):
        for dev in devices:
            yield from dev.walk()

    def _set_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    # ------------------------------------------------------------------ #
    # context menu
    # ------------------------------------------------------------------ #
    def _show_node_menu(self, node, global_pos: QPoint) -> None:
        menu = QMenu(self)

        if isinstance(node, DiskNode):
            dev = node.dev
            act_ptable = QAction("Create partition table (GPT)…", self)
            act_ptable.triggered.connect(lambda: self._do_create_partition_table(dev, "gpt"))
            menu.addAction(act_ptable)

            act_ptable_mbr = QAction("Create partition table (MBR/msdos)…", self)
            act_ptable_mbr.triggered.connect(
                lambda: self._do_create_partition_table(dev, "msdos")
            )
            menu.addAction(act_ptable_mbr)

        elif isinstance(node, PartNode):
            dev = node.dev

            if dev.mounted:
                act_umount = QAction(f"Unmount {dev.path}…", self)
                act_umount.triggered.connect(lambda: self._do_unmount(dev))
                menu.addAction(act_umount)
            elif dev.has_filesystem:
                act_mount = QAction(f"Mount {dev.path}…", self)
                act_mount.triggered.connect(lambda: self._do_mount(dev))
                menu.addAction(act_mount)

            if not dev.mounted and dev.kind in ("part", "loop"):
                menu.addSeparator()
                act_fmt = QAction(f"Format {dev.path}…", self)
                act_fmt.triggered.connect(lambda: self._do_format(dev))
                menu.addAction(act_fmt)

        if not menu.isEmpty():
            menu.exec(global_pos)

    # ------------------------------------------------------------------ #
    # action handlers: build plan → confirm → run → re-probe
    # ------------------------------------------------------------------ #
    def _apply(self, title: str, plan: list[list[str]]) -> None:
        """Confirm plan with the user, run it, then re-probe."""
        if not confirm_commands(self, title, plan):
            return
        self._busy = True
        self._set_status("Running…")

        def do_run():
            self.runner.run_privileged(plan)

        def on_done(_):
            self._busy = False
            self._set_status("Done — refreshing…")
            self._refresh()

        def on_error(msg: str):
            self._busy = False
            self._set_status(f"Error: {msg}")
            QMessageBox.critical(self, "Command failed", msg)

        run_in_background(do_run, on_done, on_error)

    def _do_mount(self, dev: BlockDevice) -> None:
        dlg = MountDialog(dev.path, self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        mp = dlg.mountpoint()
        plan = actions.plan_mount(dev, mp)
        self._apply(f"Mount {dev.path}", plan)

    def _do_unmount(self, dev: BlockDevice) -> None:
        plan = actions.plan_unmount(dev)
        self._apply(f"Unmount {dev.path}", plan)

    def _do_format(self, dev: BlockDevice) -> None:
        dlg = FormatDialog(dev.path, self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        try:
            plan = actions.plan_format(dev, dlg.fstype(), dlg.label())
        except ValueError as exc:
            QMessageBox.critical(self, "Format error", str(exc))
            return
        self._apply(f"Format {dev.path}", plan)

    def _do_create_partition_table(self, dev: BlockDevice, table_type: str) -> None:
        try:
            plan = actions.plan_create_partition_table(dev, table_type)
        except ValueError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._apply(f"Create {table_type.upper()} partition table on {dev.path}", plan)
