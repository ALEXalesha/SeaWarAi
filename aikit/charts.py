"""Графики статистики на QPainter (без QtCharts и matplotlib): линия, столбики и сетка карточек.

Вид - по образцу AiCar/chart.py (а там - нейро-змейки): карточка с заголовком, сеткой,
делениями и подписями осей, линия с заливкой, последнее значение в углу. Вторая и следующие
линии тоньше, тогда в углу значения всех с подписями - они же легенда. Доли (percent=True)
идут по шкале 0-100 %, числа - по круглой шкале y_scale (шаг 1, 2, 2.5, 5 на степень десяти),
с линией нуля, если есть отрицательные значения. Цвета - из темы aikit, график меняется
вместе с темой (set_theme).

Пустые данные: пока у главной линии меньше двух точек, карточка не прячется и не рисует
пустую сетку с одной точкой (так было в WritingSpeed), а говорит словами, откуда возьмётся
график (empty_text).

Подписи не обрезаются молча: всё, что карточке пришлось сократить или что не влезло,
попадает в chart.clipped после отрисовки - законы-тесты игр проверяют, что там пусто.
Ширина текста считается с запасом SLACK: на настоящем экране буквы шире, чем в offscreen.
Не влезают заголовок и легенда в одну строку - легенда уходит на вторую строку.

ChartGrid - карточки в две колонки (в одну на узкой странице), широкие - на всю строку.
Высоту под ширину сообщает heightForWidth, поэтому сетка правильно живёт в QScrollArea.

Модуль собран из DurakAiGame/game/ui/charts.py и RockPaperAi/game/ui/charts.py (aikit 0.2.0,
правило автора 10.10: графики в статистике всех игр с ИИ). Строки RU/EN - в TEXTS.
"""
import math

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from aikit import theme as aitheme

SLACK = 1.1          # запас ширины текста: настоящий экран рисует буквы шире offscreen
PAD = 14
BOTTOM = 46          # подписи делений и название оси под графиком
GAP = 12             # между карточками в ChartGrid
LEGEND_GAP = 14      # между сериями в легенде

TEXTS = {
    "ru": {
        "charts": "Графики",
        "game_no": "партия",
        "share": "Доля ваших побед",
        "share_empty": "Сыграйте две партии против ИИ - здесь появится, как меняется доля ваших побед "
                       "(победа - 1, ничья - половина).",
        "last20": "последние 20", "all": "все",
        "levels": "Итоги по уровням ИИ",
        "levels_empty": "Здесь будут доли побед, ничьих и поражений на каждом уровне ИИ.",
        "win": "победы", "draw": "ничьи", "loss": "поражения",
        "length": "Длина партии",
        "length_empty": "Сыграйте две партии - здесь появится, сколько длилась каждая.",
        "moves": "ходов", "last": "последняя",
        "streak": "Серии побед и рекорд",
        "streak_empty": "Сыграйте две партии - здесь появятся ваши серии побед подряд и лучшая из них.",
        "streak_now": "серия", "record": "рекорд",
        "score": "Очки и рекорд",
        "score_empty": "Сыграйте две партии - здесь появятся очки каждой партии и ваш рекорд.",
        "points": "очки",
        "learning": "Обучение ИИ",
        "learning_empty": "Кривой обучения пока нет: она появится, когда ИИ пройдёт обучение.",
        "step": "шаг обучения",
        "passport": "Сила ИИ по паспорту",
        "passport_empty": "Паспорта силы ИИ пока нет: он появится после проверки обученного ИИ.",
    },
    "en": {
        "charts": "Charts",
        "game_no": "game",
        "share": "Your share of wins",
        "share_empty": "Play two games against the AI to see how your share of wins changes "
                       "(a win is 1, a draw is half).",
        "last20": "last 20", "all": "all",
        "levels": "Results by AI level",
        "levels_empty": "Shares of wins, draws and losses at each AI level will be here.",
        "win": "wins", "draw": "draws", "loss": "losses",
        "length": "Game length",
        "length_empty": "Play two games to see how long each one was.",
        "moves": "moves", "last": "last",
        "streak": "Win streaks and record",
        "streak_empty": "Play two games to see your winning streaks and the best of them.",
        "streak_now": "streak", "record": "record",
        "score": "Score and record",
        "score_empty": "Play two games to see the score of each game and your record.",
        "points": "points",
        "learning": "AI training",
        "learning_empty": "No training curve yet: it appears once the AI has been trained.",
        "step": "training step",
        "passport": "AI strength from the passport",
        "passport_empty": "No AI strength passport yet: it appears once the trained AI is checked.",
    },
}

OUTCOME_KEYS = {"win": "good", "draw": "warn", "loss": "bad"}


def texts(lang):
    """Строки графиков на языке lang (нет языка - русские)."""
    return dict(TEXTS.get(lang) or TEXTS["ru"])


# --- чистые функции (без отрисовки) ---------------------------------------------------------

def clean(points):
    """Только конечные пары чисел, по возрастанию x: мусор из файла не рисуется."""
    out = []
    for item in points if isinstance(points, (list, tuple)) else []:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        x, y = item
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (x, y)):
            out.append((float(x), float(y)))
    return sorted(out)


def y_scale(lo, hi, most=5, integer=False):
    """Круглая шкала по y: (низ, верх, деления, шаг) шагом 1, 2, 2.5, 5 на степень десяти.
    Неотрицательные данные, у которых разброс больше их высоты, начинаются с нуля, и шкала
    не уходит ниже нуля даже у ровной линии (серия побед из одних нулей - шкала 0..1, а не
    -0,5..0,5). integer - шаг не меньше 1 (серии, ходы)."""
    if lo >= 0 and lo <= 0.3 * hi:
        lo = 0.0
    if hi - lo < 1e-9 * max(1.0, abs(hi), abs(lo)):
        pad = max(0.5, abs(hi) * 0.05)
        lo, hi = (max(0.0, lo - pad) if lo >= 0 else lo - pad), hi + pad
    raw = (hi - lo) / (most - 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw * (1 - 1e-12))
    if integer:
        step = max(1.0, step if step >= 1 else 1.0)
        if step == 2.5:
            step = 2.0 if raw <= 2 else 5.0
    start = math.floor(lo / step + 1e-9) * step
    end = math.ceil(hi / step - 1e-9) * step
    if end - start < step * 0.5:
        end = start + step
    count = int(round((end - start) / step))
    return start, end, [start + i * step for i in range(count)] + [end], step


def digits(step):
    d = 0
    while d < 6 and abs(step * 10 ** d - round(step * 10 ** d)) > 1e-6:
        d += 1
    return d


def x_ticks(x0, x1, most=6):
    """Целые деления оси x шагом 1, 2, 5, 10, 20, 50...: не больше most штук."""
    span = max(x1 - x0, 1e-9)
    most = max(2, most)
    k = 0
    while True:
        step = (1, 2, 5)[k % 3] * 10 ** (k // 3)
        if span / step <= most - 1:
            break
        k += 1
    t = math.ceil(x0 / step) * step
    out = []
    while t <= x1 + 1e-9:
        out.append(t)
        t += step
    return out or [x0]


def group(v):
    """Целое с пробелами по тысячам: 12 500."""
    return f"{int(round(v)):,}".replace(",", " ")


def pct(v):
    return f"{v * 100:.0f}%"


def num(v, unit=""):
    if abs(v) >= 10000:
        text = group(v)
    elif abs(v - round(v)) < 1e-9 or abs(v) >= 100:
        text = f"{v:.0f}"
    elif abs(v) >= 10:
        text = f"{v:.1f}".rstrip("0").rstrip(".")      # 86.0 -> 86, 86.4 остаётся
    else:
        text = f"{v:.2f}".rstrip("0").rstrip(".")
    return text + unit


def tick_text(v, step, percent):
    if percent:
        return pct(v)
    if abs(v) >= 10000 and digits(step) == 0:
        return group(v)
    return f"{v:.{digits(step)}f}"


# --- карточка ------------------------------------------------------------------------------

class ChartCard(QWidget):
    """Общая часть графиков: рамка, заголовок с легендой, заглушка без данных, сетка по y."""
    HEIGHT = 236

    def __init__(self, title="", empty_text="", x_label="", y_label="", parent=None):
        super().__init__(parent)
        self.title = title
        self.empty_text = empty_text
        self.x_label = x_label
        self.y_label = y_label
        self.theme = "dark"
        self.clipped = []
        self.shown_empty = False        # последняя отрисовка - заглушка
        self.setMinimumSize(280, self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.HEIGHT)

    def sizeHint(self):
        return QSize(560, self.HEIGHT)

    def set_theme(self, name):
        self.theme = name
        self.update()

    def set_texts(self, title, empty_text, x_label=None, y_label=None):
        self.title = title
        self.empty_text = empty_text
        if x_label is not None:
            self.x_label = x_label
        if y_label is not None:
            self.y_label = y_label
        self.update()

    def has_data(self):
        return False

    def pal(self):
        return aitheme.palette(self.theme)

    @staticmethod
    def fonts():
        title = QFont("Segoe UI")
        title.setPixelSize(14)
        title.setBold(True)
        small = QFont("Segoe UI")
        small.setPixelSize(11)
        return title, small

    def legend(self):
        """Легенда кусками: [[(текст, ключ цвета), ...] на каждую серию]."""
        return []

    # -- подписи: ширина с запасом, не влезло - в clipped
    def fits(self, fm, text, width):
        return fm.horizontalAdvance(text) * SLACK <= width

    def note_clip(self, text):
        if text and text not in self.clipped:
            self.clipped.append(text)

    def frame(self, p):
        """Карточка, заголовок и легенда. Возвращает верх области графика.
        Легенда - куски (серия целиком); не влезает в строку заголовка - идёт строками ниже."""
        pal = self.pal()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(pal["border"]), 1))
        p.setBrush(QColor(pal["surface"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        title_font, _ = self.fonts()
        p.setFont(title_font)
        fm = p.fontMetrics()
        head_w = self.width() - 2 * PAD
        chunks = [c for c in (self.legend() if self.has_data() else []) if c]

        def width(chunk):
            return sum(fm.horizontalAdvance(t) for t, _ in chunk) * SLACK

        sep = LEGEND_GAP
        all_w = sum(width(c) for c in chunks) + sep * max(0, len(chunks) - 1)
        title_w = fm.horizontalAdvance(self.title) * SLACK
        one_line = not chunks or title_w + 16 + all_w <= head_w
        title = self.title
        if title_w > head_w:
            self.note_clip(self.title)
            title = fm.elidedText(title, Qt.TextElideMode.ElideRight, head_w)
        p.setPen(QColor(pal["text"]))
        p.drawText(QRectF(PAD, 8, head_w, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        if not chunks:
            return 42
        if one_line:
            rows = [chunks]
            if title_w + all_w > head_w:            # легенда легла бы на заголовок
                self.note_clip(self.title)
        else:
            rows, row, used = [], [], 0.0
            for c in chunks:
                w = width(c)
                if row and used + sep + w > head_w:
                    rows.append(row)
                    row, used = [], 0.0
                if w > head_w:
                    self.note_clip("".join(t for t, _ in c))
                row.append(c)
                used += (sep if len(row) > 1 else 0) + w
            rows.append(row)
        y = 8 if one_line else 30
        for row in rows:
            row_w = sum(width(c) for c in row) / SLACK + sep * (len(row) - 1)
            x = PAD + head_w - row_w if one_line else PAD
            for i, chunk in enumerate(row):
                if i:
                    x += sep
                for text, key in chunk:
                    w = fm.horizontalAdvance(text)
                    p.setPen(QColor(pal[key]))
                    p.drawText(QRectF(x, y, w + 1, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
                    x += w
            y += 20
        return 42 if one_line else 42 + 20 * len(rows) - 2

    def empty(self, p, top):
        pal = self.pal()
        f = QFont("Segoe UI")
        f.setPixelSize(13)
        p.setFont(f)
        p.setPen(QColor(pal["muted"]))
        box = QRect(24, top, self.width() - 48, self.height() - top - 16)
        need = p.fontMetrics().boundingRect(QRect(0, 0, int(box.width() / SLACK), 10000),
                                            Qt.TextFlag.TextWordWrap, self.empty_text)
        if need.height() > box.height():
            self.note_clip(self.empty_text)
        p.drawText(box, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.empty_text)
        self.shown_empty = True

    def left_margin(self, labels):
        _, small = self.fonts()
        fm = QFontMetrics(small)
        widest = max((fm.horizontalAdvance(t) for t in labels), default=20)
        return int(max(34, widest * SLACK + 12) + (18 if self.y_label else 0))

    def y_grid(self, p, plot, ticks, y0, y1, step, percent):
        pal = self.pal()
        _, small = self.fonts()
        p.setFont(small)
        for v in ticks:
            y = plot.bottom() - (v - y0) / (y1 - y0) * plot.height()
            zero = not percent and abs(v) < step * 1e-6 and y0 < 0
            p.setPen(QPen(QColor(pal["muted"] if zero else pal["grid"]), 1.4 if zero else 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(pal["muted"]))
            text = tick_text(v, step, percent)
            if not self.fits(p.fontMetrics(), text, plot.left() - 8 - (18 if self.y_label else 0)):
                self.note_clip(text)
            p.drawText(QRectF(2, y - 8, plot.left() - 8, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)
        if self.y_label:
            fm = p.fontMetrics()
            if not self.fits(fm, self.y_label, plot.height()):
                self.note_clip(self.y_label)
            p.save()
            p.translate(4, plot.center().y())
            p.rotate(-90)
            p.drawText(QRectF(-plot.height() / 2, 0, plot.height(), 14), Qt.AlignmentFlag.AlignHCenter, self.y_label)
            p.restore()

    def x_title(self, p, plot):
        if not self.x_label:
            return
        fm = p.fontMetrics()
        if not self.fits(fm, self.x_label, plot.width()):
            self.note_clip(self.x_label)
        p.setPen(QColor(self.pal()["muted"]))
        p.drawText(QRectF(plot.left(), plot.bottom() + 24, plot.width(), 16),
                   Qt.AlignmentFlag.AlignHCenter, self.x_label)

    def paintEvent(self, event):
        self.clipped = []
        self.shown_empty = False
        p = QPainter(self)
        top = self.frame(p)
        if not self.has_data():
            self.empty(p, top)
        else:
            self.draw(p, top)
        p.end()

    def draw(self, p, top):
        raise NotImplementedError


class LineChart(ChartCard):
    """Линии по номеру партии (шагу обучения): первая - главная, с заливкой; остальные тоньше.
    percent=True - доли 0..1 на шкале 0-100 %, иначе числа на круглой шкале (unit - в легенде)."""

    def __init__(self, title="", empty_text="", x_label="", percent=True, names=("", ""), unit="", y_label="",
                 parent=None):
        super().__init__(title, empty_text, x_label, y_label, parent)
        self.percent = percent
        self.unit = unit
        self.names = names
        self.color_key = "good" if percent else "accent"
        self.second_key = "muted"
        self.series = []            # [(подпись, ключ цвета, точки)]
        self.stepped = set()        # номера линий, что рисуются ступеньками (рекорд, серия)
        self.integer = False        # целые числа (серии, ходы): шаг шкалы не дробный

    def set_points(self, points, second=None):
        """Главная линия и, если есть, вторая (подписи - names)."""
        items = [(self.names[0] if self.names else "", self.color_key, points)]
        if second:
            items.append((self.names[1] if len(self.names) > 1 else "", self.second_key, second))
        self.set_series(items)

    def set_series(self, items):
        self.series = [(name, key, clean(pts)) for name, key, pts in items]
        self.update()

    @property
    def points(self):
        return self.series[0][2] if self.series else []

    @property
    def second(self):
        return self.series[1][2] if len(self.series) > 1 else []

    def has_data(self):
        return len(self.points) >= 2

    def fmt(self, v):
        return pct(v) if self.percent else num(v, self.unit)

    def legend(self):
        out = []
        for i, (name, key, pts) in enumerate(self.series):
            if not pts:
                continue
            chunk = [(name + " ", "muted")] if name else []
            chunk.append((self.fmt(pts[-1][1]), key if i == 0 or key != "muted" else "text"))
            out.append(chunk)
        return out

    def draw(self, p, top):
        pal = self.pal()
        lines = [s for s in self.series if len(s[2]) >= 2]
        xs = [x for _, _, pts in lines for x, _ in pts]
        x0, x1 = min(xs), max(xs)
        if x1 - x0 < 1e-12:
            x1 = x0 + 1
        if self.percent:
            y0, y1, step = 0.0, 1.0, 0.25
            ticks = [0, 0.25, 0.5, 0.75, 1.0]
        else:
            ys = [y for _, _, pts in lines for _, y in pts]
            y0, y1, ticks, step = y_scale(min(ys), max(ys), integer=self.integer)
        left = self.left_margin([tick_text(v, step, self.percent) for v in ticks])
        plot = QRectF(left, top, self.width() - left - 16, self.height() - top - BOTTOM)
        self.y_grid(p, plot, ticks, y0, y1, step, self.percent)

        def at(x, y):
            y = max(y0, min(y1, y))
            return QPointF(plot.left() + (x - x0) / (x1 - x0) * plot.width(),
                           plot.bottom() - (y - y0) / (y1 - y0) * plot.height())

        _, small = self.fonts()
        p.setFont(small)
        fm = p.fontMetrics()
        big = max(abs(x0), abs(x1)) >= 10000

        def xtext(t):
            return group(t) if big else f"{t:g}"

        most = int(max(2, min(10, plot.width() // 60)))
        while True:
            ticks_x = x_ticks(x0, x1, most)
            widest = max(fm.horizontalAdvance(xtext(t)) for t in ticks_x)
            gap = plot.width() / max(1, (x1 - x0)) * (ticks_x[1] - ticks_x[0]) if len(ticks_x) > 1 else plot.width()
            if widest * SLACK + 8 <= gap or most <= 2:
                break
            most -= 1
        p.setPen(QPen(QColor(pal["muted"]), 1))
        for t in ticks_x:
            x = at(t, y0).x()
            text = xtext(t)
            p.drawLine(QPointF(x, plot.bottom()), QPointF(x, plot.bottom() + 4))
            p.drawText(QRectF(x - 40, plot.bottom() + 6, 80, 14), Qt.AlignmentFlag.AlignHCenter, text)
        self.x_title(p, plot)

        def path(points, steps=False):
            line = QPainterPath(at(*points[0]))
            prev = points[0][1]
            for x, y in points[1:]:
                if steps:
                    line.lineTo(at(x, prev))
                line.lineTo(at(x, y))
                prev = y
            return line

        for i in range(len(self.series) - 1, 0, -1):
            _, key, pts = self.series[i]
            if len(pts) < 2:
                continue
            p.setPen(QPen(QColor(pal[key]), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path(pts, i in self.stepped))
        colour = QColor(pal[self.series[0][1]])
        line = path(self.points, 0 in self.stepped)
        base = 0.0 if y0 <= 0 <= y1 else y0          # заливка - до нуля или до низа шкалы
        fill = QPainterPath(line)
        fill.lineTo(at(self.points[-1][0], base))
        fill.lineTo(at(self.points[0][0], base))
        fill.closeSubpath()
        grad = QLinearGradient(plot.topLeft(), plot.bottomLeft())
        c_top = QColor(colour)
        c_top.setAlpha(80)
        c_bottom = QColor(colour)
        c_bottom.setAlpha(0)
        grad.setColorAt(0, c_top)
        grad.setColorAt(1, c_bottom)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPath(fill)
        p.setPen(QPen(colour, 2.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(line)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawEllipse(at(*self.points[-1]), 3.5, 3.5)


class BarChart(ChartCard):
    """Группы столбиков: groups - подписи групп (уровни, соперники), series - [(подпись, ключ
    цвета темы, [значения])]. percent=True - доли 0..1, иначе числа на круглой шкале от нуля."""

    def __init__(self, title="", empty_text="", percent=True, unit="", y_label="", parent=None):
        super().__init__(title, empty_text, "", y_label, parent)
        self.percent = percent
        self.unit = unit
        self.groups = []
        self.series = []

    def set_data(self, groups, series):
        self.groups = [str(g) for g in groups]
        out = []
        for name, key, values in series:
            vals = []
            for v in values:
                v = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else 0.0
                vals.append(max(0.0, min(1.0, v)) if self.percent else max(0.0, v))
            out.append((name, key, vals))
        self.series = out
        self.update()

    def has_data(self):
        return bool(self.groups) and bool(self.series)

    def fmt(self, v):
        return pct(v) if self.percent else num(v, self.unit)

    def legend(self):
        return [[("■ ", key), (name, "muted")] for name, key, _ in self.series if name]

    def draw(self, p, top):
        pal = self.pal()
        if self.percent:
            y0, y1, step, ticks = 0.0, 1.0, 0.25, [0, 0.25, 0.5, 0.75, 1.0]
        else:
            hi = max([v for _, _, vals in self.series for v in vals] or [1.0]) or 1.0
            y0, y1, ticks, step = y_scale(0.0, hi)
        left = self.left_margin([tick_text(v, step, self.percent) for v in ticks])
        plot = QRectF(left, top + (6 if not self.percent else 0), self.width() - left - 16,
                      self.height() - top - BOTTOM - (6 if not self.percent else 0))
        self.y_grid(p, plot, ticks, y0, y1, step, self.percent)
        n, m = len(self.groups), len(self.series)
        slot = plot.width() / n
        bar = min(34.0, slot * 0.8 / m)
        _, small = self.fonts()
        p.setFont(small)
        fm = p.fontMetrics()
        for gi, label in enumerate(self.groups):
            cx = plot.left() + slot * (gi + 0.5)
            x = cx - bar * m / 2
            for _, key, values in self.series:
                v = values[gi] if gi < len(values) else 0.0
                h = (v - y0) / (y1 - y0) * plot.height()
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(pal[key]))
                p.drawRoundedRect(QRectF(x + 1, plot.bottom() - h, max(0.0, bar - 2), h), 3, 3)
                text = self.fmt(v)
                if fm.horizontalAdvance(text) <= bar + 10:
                    p.setPen(QColor(pal["text"]))
                    p.drawText(QRectF(x - 8, plot.bottom() - h - 15, bar + 16, 14), Qt.AlignmentFlag.AlignHCenter, text)
                x += bar
            box = QRect(int(cx - slot / 2 + 2), int(plot.bottom() + 6), int(slot - 4), 30)
            need = fm.boundingRect(QRect(0, 0, int(box.width() / SLACK), 1000), Qt.TextFlag.TextWordWrap, label)
            words_fit = all(self.fits(fm, w, box.width()) for w in label.split())
            if need.height() > box.height() or not words_fit:
                self.note_clip(label)
            p.setPen(QColor(pal["muted"]))
            p.drawText(box, Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap, label)


# --- сетка карточек ------------------------------------------------------------------------

class ChartGrid(QWidget):
    """Карточки графиков в две колонки, на узкой странице - в одну; wide - на всю строку.
    Раскладка руками в resizeEvent, высота - heightForWidth (иначе в QScrollArea сетка из
    двух колонок держала бы страницу широкой и не перестраивалась)."""

    def __init__(self, min_col=330, parent=None):
        super().__init__(parent)
        self.min_col = min_col
        self.items = []             # [(карточка, широкая)]
        sp = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def add(self, chart, wide=False):
        chart.setParent(self)
        chart.setMinimumWidth(0)
        self.items.append((chart, wide))
        chart.show()
        self.updateGeometry()
        self._place(self.width())
        return chart

    def charts(self):
        return [c for c, _ in self.items]

    def set_theme(self, name):
        for c in self.charts():
            c.set_theme(name)

    def columns(self, width):
        return 2 if width >= 2 * self.min_col + GAP else 1

    def _rows(self, width):
        """[(y, [(карточка, x, ширина)])] для ширины width."""
        cols = self.columns(width)
        col_w = (width - GAP * (cols - 1)) / cols
        rows, row, y = [], [], 0
        for chart, wide in self.items:
            if chart.isHidden():
                continue
            if wide or cols == 1:
                if row:
                    rows.append(row)
                    row = []
                rows.append([(chart, 0, width)])
                continue
            row.append((chart, len(row) * (col_w + GAP), col_w))
            if len(row) == cols:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        out = []
        for r in rows:
            out.append((y, r))
            y += max(c.height() for c, _, _ in r) + GAP
        return out

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        rows = self._rows(width)
        if not rows:
            return 0
        y, last = rows[-1]
        return y + max(c.height() for c, _, _ in last)

    def sizeHint(self):
        return QSize(2 * 330 + GAP, self.heightForWidth(2 * 330 + GAP))

    def minimumSizeHint(self):
        return QSize(self.min_col, self.heightForWidth(self.min_col))

    def _place(self, width):
        for y, row in self._rows(width):
            for chart, x, w in row:
                chart.setGeometry(int(round(x)), int(y), int(round(w)), chart.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place(self.width())
        if self.height() != self.heightForWidth(self.width()):
            self.updateGeometry()


def all_charts(widget):
    """Все карточки графиков внутри виджета (для законов: «графики есть», «подписи целы»)."""
    return widget.findChildren(ChartCard)


def outcome_bars(chart, games, levels, level_names, lang):
    """Столбики «итоги по уровням» из журнала aikit.gamelog: levels - ключи в нужном
    порядке, level_names - {ключ: подпись}."""
    from aikit import gamelog
    t = texts(lang)
    groups, series = gamelog.by_level(games, levels)
    chart.set_data([level_names.get(g, g) for g in groups],
                   [(t[o], OUTCOME_KEYS[o], vals) for o, vals in series])


class GameCharts(ChartGrid):
    """Стандартный набор графиков статистики игры против ИИ по журналу aikit.gamelog:
    доля побед (последние 20 и все), итоги по уровням, длина партии (поле length_key),
    рекорды (очки score_key с рекордом или, если очков нет, серии побед), а по желанию -
    кривая обучения и паспорт силы ИИ столбиками (широкие, на всю строку).

    Игра зовёт refresh(games, lang, level_names, ...) при показе страницы статистики и смене
    языка, set_theme - при смене темы. Подписи можно поменять словарём labels (ключи TEXTS)."""

    def __init__(self, levels, length_key="moves", score_key=None, score_better="max",
                 learning=False, passport=False, length_unit="", score_unit="", parent=None):
        super().__init__(parent=parent)
        self.levels = tuple(levels)
        self.length_key = length_key
        self.score_key = score_key
        self.score_better = score_better
        self.share = self.add(LineChart(percent=True))
        self.by_level = self.add(BarChart(percent=True))
        self.length = self.add(LineChart(percent=False, unit=length_unit)) if length_key else None
        self.records = self.add(LineChart(percent=False, unit=score_unit if score_key else ""))
        self.learning = self.add(LineChart(percent=False), wide=True) if learning else None
        self.passport = self.add(BarChart(percent=True), wide=True) if passport else None

    def refresh(self, games, lang, level_names=None, labels=None, learning=None, passport=None):
        """learning - [(подпись, ключ цвета, точки)] или None; passport - (группы, серии) для
        BarChart.set_data или None."""
        from aikit import gamelog
        t = texts(lang)
        t.update(labels or {})
        names = level_names or {}
        c = self.share
        c.set_texts(t["share"], t["share_empty"], t["game_no"])
        c.names = (t["last20"], t["all"])
        c.set_points(gamelog.rolling_share(games, 20), gamelog.rolling_share(games, None))
        self.by_level.set_texts(t["levels"], t["levels_empty"])
        outcome_bars(self.by_level, games, self.levels, names, lang)
        if self.length is not None:
            self.length.set_texts(t["length"], t["length_empty"], t["game_no"], t.get("length_y", t["moves"]))
            self.length.names = (t["last"],)
            self.length.integer = all(float(v).is_integer() for _, v in gamelog.series(games, self.length_key))
            self.length.set_points(gamelog.series(games, self.length_key))
        r = self.records
        if self.score_key:
            r.set_texts(t["score"], t["score_empty"], t["game_no"], t.get("score_y", t["points"]))
            r.color_key, r.second_key = "accent", "warn"
            r.names = (t["points"], t["record"])
            r.stepped = {1}
            r.set_points(gamelog.series(games, self.score_key),
                         gamelog.best_curve(games, self.score_key, self.score_better))
        else:
            r.set_texts(t["streak"], t["streak_empty"], t["game_no"], "")
            r.color_key, r.second_key = "accent", "warn"
            r.names = (t["streak_now"], t["record"])
            r.stepped = {0, 1}
            r.integer = True
            now, top = gamelog.streaks(games)
            r.set_points(now, top)
        if self.learning is not None:
            self.learning.set_texts(t["learning"], t["learning_empty"], t["step"], t.get("learning_y", ""))
            self.learning.set_series(learning or [])
        if self.passport is not None:
            self.passport.set_texts(t["passport"], t["passport_empty"])
            groups, series = passport if passport else ([], [])
            self.passport.set_data(groups, series)
