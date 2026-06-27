"""Canvas items: rectangular nodes for disks and their children, joined by
straight parent-child lines."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsObject, QGraphicsPathItem

from diskgrip.core.model import BlockDevice
from diskgrip.ui import theme

PAD = 9.0
MIN_W = 170.0
MAX_TEXT_W = 260.0
RADIUS = 6.0

# Media-class labels for the disk title line
_MEDIA_LABEL = {
    "ssd": "SSD",
    "hdd": "HDD",
    "usb": "USB",
    "optical": "Optical",
    "virtual": "Virtual disk",
    "unknown": "Block device",
}


class BaseNode(QGraphicsObject):
    """A flat rectangle with a bold title and smaller detail lines."""

    moved = Signal()
    drag_finished = Signal()

    def __init__(self, title: str, lines: list[str], body: QColor, border: QColor):
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(1)

        self.key: str | None = None
        self._body = body
        self._border = border
        self._press_pos: QPointF | None = None

        base = QApplication.font()
        self._title_font = QFont(base)
        self._title_font.setBold(True)
        self._line_font = QFont(base)
        self._line_font.setPointSizeF(max(7.0, base.pointSizeF() - 1.5))

        tm = QFontMetricsF(self._title_font)
        lm = QFontMetricsF(self._line_font)
        self._title = tm.elidedText(title, Qt.TextElideMode.ElideRight, MAX_TEXT_W)
        self._lines = [lm.elidedText(ln, Qt.TextElideMode.ElideRight, MAX_TEXT_W)
                       for ln in lines]
        self._title_h = tm.height()
        self._line_h = lm.height()

        widest = max(
            [tm.horizontalAdvance(self._title)]
            + [lm.horizontalAdvance(ln) for ln in self._lines],
            default=0,
        )
        self._w = min(max(MIN_W, widest + 2 * PAD), MAX_TEXT_W + 2 * PAD)
        self._h = PAD + self._title_h + len(self._lines) * self._line_h + PAD

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._w, self._h)

    def anchor(self) -> QPointF:
        return self.sceneBoundingRect().center()

    def paint(self, painter, option, widget=None) -> None:
        rect = self.boundingRect().adjusted(0.5, 0.5, -0.5, -0.5)
        pen = QPen(self._border, 2.0 if self.isSelected() else 1.0)
        painter.setPen(pen)
        painter.setBrush(self._body)
        painter.drawRoundedRect(rect, RADIUS, RADIUS)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setFont(self._title_font)
        painter.setPen(QPen(theme.text()))
        tm = QFontMetricsF(self._title_font)
        painter.drawText(QPointF(PAD, PAD + tm.ascent()), self._title)

        painter.setFont(self._line_font)
        painter.setPen(QPen(theme.text_dim()))
        lm = QFontMetricsF(self._line_font)
        y = PAD + self._title_h
        for line in self._lines:
            painter.drawText(QPointF(PAD, y + lm.ascent()), line)
            y += self._line_h

        self._paint_extra(painter)

    def _paint_extra(self, painter) -> None:
        pass

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.moved.emit()
        return super().itemChange(change, value)

    def mousePressEvent(self, event) -> None:
        self._press_pos = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self._press_pos is not None and (self.pos() - self._press_pos).manhattanLength() > 4:
            self.drag_finished.emit()
        self._press_pos = None


def _disk_lines(dev: BlockDevice) -> list[str]:
    lines = []
    if dev.model:
        lines.append(dev.model)
    parts = []
    if dev.size:
        parts.append(dev.size)
    if dev.transport:
        parts.append(dev.transport.upper())
    if dev.serial:
        parts.append(dev.serial)
    if parts:
        lines.append("  ".join(parts))
    if dev.removable:
        lines.append("removable")
    return lines


def _part_lines(dev: BlockDevice) -> list[str]:
    lines = []
    if dev.size:
        sz = dev.size
        if dev.fsuse:
            sz += f"  ({dev.fsuse} used)"
        lines.append(sz)
    if dev.fstype:
        fs = dev.fstype
        if dev.label:
            fs += f'  "{dev.label}"'
        lines.append(fs)
    elif dev.parttype:
        lines.append(dev.parttype)
    if dev.mounted:
        mp = ", ".join(dev.mountpoints)
        avail = f"  {dev.fsavail} free" if dev.fsavail else ""
        lines.append(f"→ {mp}{avail}")
    elif dev.has_filesystem:
        lines.append("→ not mounted")
    if dev.readonly:
        lines.append("read-only")
    return lines


class DiskNode(BaseNode):
    """A whole-disk (or loop) device."""

    def __init__(self, dev: BlockDevice):
        media = dev.media
        body, border = theme.disk_node(media)
        title = _MEDIA_LABEL.get(media, "Disk") + "  " + dev.name
        super().__init__(title, _disk_lines(dev), body, border)
        self.dev = dev
        self.key = f"disk:{dev.name}"


class PartNode(BaseNode):
    """A partition, LVM volume, LUKS container, or other child device."""

    def __init__(self, dev: BlockDevice):
        body, border = theme.part_node(dev.kind, dev.mounted, dev.fstype)
        super().__init__(dev.name, _part_lines(dev), body, border)
        self.dev = dev
        self.key = f"dev:{dev.name}"


class Edge(QGraphicsPathItem):
    """Straight line between the anchor points of two nodes."""

    def __init__(self, a: BaseNode, b: BaseNode):
        super().__init__()
        self.setZValue(0)
        self.setPen(theme.edge_pen())
        self._a = a
        self._b = b
        a.moved.connect(self.refresh)
        b.moved.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        path = QPainterPath(self._a.anchor())
        path.lineTo(self._b.anchor())
        self.setPath(path)
