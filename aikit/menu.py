"""Стартовое меню игры: общая ЛОГИКА, вид у каждой игры свой.

Правило автора 17.10.2026: одинаковое меню во всех играх скучно - у каждой игры своё стартовое
меню и свой стиль (фон, цвета, шрифты, раскладка кнопок), по уровню AiBoy и AiCar. Поэтому здесь
нет ни цветов, ни раскладки - только то, что повторялось бы в каждой игре:

- Backdrop - живой фон страницы. Игра рисует свою сцену в paint_scene(p, w, h, t); анимация идёт,
  только пока страница видна и не на паузе (pause/resume - для вкладки оболочки), не чаще FPS
  кадров в секунду. set_time(t) замораживает кадр - для кадров README и законов.
- Title - заголовок своим шрифтом. Таблица стилей окна задаёт шрифт всем виджетам через «*»,
  и setFont у QLabel тогда не действует; Title рисует текст сам, с разрядкой, и уменьшает шрифт,
  если текст не влезает в ширину (длинный английский заголовок в узком окне).
- layout_problems(root) - закон «меню не обрезано и не налезает»: каждая видимая подпись, кнопка,
  список и заголовок целиком внутри страницы, текст влезает, соседи не перекрываются.
- fill_share(widget, root) - доля ширины root, которую занимает widget: закон «настройки
  растягиваются на всё окно, как статистика» (было: карточка в 760 px у левого края).
"""
from PySide6.QtCore import QElapsedTimer, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter
from PySide6.QtWidgets import (QAbstractButton, QCheckBox, QComboBox, QLabel, QRadioButton, QScrollArea,
                               QSizePolicy, QWidget)


class Backdrop(QWidget):
    """Страница с живым фоном. Наследник задаёт paint_scene и кладёт поверх свою раскладку."""

    FPS = 30
    MAX_STEP = 0.1           # после паузы или долгого кадра время не прыгает вперёд

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.theme_name = "dark"
        self.t = 0.0
        self.frozen = False
        self.paused = False
        self.frames = 0                     # сколько кадров нарисовано (законы анимации)
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, round(1000 / self.FPS)))
        self._timer.timeout.connect(self._advance)

    # --- время ---

    def running(self):
        return self._timer.isActive()

    def _sync_timer(self):
        want = self.isVisible() and not self.paused and not self.frozen
        if want and not self._timer.isActive():
            self._clock.restart()
            self._timer.start()
        elif not want and self._timer.isActive():
            self._timer.stop()

    def _advance(self):
        dt = min(self.MAX_STEP, self._clock.restart() / 1000.0)
        self.t += dt
        self.tick(dt)
        self.update()

    def tick(self, dt):
        """Шаг сцены (по желанию игры): частицы, падающие фигуры. Рисовать - в paint_scene."""

    def set_time(self, t):
        """Заморозить кадр на времени t (кадры README, законы). set_time(None) - снова живой."""
        if t is None:
            self.frozen = False
        else:
            self.frozen = True
            self.t = float(t)
            self.update()
        self._sync_timer()

    def pause(self):
        self.paused = True
        self._sync_timer()

    def resume(self):
        self.paused = False
        self._sync_timer()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_timer()

    # --- вид ---

    def set_theme(self, name):
        self.theme_name = name
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint_scene(p, self.width(), self.height(), self.t)
        p.end()
        self.frames += 1

    def paint_scene(self, p, w, h, t):
        p.fillRect(0, 0, w, h, QColor("#1f242e"))


class Title(QWidget):
    """Заголовок своим шрифтом и разрядкой; не влез - шрифт меньше (до min_px)."""

    def __init__(self, family, px, weight=QFont.Weight.Bold, spacing=0.0, min_px=None,
                 align=Qt.AlignmentFlag.AlignCenter, parent=None):
        super().__init__(parent)
        self.family = family
        self.px = px
        self.min_px = min_px or max(10, round(px * 0.55))
        self.weight = weight
        self.spacing = spacing             # разрядка в долях кегля
        self.align = align
        self.color = QColor("#e6e8ec")
        self._text = ""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def make_font(self, px):
        f = QFont(self.family)
        f.setPixelSize(max(1, round(px)))
        f.setWeight(self.weight)
        if self.spacing:
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, px * self.spacing)
        return f

    def text_width(self, px):
        return QFontMetricsF(self.make_font(px)).horizontalAdvance(self._text) + 4

    def fitted_px(self, width=None):
        width = self.width() if width is None else width
        px = self.px
        while px > self.min_px and self.text_width(px) > width:
            px -= 1
        return px

    def clipped(self):
        """Текст не влез даже самым мелким шрифтом (закон layout_problems)."""
        return bool(self._text) and self.text_width(self.fitted_px()) > self.width() + 0.5

    def setText(self, text):
        self._text = text
        self.updateGeometry()
        self.update()

    def text(self):
        return self._text

    def set_color(self, color):
        self.color = QColor(color)
        self.update()

    def sizeHint(self):
        fm = QFontMetricsF(self.make_font(self.px))
        return QSize(round(self.text_width(self.px)), round(fm.height() * 1.15))

    def minimumSizeHint(self):
        fm = QFontMetricsF(self.make_font(self.px))
        return QSize(min(round(self.text_width(self.min_px)), 120), round(fm.height() * 1.15))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font = self.make_font(self.fitted_px())
        self.paint_text(p, self.rect(), self._text, font)
        p.end()

    def paint_text(self, p, rect, text, font):
        """Игра может нарисовать по-своему: обводка, тень, буквы разного цвета."""
        p.setFont(font)
        p.setPen(self.color)
        p.drawText(rect, int(self.align | Qt.AlignmentFlag.AlignVCenter), text)


# --- законы раскладки ---


def _box(w, root):
    return QRect(w.mapTo(root, QPoint(0, 0)), w.size())


def _leaves(root):
    kinds = (QLabel, QAbstractButton, QComboBox, Title)
    out = []
    for w in root.findChildren(QWidget):
        if not isinstance(w, kinds) or not w.isVisibleTo(root):
            continue
        if any(isinstance(a, QScrollArea) for a in _ancestors(w, root)):
            continue                       # в прокрутке - своя видимая область
        out.append(w)
    return out


def _ancestors(w, root):
    a = w.parentWidget()
    while a is not None and a is not root:
        yield a
        a = a.parentWidget()


def _name(w):
    text = w.text() if hasattr(w, "text") else ""
    return f"{type(w).__name__}({w.objectName() or '-'}, «{str(text)[:24]}»)"


def descender_deficit(fm, text):
    """На сколько px хвосты букв (р, у, д) уходят ниже, чем обещает шрифт. У Cambria в Qt нижний
    вынос шрифта 0 - высота подписи только под верх букв, и хвосты срезаются («одному» читалось
    как «одномv», Морской бой, проверка 17.10)."""
    if not text:
        return 0.0
    return max(0.0, fm.tightBoundingRect(text).bottom() - fm.descent())


def text_clipped(w):
    """Текст виджета не влезает в его размер."""
    if isinstance(w, Title):
        return w.clipped()
    if isinstance(w, QLabel):
        text = w.text()
        if not text or w.textFormat() == Qt.TextFormat.RichText or "<" in text:
            return False
        r = w.contentsRect()
        fm = QFontMetricsF(w.font())
        lines = text.split("\n")              # подпись в несколько строк: мерить самую длинную строку
        deficit = max(descender_deficit(fm, line) for line in lines)
        if w.wordWrap():
            return w.heightForWidth(w.width()) + deficit > w.height() + 1
        widest = max(fm.horizontalAdvance(line) for line in lines)
        tall = fm.lineSpacing() * (len(lines) - 1) + fm.height() + deficit
        return widest > r.width() + 0.5 or tall > r.height() + 1
    if isinstance(w, QAbstractButton):
        if not w.text():
            return False
        if w.isCheckable() and not isinstance(w, (QCheckBox, QRadioButton)):
            # выбранная пишется жирным (флажки - нет) (:checked в таблице стилей), а sizeHint - по обычному
            from aikit.widgets import bold_width
            if bold_width(w) > w.width() + 1:
                return True
        return w.sizeHint().width() > w.width() or w.sizeHint().height() > w.height() + 1
    return False


def layout_problems(root, overlap=True):
    """Список нарушений раскладки страницы root (пусто - всё цело). Звать после раскладки
    (processEvents) в окне нужного размера."""
    out = []
    frame = root.rect()
    leaves = _leaves(root)
    boxes = {}
    for w in leaves:
        r = _box(w, root)
        boxes[w] = r
        if not frame.contains(r):
            out.append(f"{_name(w)} за краем: {r.getRect()} не в {frame.getRect()}")
        if text_clipped(w):
            out.append(f"{_name(w)}: текст не влез в {w.width()}x{w.height()}")
    if overlap:
        for i, a in enumerate(leaves):
            for b in leaves[i + 1:]:
                if a.isAncestorOf(b) or b.isAncestorOf(a):
                    continue
                inter = boxes[a].intersected(boxes[b])
                if inter.width() > 1 and inter.height() > 1:
                    out.append(f"{_name(a)} налезает на {_name(b)}")
    return out


def fill_share(widget, root):
    """Какую долю ширины root занимает widget (настройки - почти всю, как статистика)."""
    return widget.width() / max(1, root.width())


SIZES = ((900, 640), (1180, 780), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160))
"""Размеры окна для законов: от минимального до 4K (игра поднимает минимум своим)."""
