"""Иконка программы: клетки моря, корабль и попадание, нарисованные тем же кодом цветов,
что и поле. Её же может собрать в .ico build.py."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

from game.ui.board import colors


def render(size=256):
    c = colors("dark")
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size, size), size * 0.2, size * 0.2)
    p.setClipPath(clip)
    p.fillRect(QRectF(0, 0, size, size), c["water"])
    cell = size / 4
    if size >= 32:
        p.setPen(QPen(c["line"], max(1.0, size / 96)))
        for i in range(1, 4):
            p.drawLine(QPointF(i * cell, 0), QPointF(i * cell, size))
            p.drawLine(QPointF(0, i * cell), QPointF(size, i * cell))
    ship = QRectF(cell * 0.5, cell * 1.5, cell * 3, cell).adjusted(size * 0.03, size * 0.03, -size * 0.03, -size * 0.03)
    p.setPen(QPen(c["ship_edge"], max(1.0, size / 80)))
    p.setBrush(c["ship"])
    p.drawRoundedRect(ship, ship.height() * 0.35, ship.height() * 0.35)
    pen = QPen(c["hit"], max(2.0, size * 0.07))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    m = cell * 0.3
    r = QRectF(cell * 2.5, cell * 1.5, cell, cell)
    p.drawLine(r.topLeft() + QPointF(m, m), r.bottomRight() - QPointF(m, m))
    p.drawLine(r.topRight() + QPointF(-m, m), r.bottomLeft() + QPointF(m, -m))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(c["miss"]))
    p.drawEllipse(QPointF(cell * 1.5, cell * 3.2), size * 0.035, size * 0.035)
    p.end()
    return img


def app_icon():
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(render(s)))
    return icon
