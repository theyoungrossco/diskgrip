"""Canvas items: DiskBar with nested PartSegments (gparted-style), plus legacy
rectangular nodes and connector edges kept for cross-device relationships."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsObject, QGraphicsPathItem

from diskgrip.core.model import BlockDevice
from diskgrip.ui import theme

# ── DiskBar / PartSegment constants ────────────────────────────────────────────
BAR_W = 800.0          # all disk bars share this fixed width
DISK_HEADER_H = 32.0   # height of the disk metadata strip above the partition bar
BAR_H = 56.0           # height of the partition-segment area
BAR_CORNER_R = 5.0
MIN_SEG_W = 2.0        # minimum rendered segment width in pixels

# ── Legacy BaseNode / PartNode / DiskNode constants ───────────────────────────
PAD = 9.0
MIN_W = 170.0
MAX_TEXT_W = 260.0
RADIUS = 6.0

_MEDIA_LABEL = {
    "ssd": "SSD",
    "hdd": "HDD",
    "usb": "USB",
    "optical": "Optical",
    "virtual": "Virtual disk",
    "unknown": "Block device",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seg_detail_lines(dev: BlockDevice) -> list[str]:
    """Short info lines for a partition segment: size, fs/label, mount, flags."""
    lines = []
    if dev.size:
        sz = dev.size
        if dev.fsuse:
            sz += f" ({dev.fsuse})"
        lines.append(sz)
    if dev.fstype:
        fs = dev.fstype
        if dev.label:
            fs += f' "{dev.label}"'
        lines.append(fs)
    elif dev.parttype:
        lines.append(dev.parttype)
    if dev.mountpoints:
        lines.append(dev.mountpoints[0])
    if dev.partflags:
        lines.append("  ".join(dev.partflags))
    return lines


def _compute_segments(
    disk: BlockDevice, bar_w: float
) -> list[tuple[float, float, BlockDevice | None]]:
    """Compute (x_offset, width, device_or_None) segments for a DiskBar.

    Partitions are proportional to their byte size relative to the disk.
    Any remaining space (unallocated / GPT overhead) that is at least 0.5 %
    of the disk appears as a trailing segment with device=None.
    Falls back to equal widths when byte counts are not available.
    """
    children = disk.children
    if not children:
        return [(0.0, bar_w, None)]

    disk_bytes = disk.size_bytes
    if disk_bytes and disk_bytes > 0:
        sorted_parts = sorted(children, key=lambda c: c.start if c.start is not None else 0)
        segments: list[tuple[float, float, BlockDevice | None]] = []
        used_bytes = 0
        for child in sorted_parts:
            child_bytes = child.size_bytes or 0
            x = bar_w * used_bytes / disk_bytes
            w = max(bar_w * child_bytes / disk_bytes, MIN_SEG_W)
            segments.append((x, w, child))
            used_bytes += child_bytes
        # Trailing unallocated (>0.5% of disk is worth rendering)
        remaining = disk_bytes - used_bytes
        if remaining > disk_bytes * 0.005:
            rem_w = bar_w * remaining / disk_bytes
            if rem_w >= 4.0:
                segments.append((bar_w * used_bytes / disk_bytes, rem_w, None))
        return segments
    else:
        n = len(children)
        w = bar_w / n
        return [(i * w, w, child) for i, child in enumerate(children)]


# ── gparted-style items ───────────────────────────────────────────────────────

class PartSegment(QGraphicsItem):
    """One proportional slice inside a DiskBar — one partition or unallocated gap."""

    def __init__(
        self,
        dev: BlockDevice | None,
        x: float,
        w: float,
        parent: QGraphicsItem,
    ) -> None:
        super().__init__(parent)
        self.setPos(x, DISK_HEADER_H)
        self.dev = dev
        self.key: str | None = f"dev:{dev.name}" if dev else None
        self._w = w

        if dev is not None:
            self._body, self._border = theme.part_node(dev.kind, dev.mounted, dev.fstype)
        else:
            self._body, self._border = theme.unallocated_segment()

        base = QApplication.font()
        self._name_font = QFont(base)
        self._name_font.setBold(True)
        self._name_font.setPointSizeF(max(6.5, base.pointSizeF() - 1.5))
        self._detail_font = QFont(base)
        self._detail_font.setPointSizeF(max(5.5, base.pointSizeF() - 2.5))

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._w, BAR_H)

    def paint(self, painter, option, widget=None) -> None:
        w = self._w
        h = BAR_H
        pen = QPen(self._border, 1.0)
        painter.setPen(pen)
        painter.setBrush(self._body)
        # Hairline gap between segments via inset
        painter.drawRect(QRectF(0.5, 0, w - 1.0, h))

        dev = self.dev
        if dev is None:
            if w > 36:
                painter.setPen(QPen(theme.text_dim()))
                painter.setFont(self._detail_font)
                painter.drawText(
                    QRectF(2, 0, w - 4, h),
                    Qt.AlignmentFlag.AlignCenter,
                    "free",
                )
            return

        if w < 14:
            return

        nm = QFontMetricsF(self._name_font)
        painter.setFont(self._name_font)
        painter.setPen(QPen(theme.text()))
        painter.drawText(
            QPointF(4, 3 + nm.ascent()),
            nm.elidedText(dev.name, Qt.TextElideMode.ElideRight, w - 6),
        )

        dm = QFontMetricsF(self._detail_font)
        painter.setFont(self._detail_font)
        painter.setPen(QPen(theme.text_dim()))
        y = 3 + nm.height() + 1
        for line in _seg_detail_lines(dev):
            if y + dm.height() > h - 2:
                break
            painter.drawText(
                QPointF(4, y + dm.ascent()),
                dm.elidedText(line, Qt.TextElideMode.ElideRight, w - 6),
            )
            y += dm.height()


class DiskBar(QGraphicsObject):
    """A gparted-style horizontal bar: disk header + proportional partition segments."""

    moved = Signal()
    drag_finished = Signal()

    def __init__(self, dev: BlockDevice) -> None:
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        self.setZValue(1)

        self.dev = dev
        self.key = f"disk:{dev.name}"
        self._press_pos: QPointF | None = None
        self._body, self._border = theme.disk_node(dev.media)

        base = QApplication.font()
        self._header_font = QFont(base)
        self._header_font.setBold(True)
        self._header_font.setPointSizeF(max(7.5, base.pointSizeF() - 0.5))

        for x, w, child in _compute_segments(dev, BAR_W):
            PartSegment(child, x, max(w, MIN_SEG_W), self)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, BAR_W, DISK_HEADER_H + BAR_H)

    def anchor(self) -> QPointF:
        return self.sceneBoundingRect().center()

    def paint(self, painter, option, widget=None) -> None:
        w = BAR_W
        total_h = DISK_HEADER_H + BAR_H

        # Outer rounded rect (disk border colour)
        rect = QRectF(0.5, 0.5, w - 1, total_h - 1)
        pen = QPen(self._border, 2.0 if self.isSelected() else 1.0)
        painter.setPen(pen)
        painter.setBrush(self._body)
        painter.drawRoundedRect(rect, BAR_CORNER_R, BAR_CORNER_R)

        # Background for the segment area (children paint on top)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.background())
        painter.drawRect(QRectF(1, DISK_HEADER_H, w - 2, BAR_H))

        # Divider between header and segment area
        painter.setPen(QPen(self._border, 0.5))
        painter.drawLine(QPointF(0.5, DISK_HEADER_H), QPointF(w - 0.5, DISK_HEADER_H))

        # Header text: media label, device name, size, model, pttype
        dev = self.dev
        parts = [_MEDIA_LABEL.get(dev.media, "Disk"), dev.name]
        if dev.size:
            parts.append(dev.size)
        if dev.model:
            parts.append(dev.model)
        if dev.pttype:
            parts.append(dev.pttype.upper())
        title = "  ".join(parts)

        hm = QFontMetricsF(self._header_font)
        painter.setFont(self._header_font)
        painter.setPen(QPen(theme.text()))
        text_y = (DISK_HEADER_H - hm.height()) / 2 + hm.ascent()
        painter.drawText(
            QPointF(8, text_y),
            hm.elidedText(title, Qt.TextElideMode.ElideRight, w - 16),
        )

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


# ── Legacy rectangular node items (kept for cross-device edges: LVM, RAID) ───

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
    """A whole-disk (or loop) device (legacy rectangular node)."""

    def __init__(self, dev: BlockDevice):
        media = dev.media
        body, border = theme.disk_node(media)
        title = _MEDIA_LABEL.get(media, "Disk") + "  " + dev.name
        super().__init__(title, _disk_lines(dev), body, border)
        self.dev = dev
        self.key = f"disk:{dev.name}"


class PartNode(BaseNode):
    """A partition, LVM volume, LUKS container, or other child device (legacy)."""

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
