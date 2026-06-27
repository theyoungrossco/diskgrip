"""Canvas: lays out disk nodes and their children as a tree, one column per
disk, partitions stacked vertically beneath their parent."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from diskgrip.core.model import BlockDevice
from diskgrip.ui import theme
from diskgrip.ui.items import DiskNode, Edge, PartNode

COL_GAP = 50.0    # horizontal space between disk columns
NODE_GAP = 14.0   # vertical space between sibling nodes in a column
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

        x = MARGIN
        for disk in devices:
            col_width = self._place_tree(disk, x, MARGIN)
            x += col_width + COL_GAP

        # Fit the whole diagram in view on first populate; subsequent refreshes
        # keep whatever pan/zoom the user had set.
        self.setSceneRect(scene.itemsBoundingRect().adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN))

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    # ------------------------------------------------------------------ #
    # layout
    # ------------------------------------------------------------------ #
    def _place_tree(self, disk: BlockDevice, left: float, top: float) -> float:
        """Place *disk* and all its children at (*left*, *top*).

        Returns the column width (the widest node in this subtree) so the
        caller knows where to start the next column.
        """
        scene = self.scene()
        disk_node = DiskNode(disk)
        scene.addItem(disk_node)
        disk_node.setPos(left, top)

        col_w = disk_node.boundingRect().width()
        y = top + disk_node.boundingRect().height() + NODE_GAP

        for child in disk.children:
            child_node, subtree_h = self._place_child(child, left, y, scene, disk_node)
            col_w = max(col_w, child_node.boundingRect().width())
            y += subtree_h + NODE_GAP

        return col_w

    def _place_child(self, dev: BlockDevice, left: float, top: float,
                     scene: QGraphicsScene, parent_node) -> tuple[PartNode, float]:
        """Place *dev* and its children recursively; return (node, total height)."""
        node = PartNode(dev)
        scene.addItem(node)
        node.setPos(left + 20, top)  # indent children relative to parent column
        edge = Edge(parent_node, node)
        scene.addItem(edge)

        total_h = node.boundingRect().height()
        y = top + total_h + NODE_GAP

        for child in dev.children:
            child_node, child_h = self._place_child(child, left + 20, y, scene, node)
            total_h += NODE_GAP + child_h
            y += child_h + NODE_GAP

        return node, total_h

    # ------------------------------------------------------------------ #
    # context menus
    # ------------------------------------------------------------------ #
    def contextMenuEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.pos())
        item = self.scene().itemAt(scene_pos, self.transform())
        # Walk up to find a DiskNode or PartNode (an Edge has no menu)
        while item is not None and not isinstance(item, (DiskNode, PartNode)):
            item = item.parentItem()
        if item is not None:
            self.node_menu_requested.emit(item, event.globalPos())
        else:
            super().contextMenuEvent(event)
