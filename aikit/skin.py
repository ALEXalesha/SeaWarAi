"""Страницы «Настройки» и «Статистика» и боковая панель партии: общая ЛОГИКА, вид у каждой игры свой.

Правило автора 17.10.2026 (20:56): «менюшки настроек и статистики тоже должны различаться в ai
играх». Стартовые меню у игр уже свои (aikit.menu), а настройки и статистика оставались общим видом
темы aikit: те же карточки, Segoe UI, синие кнопки во всех играх. Здесь - общий механизм, вид задаёт
игра:

- Skin - стиль игры: цвета обеих тем (недостающие - из темы aikit), шрифты заголовка, текста и
  цифр, форма карточек (CARD_STYLES) и кнопок (BUTTON_STYLES), фон страницы. Игра наследует Skin,
  меняет поля, по желанию рисует свой фон (paint_backdrop), заголовок (paint_heading) и добавляет
  правила таблицы стилей (extra_qss).
- Skin.qss(theme) - таблица стилей страницы: карточки, подписи, кнопки, переключатели, списки,
  ползунки, флажки, таблицы, прокрутка, плитки. Skin.side_qss(theme) - та же форма для боковой
  панели партии (карточка - сама панель).
- SkinPage - страница со своим фоном (рисуется один раз на размер и тему) и шапкой: строка-метка,
  заголовок шрифтом игры и «Назад»; содержимое - в прокрутке без горизонтальной полосы.
- Графики aikit.charts берут у Skin цвета, шрифты и рамку карточки (ChartGrid.set_skin) - карточки
  графиков того же вида, что и карточки страницы.
- StatTiles - плитки с крупными числами (как в AiCar): в ряд, в узком окне - по две или по одной.

Законы (игры зовут их в своих тестах, во всех размерах aikit.menu.SIZES, обеих темах, двух языках):
- page_problems(page) - ничего не обрезано и не за краем (страница не шире окна), соседи не
  налезают, у переносимых подписей нет потолка высоты (на настоящем экране буквы шире, чем
  в offscreen - TicTacToeAi 1.0.0), у графиков пусты clipped и overlaps().
- difference(a, b) - доля заметно разных точек двух кадров: страница игры не должна совпадать
  с общим видом aikit и со страницей другой игры.
"""
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from aikit import theme as aitheme
from aikit.menu import Title, layout_problems
from aikit.widgets import Combo, button, label

QWIDGETSIZE_MAX = 16777215
CARD_STYLES = ("plain", "bevel", "stripe", "glow")
BUTTON_STYLES = ("plain", "bevel", "stripe", "pill", "arcade")


def shade(color, factor):
    """Светлее (factor > 1) или темнее (< 1) - для фасок и нижней кромки аркадных кнопок."""
    c = QColor(color)
    return (c.lighter(round(factor * 100)) if factor >= 1 else c.darker(round(100 / factor))).name()


def rgba(color, alpha):
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {int(alpha)})"


class Skin:
    """Стиль страниц одной игры. Значения по умолчанию - общий вид aikit (тема Paint)."""

    key = "aikit"
    palettes = {}                 # {"dark": {...}, "light": {...}}; цвета - #rrggbb
    heading_family = "Segoe UI"
    heading_px = 30
    heading_weight = QFont.Weight.Bold
    heading_spacing = 0.0         # разрядка заголовка в долях кегля
    heading_upper = False
    heading_color = "text"        # ключ палитры
    section_family = None         # None - как заголовок
    section_color = "text"
    body_family = "Segoe UI"
    mono_family = "Consolas"      # числа: плитки, крупные цифры
    radius = 14                   # карточки
    control_radius = 10           # кнопки, списки
    border = 1
    card_alpha = 255              # < 255 - фон страницы просвечивает сквозь карточки
    card_style = "plain"
    button_style = "plain"

    # --- цвета ---

    def palette(self, theme):
        p = dict(aitheme.palette(theme))
        p.update(self.palettes.get(theme) or self.palettes.get("dark") or {})
        p.setdefault("hi", shade(p["surface2"], 1.35))
        p.setdefault("lo", shade(p["surface2"], 0.6))
        p.setdefault("stripe", p["accent"])
        p.setdefault("button", p["surface2"])
        p.setdefault("button_text", p["text"])
        p.setdefault("field", p["surface2"])          # поля ввода, списки
        return p

    # --- таблица стилей ---

    def card_rule(self, p, selector="QFrame#card"):
        surf = rgba(p["surface"], self.card_alpha)
        r, b = self.radius, self.border
        if self.card_style == "bevel":
            body = (f"background: {surf}; border-style: solid; border-width: 3px; border-radius: 0;"
                    f" border-color: {p['hi']} {p['lo']} {p['lo']} {p['hi']};")
        elif self.card_style == "stripe":
            body = (f"background: {surf}; border: {b}px solid {p['border']}; border-left: 5px solid {p['stripe']};"
                    f" border-radius: {r}px;")
        elif self.card_style == "glow":
            body = f"background: {surf}; border: 2px solid {p['accent']}; border-radius: {r}px;"
        else:
            body = f"background: {surf}; border: {b}px solid {p['border']}; border-radius: {r}px;"
        return f"{selector} {{ {body} }}\n"

    def button_rules(self, p):
        r = self.control_radius
        fam = self.section_family or self.heading_family
        base = f'font-family: "{fam}"; font-size: 14px; font-weight: 600; color: {p["button_text"]};'
        acc, acc_t = p["accent"], p["accent_text"]
        st = self.button_style
        if st == "bevel":
            shape = (f"background: {p['button']}; border-style: solid; border-width: 3px; border-radius: 0;"
                     f" border-color: {p['hi']} {p['lo']} {p['lo']} {p['hi']}; padding: 6px 14px;")
            hover = f"background: {p['hi']};"
            pressed = f"border-color: {p['lo']} {p['hi']} {p['hi']} {p['lo']};"
            primary = f"background: {acc}; color: {acc_t};"
        elif st == "stripe":
            shape = (f"background: {p['button']}; border: 1px solid {p['border']}; border-left: 4px solid {p['stripe']};"
                     f" border-radius: {r}px; padding: 7px 14px;")
            hover = f"border-color: {acc}; border-left-color: {acc};"
            pressed = f"background: {p['surface']};"
            primary = f"background: {acc}; color: {acc_t}; border-color: {acc}; border-left-color: {shade(acc, 0.7)};"
        elif st == "pill":
            shape = (f"background: {rgba(p['button'], 200)}; border: 2px solid {p['accent']}; border-radius: 17px;"
                     f" padding: 6px 18px;")
            hover = f"background: {rgba(p['accent'], 60)};"
            pressed = f"background: {rgba(p['accent'], 110)};"
            primary = f"background: {acc}; color: {acc_t};"
        elif st == "arcade":
            shape = (f"background: {p['button']}; border: none; border-bottom: 4px solid {shade(p['button'], 0.6)};"
                     f" border-radius: {r}px; padding: 7px 16px 5px 16px;")
            hover = f"background: {shade(p['button'], 1.15)};"
            pressed = f"border-bottom-width: 1px; padding-top: 10px;"
            primary = f"background: {acc}; color: {acc_t}; border-bottom-color: {shade(acc, 0.6)};"
        else:
            shape = f"background: {p['button']}; border: 1px solid {p['border']}; border-radius: {r}px; padding: 8px 16px;"
            hover = f"border-color: {acc};"
            pressed = f"background: {p['grid']};"
            primary = f"background: {acc}; color: {acc_t}; border-color: {acc};"
        seg_r = 0 if st == "bevel" else (14 if st == "pill" else max(0, r - 2))
        return f"""
QPushButton {{ {base} {shape} }}
QPushButton:hover {{ {hover} }}
QPushButton:pressed {{ {pressed} }}
QPushButton:disabled {{ color: {p['muted']}; }}
QPushButton:focus {{ outline: none; }}
QPushButton#primary {{ {primary} }}
QPushButton#seg {{
    font-family: "{self.body_family}"; font-size: 13px; font-weight: 500;
    background: {p['field']}; color: {p['text']}; border: 1px solid {p['border']};
    border-radius: {seg_r}px; padding: 5px 10px;
}}
QPushButton#seg:checked {{ background: {acc}; color: {acc_t}; border-color: {acc}; font-weight: 700; }}
"""

    def qss(self, theme):
        p = self.palette(theme)
        sec = self.section_family or self.heading_family
        fr = 0 if self.button_style == "bevel" else self.control_radius
        return f"""
QWidget#skinBody, QScrollArea, QScrollArea > QWidget > QWidget#skinBody {{ background: transparent; }}
QScrollArea {{ border: none; }}
QLabel {{ font-family: "{self.body_family}"; color: {p['text']}; background: transparent; }}
QLabel#skinTag {{ font-family: "{self.mono_family}"; font-size: 12px; color: {p['accent']}; }}
QLabel#section {{ font-family: "{sec}"; font-size: 17px; font-weight: 700; color: {p[self.section_color]}; }}
QLabel#muted {{ color: {p['muted']}; }}
QLabel#hint {{ font-size: 12px; color: {p['muted']}; }}
QLabel#bigNumber {{ font-family: "{self.mono_family}"; font-size: 28px; font-weight: 700; color: {p['text']}; }}
QLabel#status {{ font-family: "{sec}"; font-size: 19px; font-weight: 700; color: {p['text']}; }}
QLabel#statusWin {{ font-family: "{sec}"; font-size: 19px; font-weight: 700; color: {p['good']}; }}
QLabel#statusLoss {{ font-family: "{sec}"; font-size: 19px; font-weight: 700; color: {p['bad']}; }}
QLabel#statusDraw {{ font-family: "{sec}"; font-size: 19px; font-weight: 700; color: {p['warn']}; }}
QLabel#tileValue {{ font-family: "{self.mono_family}"; font-size: 28px; font-weight: 700; color: {p['accent']}; }}
QLabel#tileCaption {{ font-size: 13px; color: {p['text']}; }}
QLabel#tileNote {{ font-size: 12px; color: {p['muted']}; }}
QLabel#skinGroup {{ font-family: "{self.mono_family}"; font-size: 12px; font-weight: 700; color: {p['accent']}; }}
{self.card_rule(p)}{self.card_rule(p, "QFrame#tile")}{self.card_rule(p, "QFrame#settingRow")}{self.button_rules(p)}
QComboBox {{
    font-family: "{self.body_family}"; background: {p['field']}; color: {p['text']};
    border: 1px solid {p['border']}; border-radius: {fr}px; padding: 6px 30px 6px 10px; min-width: 140px;
}}
QComboBox:hover {{ border-color: {p['accent']}; }}
QComboBox::drop-down {{ border: none; background: transparent; width: 26px; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{
    background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border']};
    selection-background-color: {p['accent']}; selection-color: {p['accent_text']};
}}
QSpinBox {{ font-family: "{self.mono_family}"; background: {p['field']}; color: {p['text']};
    border: 1px solid {p['border']}; border-radius: {fr}px; padding: 4px; }}
QSlider::groove:horizontal {{ height: 6px; background: {p['field']}; border-radius: {min(3, fr)}px; }}
QSlider::sub-page:horizontal {{ background: {p['accent']}; border-radius: {min(3, fr)}px; }}
QSlider::handle:horizontal {{ background: {p['text']}; width: 16px; height: 16px; margin: -6px 0;
    border-radius: {8 if fr else 0}px; }}
QCheckBox {{ font-family: "{self.body_family}"; spacing: 10px; color: {p['text']}; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: {min(5, fr)}px;
    border: 2px solid {p['border']}; background: {p['field']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; border-color: {p['accent']}; image: none; }}
QTableWidget, QListWidget {{ font-family: "{self.body_family}"; border: none;
    background: {rgba(p["surface"], self.card_alpha)}; gridline-color: {p['grid']}; color: {p['text']};
    selection-background-color: {p['surface2']}; selection-color: {p['text']}; }}
QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {p['grid']}; }}
QHeaderView::section {{ font-family: "{sec}"; background: {p["surface"]}; color: {p['muted']}; border: none;
    border-bottom: 2px solid {p['accent']}; padding: 6px 8px; font-weight: 700; }}
QHeaderView {{ background: {p["surface"]}; border: none; }}
QTableCornerButton::section {{ background: {p["surface"]}; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: {min(4, fr)}px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QToolTip {{ background: {p['surface']}; color: {p['text']}; border: 1px solid {p['border']}; }}
{self.extra_qss(p, theme)}"""

    def side_qss(self, theme):
        """Боковая панель партии: та же форма, карточка - сама панель (QFrame#card)."""
        return self.qss(theme)

    def extra_qss(self, p, theme):
        """Свои правила игры поверх общих (по желанию)."""
        return ""

    # --- рисование ---

    def paint_backdrop(self, p, w, h, pal, theme):
        """Фон страницы (неподвижный, рисуется один раз на размер и тему). По умолчанию - заливка."""
        p.fillRect(0, 0, w, h, QColor(pal["bg"]))

    def paint_heading(self, p, rect, text, font, pal, align):
        """Заголовок страницы. Игра может нарисовать по-своему: тень, обводка, буквы разного цвета."""
        p.setFont(font)
        p.setPen(QColor(pal[self.heading_color]))
        p.drawText(rect, int(align | Qt.AlignmentFlag.AlignVCenter), text)

    def paint_card(self, p, rect, pal):
        """Рамка карточки графика - того же вида, что QFrame#card в таблице стилей."""
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        surf = QColor(pal["surface"])
        surf.setAlpha(self.card_alpha)
        r = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.card_style == "bevel":
            p.fillRect(rect, surf)
            k = 3
            p.fillRect(QRectF(rect.left(), rect.top(), rect.width(), k), QColor(pal["hi"]))
            p.fillRect(QRectF(rect.left(), rect.top(), k, rect.height()), QColor(pal["hi"]))
            p.fillRect(QRectF(rect.left(), rect.bottom() - k + 1, rect.width(), k), QColor(pal["lo"]))
            p.fillRect(QRectF(rect.right() - k + 1, rect.top(), k, rect.height()), QColor(pal["lo"]))
        elif self.card_style == "stripe":
            path = QPainterPath()
            path.addRoundedRect(r, self.radius, self.radius)
            p.setPen(QPen(QColor(pal["border"]), self.border))
            p.setBrush(surf)
            p.drawPath(path)
            p.setClipPath(path)
            p.fillRect(QRectF(rect.left(), rect.top(), 5, rect.height()), QColor(pal["stripe"]))
        elif self.card_style == "glow":
            glow = QColor(pal["accent"])
            glow.setAlpha(45)
            p.setPen(QPen(glow, 6))
            p.setBrush(surf)
            p.drawRoundedRect(r.adjusted(3, 3, -3, -3), self.radius, self.radius)
            p.setPen(QPen(QColor(pal["accent"]), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), self.radius, self.radius)
        else:
            p.setPen(QPen(QColor(pal["border"]), self.border))
            p.setBrush(surf)
            p.drawRoundedRect(r, self.radius, self.radius)
        p.restore()

    def chart_fonts(self):
        title = QFont(self.section_family or self.heading_family)
        title.setPixelSize(14)
        title.setBold(True)
        small = QFont(self.body_family)
        small.setPixelSize(11)
        return title, small

    def signature(self):
        """Что делает вид игры своим (для законов «разные игры - разный вид»)."""
        p = self.palette("dark")
        return (p["bg"], p["surface"], p["accent"], self.heading_family, self.body_family,
                self.card_style, self.button_style, self.radius)


DEFAULT = Skin()


class SkinTitle(Title):
    """Заголовок страницы: шрифт, разрядка и рисунок - от Skin игры."""

    def __init__(self, skin):
        super().__init__(skin.heading_family, skin.heading_px, weight=skin.heading_weight,
                         spacing=skin.heading_spacing, min_px=max(14, round(skin.heading_px * 0.6)),
                         align=Qt.AlignmentFlag.AlignLeft)
        self.skin = skin
        self.pal = skin.palette("dark")

    def setText(self, text):
        super().setText(text.upper() if self.skin.heading_upper else text)

    def paint_text(self, p, rect, text, font):
        self.skin.paint_heading(p, rect, text, font, self.pal, self.align)


class SkinPage(QWidget):
    """Страница настроек или статистики: фон игры, шапка (метка, заголовок, «Назад»), прокрутка.
    Содержимое класть в self.col (раскладка внутри прокрутки)."""

    def __init__(self, skin=None, back=None, parent=None):
        super().__init__(parent)
        self.skin = skin or DEFAULT
        self.theme = "dark"
        self._cache = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.body = QWidget()
        self.body.setObjectName("skinBody")
        self.scroll.setWidget(self.body)
        outer.addWidget(self.scroll)
        self.col = QVBoxLayout(self.body)
        self.col.setContentsMargins(26, 18, 26, 22)
        self.col.setSpacing(14)
        head = QHBoxLayout()
        head.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.tag = label("", "skinTag")
        self.tag.hide()
        titles.addWidget(self.tag)
        self.heading = SkinTitle(self.skin)
        titles.addWidget(self.heading)
        head.addLayout(titles, 1)
        self.back_button = button("", "back", back)
        head.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.col.addLayout(head)

    def set_tag(self, text):
        self.tag.setText(text)
        self.tag.setVisible(bool(text))

    def palette_now(self):
        return self.skin.palette(self.theme)

    def set_theme(self, theme):
        self.theme = theme
        pal = self.palette_now()
        self.setStyleSheet(self.skin.qss(theme))
        self.heading.pal = pal
        self.heading.update()
        for c in self.findChildren(Combo):
            c.set_arrow_color(pal["text"])
        from aikit.charts import ChartGrid, ChartCard
        for c in self.findChildren(ChartCard):
            c.set_skin(self.skin)
            c.set_theme(theme)
        for g in self.findChildren(ChartGrid):
            g.updateGeometry()
        self._cache = None
        self.update()

    def paintEvent(self, event):
        key = (self.width(), self.height(), self.theme)
        if self._cache is None or self._cache[0] != key:
            pm = QPixmap(max(1, self.width()), max(1, self.height()))
            pm.fill(QColor(self.palette_now()["bg"]))
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.skin.paint_backdrop(p, self.width(), self.height(), self.palette_now(), self.theme)
            p.end()
            self._cache = (key, pm)
        p = QPainter(self)
        p.drawPixmap(0, 0, self._cache[1])
        p.end()


class SettingsList(QWidget):
    """Настройки плашками (QFrame#settingRow - форма карточек игры): слева название и пояснение
    с переносом, справа поле; group(text) - подзаголовок группы. rows[key] = (название, пояснение)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(8)
        self.rows = {}
        self.frames = {}
        self.groups = []

    def group(self, text=""):
        g = label(text.upper(), "skinGroup")
        if self.groups or self.rows:
            self.lay.addSpacing(6)
        self.lay.addWidget(g)
        self.groups.append(g)
        return g

    def set_group(self, i, text):
        self.groups[i].setText(text.upper())

    def add(self, key, widget):
        row = QFrame()
        row.setObjectName("settingRow")
        g = QGridLayout(row)
        g.setContentsMargins(18, 12, 18, 12)
        g.setHorizontalSpacing(22)
        g.setColumnStretch(0, 3)
        g.setColumnStretch(1, 2)
        names = QVBoxLayout()
        names.setSpacing(2)
        title = label("", "section")
        hint = label("", "hint", wrap=True)
        names.addWidget(title)
        names.addWidget(hint)
        g.addLayout(names, 0, 0)
        g.addWidget(widget, 0, 1, Qt.AlignmentFlag.AlignVCenter)
        self.lay.addWidget(row)
        self.rows[key] = (title, hint)
        self.frames[key] = row
        return title, hint


class StatTiles(QWidget):
    """Плитки с крупными числами (как в AiCar): число, подпись, пояснение. В ряд, если каждой
    хватает min_tile px, иначе по две или по одной - подписи не сжимаются в столбик."""

    GAP = 12

    def __init__(self, count, min_tile=170, parent=None):
        super().__init__(parent)
        self.min_tile = min_tile
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(self.GAP)
        self.tiles = []
        for _ in range(count):
            frame = QFrame()
            frame.setObjectName("tile")
            v = QVBoxLayout(frame)
            v.setContentsMargins(16, 12, 16, 12)
            v.setSpacing(2)
            value = label("", "tileValue")
            caption = label("", "tileCaption", wrap=True)
            note = label("", "tileNote", wrap=True)
            for w in (value, caption, note):
                v.addWidget(w)
            v.addStretch(1)
            self.tiles.append((frame, value, caption, note))
        self.cols = 0
        self._place(len(self.tiles))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def columns(self, width):
        n = len(self.tiles)
        c = max(1, min(n, (width + self.GAP) // (self.min_tile + self.GAP)))
        if c < n and c > 2 and n % c:
            c = 2 if n % 2 == 0 else c          # 4 плитки - 2+2, а не 3+1
        return c

    def _place(self, cols):
        if cols == self.cols:
            return
        self.cols = cols
        for frame, *_ in self.tiles:
            self.grid.removeWidget(frame)
        for i, (frame, *_) in enumerate(self.tiles):
            self.grid.addWidget(frame, i // cols, i % cols)
        for c in range(len(self.tiles)):
            self.grid.setColumnStretch(c, 1 if c < cols else 0)

    def set_tile(self, i, value, caption, note=""):
        _, v, c, n = self.tiles[i]
        v.setText(str(value))
        c.setText(caption)
        n.setText(note)
        n.setVisible(bool(note))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place(self.columns(self.width()))

    def sizeHint(self):
        return QSize(len(self.tiles) * (self.min_tile + self.GAP), super().sizeHint().height())


# --- законы ---


def _name(w):
    text = w.text() if hasattr(w, "text") else ""
    return f"{type(w).__name__}({w.objectName() or '-'}, «{str(text)[:24]}»)"


def page_problems(page):
    """Нарушения страницы (пусто - всё цело). Звать после раскладки в окне нужного размера."""
    scroll = page.scroll if isinstance(getattr(page, "scroll", None), QScrollArea) else page.findChild(QScrollArea)
    body = scroll.widget() if scroll is not None else page
    out = []
    if scroll is not None:
        vw = scroll.viewport().width()
        if body.width() > vw + 1:
            out.append(f"страница шире окна: {body.width()} > {vw} - правый край обрезан")
    out += layout_problems(body)
    for w in body.findChildren(QLabel):
        if w.isVisibleTo(body) and w.wordWrap() and w.maximumHeight() < QWIDGETSIZE_MAX:
            out.append(f"{_name(w)}: у подписи с переносом потолок высоты {w.maximumHeight()}")
    from aikit.charts import all_charts
    for c in all_charts(body):
        if not c.isVisibleTo(body):
            continue
        c.grab()
        if c.clipped:
            out.append(f"график «{c.title}»: не влезло {c.clipped}")
        if c.overlaps():
            out.append(f"график «{c.title}»: налезают {c.overlaps()[:3]}")
    return out


def difference(a, b, size=(160, 100), tol=24):
    """Доля заметно разных точек двух кадров (QImage/QPixmap), сжатых до size."""
    def small(img):
        if isinstance(img, QPixmap):
            img = img.toImage()
        return img.scaled(*size, Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_RGB32)
    x, y = small(a), small(b)
    diff = 0
    for j in range(size[1]):
        for i in range(size[0]):
            ca, cb = x.pixelColor(i, j), y.pixelColor(i, j)
            if max(abs(ca.red() - cb.red()), abs(ca.green() - cb.green()), abs(ca.blue() - cb.blue())) > tol:
                diff += 1
    return diff / (size[0] * size[1])
