"""Вид страниц «Настройки» и «Статистика» Морского боя - «штурманская рубка», как стартовое меню
(правило автора 17.10: настройки и статистика у каждой игры свои).

Фон страниц - неподвижная морская карта: ночное море (днём - бумажная карта), штурманская сетка с
буквами и цифрами, роза ветров в правом нижнем углу и волны внизу. Карточки и кнопки - таблички с
полосой сонара слева (stripe), главная кнопка - сигнальная оранжевая; заголовок - морской Cambria,
подписи - Corbel, числа и подписи таблиц - Consolas, переключатели - капсулы.

Механизм общий (aikit.skin), здесь - только стиль Морского боя.
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF

from aikit.skin import Skin
from game.ui.menu import paint_chart, paint_waves
from game.ui.menu import palette as sea_palette


def _pal(name):
    s = sea_palette(name)
    return {"bg": s["bg"], "surface": s["plate"], "surface2": s["plate_hi"], "border": s["panel_line"],
            "text": s["ink"], "muted": s["muted"], "accent": s["sonar"], "accent_text": s["bg"],
            "good": s["ok"], "bad": s["bad"], "warn": s["accent"], "grid": s["grid"],
            "stripe": s["sonar_dim"], "button": s["plate"], "field": s["bg2"]}


class SeaSkin(Skin):
    key = "seawar-chartroom"
    palettes = {"dark": _pal("dark"), "light": _pal("light")}
    heading_family = "Constantia"
    heading_px = 34
    heading_spacing = 0.03
    section_family = "Constantia"
    section_color = "accent"
    body_family = "Corbel"
    mono_family = "Consolas"
    radius = 6
    control_radius = 6
    card_style = "stripe"
    button_style = "stripe"
    card_alpha = 230

    def extra_qss(self, p, theme):
        sea = sea_palette(theme)
        return f"""
QLabel {{ font-size: 14px; }}
QLabel#section {{ font-size: 19px; }}
QLabel#hint {{ font-family: "Consolas"; }}
QPushButton {{ font-family: "Corbel"; font-size: 15px; font-weight: 700; }}
QPushButton#primary {{ background: {sea['accent']}; color: {sea['accent_text']}; border-color: {sea['accent']};
    border-left: 4px solid {sea['ink']}; }}
QPushButton#seg {{ border-radius: 13px; }}
QHeaderView::section {{ font-family: "Consolas"; border-bottom: 2px solid {sea['sonar_dim']}; }}
QTableWidget {{ font-family: "Consolas"; }}
QLabel#tileValue {{ color: {sea['accent']}; }}
"""

    def paint_backdrop(self, p, w, h, pal, theme):
        sea = sea_palette(theme)
        lang = getattr(self, "lang", "ru")
        paint_chart(p, w, h, sea, lang)
        paint_waves(p, w, h, 1.3, sea)
        compass(p, QPointF(w - min(w, h) * 0.16, h - min(w, h) * 0.26), min(w, h) * 0.11, sea)
        veil = QColor(sea["bg"])
        veil.setAlphaF(0.35)
        p.fillRect(0, 0, w, h, veil)


def compass(p, c, r, sea):
    """Роза ветров: круг с делениями, четыре луча и буква севера."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    ring = QColor(sea["sonar_dim"])
    p.setPen(QPen(ring, 1.4))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, r, r)
    p.drawEllipse(c, r * 0.72, r * 0.72)
    for a in range(0, 360, 10):
        rad = math.radians(a)
        k = 0.88 if a % 30 else 0.80
        p.drawLine(QPointF(c.x() + math.cos(rad) * r * k, c.y() - math.sin(rad) * r * k),
                   QPointF(c.x() + math.cos(rad) * r, c.y() - math.sin(rad) * r))
    for a, long in ((90, 1.0), (0, 0.8), (180, 0.8), (270, 0.8), (45, 0.5), (135, 0.5), (225, 0.5), (315, 0.5)):
        rad = math.radians(a)
        tip = QPointF(c.x() + math.cos(rad) * r * 0.95 * long, c.y() - math.sin(rad) * r * 0.95 * long)
        side = math.radians(a + 90)
        wdt = r * 0.09
        left = QPointF(c.x() + math.cos(side) * wdt, c.y() - math.sin(side) * wdt)
        right = QPointF(c.x() - math.cos(side) * wdt, c.y() + math.sin(side) * wdt)
        col = QColor(sea["accent"] if a == 90 else sea["sonar_dim"])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawPolygon(QPolygonF([left, tip, right, c]))
    f = QFont("Cambria")
    f.setPixelSize(max(10, round(r * 0.28)))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(sea["accent"]))
    p.drawText(QRectF(c.x() - r, c.y() - r * 1.45, 2 * r, r * 0.4), int(Qt.AlignmentFlag.AlignCenter), "N")
    p.restore()


SKIN = SeaSkin()
