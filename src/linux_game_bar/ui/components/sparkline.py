"""Anti-aliased sparkline live graph component with Xbox green gradient fill."""

from typing import List
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QPainterPath, QFont
from PySide6.QtWidgets import QWidget


class SparklineGraph(QWidget):
    """Real-time vector history graph."""

    def __init__(self, title: str = "", unit: str = "%", max_val: float = 100.0, accent: str = "#107C10", parent: QWidget = None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.max_val = max(1.0, max_val)
        self.accent_color = QColor(accent)
        self.data: List[float] = []
        self.setMinimumHeight(75)

    def set_data(self, values: List[float]) -> None:
        self.data = values
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Background card
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(36, 36, 42, 180))
        painter.drawRoundedRect(0, 0, w, h, 6, 6)

        # Draw grid lines (50%)
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1, Qt.DashLine))
        mid_y = h / 2.0
        painter.drawLine(0, int(mid_y), w, int(mid_y))

        # Title and Current Value
        painter.setPen(QColor(160, 160, 165))
        font = QFont("Segoe UI, Ubuntu, sans-serif", 9)
        painter.setFont(font)
        painter.drawText(8, 16, self.title)

        cur_val = self.data[-1] if self.data else 0.0
        val_str = f"{cur_val:.1f}{self.unit}"
        painter.setPen(QColor(255, 255, 255))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(w - painter.fontMetrics().horizontalAdvance(val_str) - 8, 16, val_str)

        if len(self.data) < 2:
            return

        # Graph plot area (leave 22px at top for header)
        top_offset = 22.0
        plot_h = h - top_offset - 6.0
        step_x = (w - 12.0) / float(len(self.data) - 1)

        points = []
        for i, val in enumerate(self.data):
            x = 6.0 + i * step_x
            clamped = max(0.0, min(self.max_val, val))
            norm = clamped / self.max_val
            y = top_offset + plot_h - (norm * plot_h)
            points.append(QPointF(x, y))

        # Construct path for gradient fill
        fill_path = QPainterPath()
        fill_path.moveTo(points[0].x(), top_offset + plot_h)
        for pt in points:
            fill_path.lineTo(pt)
        fill_path.lineTo(points[-1].x(), top_offset + plot_h)
        fill_path.closeSubpath()

        # Gradient fill
        gradient = QLinearGradient(0, top_offset, 0, top_offset + plot_h)
        grad_color = QColor(self.accent_color)
        grad_color.setAlpha(120)
        gradient.setColorAt(0.0, grad_color)
        grad_color.setAlpha(15)
        gradient.setColorAt(1.0, grad_color)

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(fill_path)

        # Plot line
        line_path = QPainterPath()
        line_path.moveTo(points[0])
        for pt in points[1:]:
            line_path.lineTo(pt)

        painter.setPen(QPen(self.accent_color, 2.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(line_path)
