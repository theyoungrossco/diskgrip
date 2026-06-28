"""Canvas: lays out DiskBar items vertically, one per disk, gparted-style."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from diskgrip.core.model import BlockDevice
from diskgrip.ui import theme
from diskgrip.ui.items import DiskBar, DiskNode, PartNode, PartSegment

DISK_GAP = 18.0   # vertical gap between disk bars
MARGIN = 30.0     # scene margin on all sides


class Canvas(QGraphicsView):
    node_menu_requested = Signal(object, QPoint)  # (node, global_pos)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(theme.background())

        self._devices: list[BlockDevice] = []

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def populate(self, devices: list[BlockDevice]) -> None:
        """Clear and rebuild the scene from *devices*."""
        self._devices = devices
        scene = self.scene()
        scene.clear()

        if not devices:
            return

        y = MARGIN
        for disk in devices:
            bar = DiskBar(disk)
            scene.addItem(bar)
            bar.setPos(MARGIN, y)
            y += bar.boundingRect().height() + DISK_GAP

        self.setSceneRect(
            scene.itemsBoundingRect().adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN)
        )

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    # ------------------------------------------------------------------ #
    # context menus
    # ------------------------------------------------------------------ #
    def contextMenuEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.pos())
        item = self.scene().itemAt(scene_pos, self.transform())
        # Walk up to find an actionable item type
        while item is not None and not isinstance(
            item, (DiskBar, DiskNode, PartNode, PartSegment)
        ):
            item = item.parentItem()
        if item is not None:
            # Right-click on unallocated space → show disk menu instead
            if isinstance(item, PartSegment) and item.dev is None:
                item = item.parentItem()
            self.node_menu_requested.emit(item, event.globalPos())
        else:
            super().contextMenuEvent(event)
