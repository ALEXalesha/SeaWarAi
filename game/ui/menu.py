"""Стартовое меню Морского боя - «штурманская рубка».

Свой стиль (правило автора 17.10: у каждой игры своё меню, и боковые панели тоже): ночное море,
штурманская сетка с буквами А-К и цифрами, справа - экран сонара: вращается луч, за ним гаснет
след, отметки кораблей вспыхивают, когда луч проходит по ним, по попаданиям расходятся круги;
внизу катятся волны. Слева - вахтенный журнал: заголовок морским Cambria с чертой сигнального
цвета, кнопки с полосой слева (как таблички на переборке), переключатели-капсулы. Светлая тема -
морская карта на бумаге. Боковая панель боя, расстановка и поля - в тех же цветах.

Общее из aikit.menu - только живой фон (Backdrop), заголовок Title и законы раскладки.
"""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QConicalGradient, QFont, QFontMetrics, QLinearGradient, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout

from aikit.menu import Backdrop, Title
from aikit.widgets import button, fit_segments, label, segmented
from game.ai.agents import LEVELS
from game.core.rules import LETTERS

PALETTES = {
    "dark": {
        "bg": "#06131f", "bg2": "#0b2133", "grid": "#123349", "coord": "#4b7690", "ink": "#e3edf3",
        "muted": "#8fb0c3", "sonar": "#3fe0c8", "sonar_dim": "#1b6f66", "accent": "#ff8a3d",
        "accent_text": "#1b0d02", "panel": "rgba(7, 24, 38, 225)", "panel_line": "#1f4d68",
        "plate": "#0f2a3f", "plate_hi": "#173a54", "wave": "#2a6a8a",
        # поля боя
        "water": "#0d2a40", "line": "#1d4c68", "ship": "#7f97ad", "ship_edge": "#e3edf3",
        "hit": "#ff5b4a", "miss": "#5f8aa3", "auto": "#163b55", "sunk": "#3b4d5e", "heat": "#ff8a3d",
        "ok": "#3fe0c8", "bad": "#ff5b4a", "last": "#ffd166",
    },
    "light": {
        "bg": "#ebe5d3", "bg2": "#dfe6e2", "grid": "#b9c9cc", "coord": "#5d7a86", "ink": "#16304a",
        "muted": "#4f6573", "sonar": "#0f7f73", "sonar_dim": "#8fc0b8", "accent": "#c8501e",
        "accent_text": "#fff8ef", "panel": "rgba(250, 247, 238, 235)", "panel_line": "#9fb4bc",
        "plate": "#f4f0e4", "plate_hi": "#e6e0cd", "wave": "#7fa7b6",
        "water": "#d5e5ea", "line": "#9dbac6", "ship": "#5b7387", "ship_edge": "#16304a",
        "hit": "#cf3a26", "miss": "#6f8a97", "auto": "#c2d4da", "sunk": "#9aa6ad", "heat": "#c8501e",
        "ok": "#0f7f73", "bad": "#cf3a26", "last": "#b07a10",
    },
}

SWEEP = 4.8          # секунд на оборот луча
TRAIL = 70.0         # градусов следа за лучом


def palette(name):
    return PALETTES.get(name, PALETTES["dark"])


def contacts(seed=11):
    """Отметки на сонаре: (угол°, доля радиуса, вид, длина, поворот). Детерминировано."""
    rng = random.Random(seed)
    out = []
    for k in range(9):
        angle = (k * 40 + rng.uniform(-12, 12)) % 360
        dist = rng.uniform(0.22, 0.88)
        kind = "ship" if k % 3 else "hit"
        out.append((angle, dist, kind, rng.choice((1, 2, 3, 4)), rng.uniform(0, 180)))
    return out


def sweep_angle(t):
    """Угол луча в градусах (по часовой от «востока», как рисует Qt - против часовой)."""
    return (t / SWEEP * 360.0) % 360.0


def glow(angle, beam):
    """Насколько ярка отметка: 1 - луч только что прошёл, дальше гаснет по следу."""
    behind = (beam - angle) % 360.0
    return max(0.0, 1.0 - behind / 300.0) ** 2


class Sonar(Backdrop):
    """Фон: ночное море, штурманская сетка, сонар и волны."""

    FPS = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.contacts = contacts()
        self.lang = "ru"
        self.free_left = 0             # сонар - правее этой границы (раскладка меню сдвигает)

    def scope(self, w, h):
        """Центр и радиус сонара: в свободной части справа от колонки меню, не заходя на неё."""
        left = max(self.free_left, w * 0.1)
        r = max(40.0, min(h * 0.40, (w - left) / 2 - 18))
        return QPointF((left + w) / 2, h * 0.5), r

    def scope_rect(self):
        c, r = self.scope(self.width(), self.height())
        return QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)

    def paint_scene(self, p, w, h, t):
        pal = palette(self.theme_name)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor(pal["bg"]))
        g.setColorAt(1, QColor(pal["bg2"]))
        p.fillRect(0, 0, w, h, g)
        # штурманская сетка с подписями
        cell = max(34.0, h / 13.0)
        p.setPen(QPen(QColor(pal["grid"]), 1))
        x = cell * 1.2
        while x < w:
            p.drawLine(QPointF(x, cell * 0.8), QPointF(x, h))
            x += cell
        y = cell * 0.8
        while y < h:
            p.drawLine(QPointF(cell * 1.2, y), QPointF(w, y))
            y += cell
        f = QFont("Consolas")
        f.setPixelSize(max(10, round(cell * 0.32)))
        p.setFont(f)
        p.setPen(QColor(pal["coord"]))
        letters = LETTERS.get(self.lang, LETTERS["ru"])
        for i, letter in enumerate(letters):
            p.drawText(QRectF(cell * 1.2 + i * cell, cell * 0.2, cell, cell * 0.6), int(Qt.AlignmentFlag.AlignCenter), letter)
        for j in range(10):
            p.drawText(QRectF(cell * 0.2, cell * 0.8 + j * cell, cell, cell), int(Qt.AlignmentFlag.AlignCenter), str(j + 1))
        self._waves(p, w, h, t, pal)
        self._scope(p, w, h, t, pal)

    def _waves(self, p, w, h, t, pal):
        for k in range(3):
            col = QColor(pal["wave"])
            col.setAlpha(110 - k * 28)
            p.setPen(QPen(col, 2.0 + k * 0.6))
            path = QPainterPath()
            base = h * (0.86 + k * 0.045)
            amp = h * (0.010 + 0.004 * k)
            step = max(6.0, w / 160)
            x = 0.0
            path.moveTo(0, base)
            while x <= w + step:
                y = base + amp * math.sin(x / (w / (7 + k * 2)) * 2 * math.pi + t * (0.8 + 0.35 * k))
                path.lineTo(x, y)
                x += step
            p.drawPath(path)

    def _scope(self, p, w, h, t, pal):
        c, r = self.scope(w, h)
        disc = QColor(pal["bg"])
        disc.setAlpha(200)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(disc)
        p.drawEllipse(c, r, r)
        ring = QColor(pal["sonar_dim"])
        p.setBrush(Qt.BrushStyle.NoBrush)
        for k in range(1, 5):
            p.setPen(QPen(ring, 1.4 if k < 4 else 2.4))
            p.drawEllipse(c, r * k / 4, r * k / 4)
        p.setPen(QPen(ring, 1.0))
        for a in range(0, 360, 30):
            rad = math.radians(a)
            p.drawLine(c, QPointF(c.x() + math.cos(rad) * r, c.y() - math.sin(rad) * r))
        beam = sweep_angle(t)
        # след луча - конический градиент
        cg = QConicalGradient(c, beam)
        head = QColor(pal["sonar"])
        head.setAlpha(150)
        tail = QColor(pal["sonar"])
        tail.setAlpha(0)
        cg.setColorAt(0.0, head)
        cg.setColorAt(TRAIL / 360.0, tail)
        cg.setColorAt(1.0, tail)
        path = QPainterPath()
        path.moveTo(c)
        path.arcTo(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), beam, -TRAIL)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cg)
        p.drawPath(path)
        p.setPen(QPen(QColor(pal["sonar"]), 2.2))
        rad = math.radians(beam)
        p.drawLine(c, QPointF(c.x() + math.cos(rad) * r, c.y() - math.sin(rad) * r))
        # отметки
        for angle, dist, kind, length, turn in self.contacts:
            a = glow(angle, beam)
            if a <= 0.02:
                continue
            rad = math.radians(angle)
            pos = QPointF(c.x() + math.cos(rad) * r * dist, c.y() - math.sin(rad) * r * dist)
            size = r * 0.045
            if kind == "ship":
                col = QColor(pal["sonar"])
                col.setAlphaF(min(1.0, 0.25 + 0.75 * a))
                p.save()
                p.translate(pos)
                p.rotate(turn)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(QRectF(-size * length, -size * 0.55, size * 2 * length, size * 1.1), size * 0.5, size * 0.5)
                p.restore()
            else:
                col = QColor(pal["accent"])
                col.setAlphaF(min(1.0, 0.3 + 0.7 * a))
                p.setPen(QPen(col, max(2.0, size * 0.45)))
                p.drawLine(QPointF(pos.x() - size, pos.y() - size), QPointF(pos.x() + size, pos.y() + size))
                p.drawLine(QPointF(pos.x() - size, pos.y() + size), QPointF(pos.x() + size, pos.y() - size))
                ripple = (1.0 - a) * size * 6
                col.setAlphaF(max(0.0, 0.6 * a))
                p.setPen(QPen(col, 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(pos, size + ripple, size + ripple)
        p.setPen(QPen(QColor(pal["sonar"]), 2.0))
        p.setBrush(QColor(pal["sonar"]))
        p.drawEllipse(c, 3.0, 3.0)


def plate_qss(pal, k=1.0, scope=""):
    """Кнопки-таблички с полосой слева, капсулы-переключатели, подписи. scope - префикс селектора."""
    def px(v):
        return f"{max(1, round(v * k))}px"
    s = scope
    return f"""
{s}QPushButton {{
    font-family: "Corbel", "Segoe UI"; font-size: {px(17)}; font-weight: 700;
    text-align: left; padding: {px(10)} {px(16)} {px(10)} {px(18)};
    background: {pal['plate']}; color: {pal['ink']};
    border: 1px solid {pal['panel_line']}; border-left: {px(6)} solid {pal['sonar_dim']};
    border-radius: {px(6)};
}}
{s}QPushButton:hover {{ border-left-color: {pal['sonar']}; background: {pal['plate_hi']}; }}
{s}QPushButton:disabled {{ color: {pal['muted']}; border-left-color: {pal['panel_line']}; }}
{s}QPushButton#primary, {s}QPushButton#menuPrimary {{
    background: {pal['accent']}; color: {pal['accent_text']};
    border: 1px solid {pal['accent']}; border-left: {px(6)} solid {pal['ink']};
}}
{s}QPushButton#seg {{
    font-family: "Corbel", "Segoe UI"; font-size: {px(14)}; font-weight: 600; text-align: center;
    padding: {px(5)} {px(12)}; border-radius: {px(13)};
    border: 1px solid {pal['panel_line']}; background: transparent; color: {pal['ink']};
}}
{s}QPushButton#seg:checked {{ background: {pal['sonar']}; color: {pal['bg']}; border-color: {pal['sonar']}; }}
"""


def page_qss(pal):
    """Страницы расстановки и боя: фон моря, кнопки-таблички."""
    return f"""
QWidget#page {{ background: {pal['bg']}; }}
QLabel {{ color: {pal['ink']}; }}
QLabel#heading {{ font-family: "Cambria", "Georgia"; font-size: 28px; font-weight: 700; color: {pal['ink']}; }}
QLabel#section {{ font-family: "Cambria", "Georgia"; font-size: 17px; font-weight: 700; color: {pal['ink']}; }}
QLabel#muted {{ color: {pal['muted']}; }}
""" + plate_qss(pal, 0.85)


def side_qss(pal):
    """Боковая панель боя - вахтенный журнал: тёмная табличка с тонкой рамкой цвета сонара."""
    return f"""
QFrame#card {{ background: {pal['panel']}; border: 1px solid {pal['panel_line']}; border-top: 3px solid {pal['sonar']}; border-radius: 6px; }}
QLabel {{ color: {pal['ink']}; }}
QLabel#section {{ font-family: "Cambria", "Georgia"; font-size: 17px; font-weight: 700; color: {pal['sonar']}; }}
QLabel#status {{ font-family: "Cambria", "Georgia"; font-size: 21px; font-weight: 700; color: {pal['ink']}; }}
QLabel#statusWin {{ font-family: "Cambria", "Georgia"; font-size: 21px; font-weight: 700; color: {pal['ok']}; }}
QLabel#statusLoss {{ font-family: "Cambria", "Georgia"; font-size: 21px; font-weight: 700; color: {pal['bad']}; }}
QLabel#muted {{ color: {pal['muted']}; }}
QLabel#hint {{ font-family: "Consolas"; font-size: 12px; color: {pal['muted']}; }}
QListWidget {{ font-family: "Consolas"; font-size: 13px; background: {pal['bg']}; color: {pal['ink']};
    border: 1px solid {pal['panel_line']}; border-radius: 4px; }}
QCheckBox {{ color: {pal['ink']}; spacing: 10px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 9px; border: 2px solid {pal['sonar_dim']}; background: transparent; }}
QCheckBox::indicator:checked {{ background: {pal['sonar']}; border-color: {pal['sonar']}; image: none; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
""" + plate_qss(pal, 0.85)


def menu_qss(pal, k):
    def px(v):
        return f"{max(1, round(v * k))}px"
    return f"""
QFrame#log {{ background: {pal['panel']}; border: 1px solid {pal['panel_line']}; border-radius: {px(8)}; }}
QFrame#rule {{ background: {pal['accent']}; border: none; }}
QLabel#seaTag {{ font-family: "Consolas"; font-size: {px(13)}; color: {pal['sonar']}; }}
QLabel#seaSub {{ font-family: "Cambria", "Georgia"; font-style: italic; font-size: {px(16)}; color: {pal['muted']}; }}
QLabel#seaCaption {{ font-family: "Consolas"; font-size: {px(13)}; color: {pal['muted']}; }}
QLabel#seaFoot {{ font-family: "Consolas"; font-size: {px(12)}; color: {pal['muted']}; }}
""" + plate_qss(pal, k)


class MenuPage(Sonar):
    """Меню: слева колонка «вахтенного журнала», справа - сонар на весь рост."""

    def __init__(self, gw):
        super().__init__()
        self.gw = gw
        self.scale = None
        root = QHBoxLayout(self)
        self.root = root
        self.column = QVBoxLayout()
        root.addLayout(self.column)
        root.addStretch(1)
        col = self.column
        col.addStretch(1)
        self.tag = label("", "seaTag")
        col.addWidget(self.tag)
        self.title = Title("Cambria", 64, spacing=0.04, min_px=30, align=Qt.AlignmentFlag.AlignLeft)
        col.addWidget(self.title)
        self.rule = QFrame()
        self.rule.setObjectName("rule")
        col.addWidget(self.rule)
        self.sub = label("", "seaSub", wrap=True)
        col.addWidget(self.sub)
        self.log = QFrame()
        self.log.setObjectName("log")
        grid = QGridLayout(self.log)
        self.grid = grid
        self.captions = {}
        self.seg = {}
        rows = (("level", segmented({lv: "" for lv in LEVELS}, lambda v: gw.change("level", v))),
                ("mode", segmented({"play": "", "demo": ""}, lambda v: gw.change("mode", v))),
                ("touch", segmented({False: "", True: ""}, lambda v: gw.change("corners", v))))
        for r, (key, (box, buttons)) in enumerate(rows):
            cap = label("", "seaCaption")
            self.captions[key] = cap
            grid.addWidget(cap, r, 0)
            grid.addWidget(box, r, 1)
            self.seg[key] = buttons
        grid.setColumnStretch(2, 1)
        col.addWidget(self.log)
        self.play_button = button("", "menuPrimary", lambda: gw.play_clicked())
        self.stats_button = button("", None, lambda: gw.show_page("stats"))
        self.settings_button = button("", None, lambda: gw.show_page("settings"))
        self.buttons = (self.play_button, self.stats_button, self.settings_button)
        for b in self.buttons:
            col.addWidget(b)
        col.addStretch(1)
        self.foot = label("", "seaFoot", wrap=True)
        col.addWidget(self.foot)
        self.apply_scale(force=True)

    def scale_for(self, w, h):
        return round(max(1.0, min(2.4, w / 1280, h / 800)), 2)

    def column_width(self):
        return round(min(560 * self.scale, max(430, self.width() * 0.46)))

    def apply_scale(self, force=False):
        k = self.scale_for(max(self.width(), 900), max(self.height(), 620))
        if not force and k == self.scale:
            return
        self.scale = k
        pal = palette(self.theme_name)
        self.setStyleSheet(menu_qss(pal, k))
        self.title.px = round(64 * k)
        self.title.min_px = round(30 * k)
        self.title.set_color(pal["ink"])
        self.title.updateGeometry()
        self.root.setContentsMargins(round(56 * k), round(30 * k), round(30 * k), round(24 * k))
        self.column.setSpacing(round(10 * k))
        self.rule.setFixedSize(round(120 * k), max(2, round(4 * k)))
        self.grid.setContentsMargins(round(18 * k), round(14 * k), round(18 * k), round(14 * k))
        self.grid.setHorizontalSpacing(round(14 * k))
        self.grid.setVerticalSpacing(round(10 * k))
        f = QFont("Corbel")
        f.setPixelSize(round(14 * k))
        f.setWeight(QFont.Weight.DemiBold)
        fm = QFontMetrics(f)
        for buttons in self.seg.values():
            fit_segments(buttons)
            for b in buttons.values():
                b.setMinimumWidth(max(b.minimumWidth(), fm.horizontalAdvance(b.text()) + 2 * round(12 * k) + 8))
        self._fit_width()

    def _fit_width(self):
        w = self.column_width()
        for x in (self.tag, self.title, self.sub, self.log, self.foot) + self.buttons:
            x.setFixedWidth(w)
        # сонар - в свободной части справа от колонки
        self.free_left = self.root.contentsMargins().left() + w + round(24 * self.scale)

    def set_theme(self, name):
        super().set_theme(name)
        self.apply_scale(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_scale()
        self._fit_width()

    def sync(self, s):
        self.seg["level"][s["level"]].setChecked(True)
        self.seg["mode"][s["mode"]].setChecked(True)
        self.seg["touch"][s["corners"]].setChecked(True)

    def retranslate(self):
        t = self.gw.t
        self.lang = self.gw.ctx.lang
        self.title.setText(t("app_title"))
        self.sub.setText(t("app_sub"))
        self.tag.setText(t("menu_tag"))
        for key, cap in self.captions.items():
            cap.setText(t(key).upper())
        for k, b in self.seg["level"].items():
            b.setText(t(k))
        for k, b in self.seg["mode"].items():
            b.setText(t("mode_" + k))
        self.seg["touch"][False].setText(t("touch_strict"))
        self.seg["touch"][True].setText(t("touch_corners"))
        self.play_button.setText(t("play").upper())
        self.stats_button.setText(t("stats").upper())
        self.settings_button.setText(t("settings").upper())
        self.apply_scale(force=True)
        self.sync(self.gw.settings)

    def set_foot(self, text):
        self.foot.setText(text)
