"""Поле морского боя своим кодом: клетки, подписи А-К и 1-10, корабли, попадания,
промахи, тепловая карта «Мыслей ИИ», анимации выстрелов и расстановка мышью.

BoardWidget - поле в бою (своё или чужое). SetupBoard - расстановка: поле и «причал» с
кораблями, перетаскивание левой кнопкой, поворот правой.
"""
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget


from game.core.battle import HIT, MISS, SUNK, UNKNOWN
from game.core.rules import FLEET, LETTERS, SIZE, Rules, can_place, ship_cells

N = SIZE * SIZE


def mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


def colors(theme_name):
    """Цвета поля - из палитры меню «штурманская рубка» (game.ui.menu.PALETTES): ночное море
    или морская карта на бумаге, сонарный цвет для «можно», сигнальный - для тепла."""
    from game.ui.menu import palette
    p = palette(theme_name)
    return {
        "bg": QColor(p["bg"]), "water": QColor(p["water"]), "line": QColor(p["line"]),
        "coord": QColor(p["coord"]), "ship": QColor(p["ship"]), "ship_edge": QColor(p["ship_edge"]),
        "hit": QColor(p["hit"]), "miss": QColor(p["miss"]), "auto": QColor(p["auto"]),
        "sunk": QColor(p["sunk"]), "heat": QColor(p["heat"]), "hover": QColor(p["sonar"]),
        "ok": QColor(p["ok"]), "bad": QColor(p["bad"]), "text": QColor(p["ink"]),
        "last": QColor(p["last"]),
    }


class BoardWidget(QWidget):
    """Поле 10x10. view - что видно (UNKNOWN/MISS/HIT/SUNK), ships - какие корабли рисовать,
    heat - тепловая карта 0..1 или None. clickable - по клику сигнал cellClicked(клетка)."""

    cellClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.theme_name = "dark"
        self.lang = "ru"
        self.c = colors("dark")
        self.view = [UNKNOWN] * N
        self.auto = set()
        self.ships = []
        self.heat = None
        self.clickable = False
        self.hover = -1
        self.last = -1
        self.title = ""
        self.anim_ms = 450
        self.effects = []            # (клетка, вид, начало)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def sizeHint(self):
        return QSize(420, 440)

    def minimumSizeHint(self):
        return QSize(300, 320)

    def set_theme(self, name, lang):
        self.theme_name, self.lang = name, lang
        self.c = colors(name)
        self.update()

    def set_state(self, view, ships, auto=(), heat=None, last=-1):
        self.view = list(view)
        self.ships = [tuple(s) for s in ships]
        self.auto = set(auto)
        self.heat = heat
        self.last = last
        self.update()

    # --- геометрия ---

    @staticmethod
    def bands(cell):
        """Место под подписи: сверху под буквы, слева под цифры. Растёт с клеткой - шрифт подписей
        тоже растёт (36 % клетки); постоянные 24 и 30 px на 2560x1440 срезали низ букв, а на
        3840x2160 - половину букв и «1» у «10» (проверка 17.10)."""
        return max(24.0, cell * 0.56), max(30.0, cell * 0.78)

    def geometry_(self):
        """(x0, y0, клетка): поле квадратное, слева и сверху место под подписи."""
        top = 28 if self.title else 0
        cell = max(8.0, min((self.width() - 30) / SIZE, (self.height() - 26 - top) / SIZE))
        for _ in range(3):                 # полосы подписей зависят от клетки - уточнить
            bt, bl = self.bands(cell)
            cell = max(8.0, min((self.width() - bl) / SIZE, (self.height() - bt - 2 - top) / SIZE))
        bt, bl = self.bands(cell)
        x0 = (self.width() - cell * SIZE + bl) / 2
        y0 = top + bt + max(0.0, (self.height() - top - bt - 2 - cell * SIZE) / 2)
        return x0, y0, cell

    def cell_rect(self, x):
        x0, y0, cell = self.geometry_()
        r, c = divmod(x, SIZE)
        return QRectF(x0 + c * cell, y0 + r * cell, cell, cell)

    def cell_at(self, pos):
        x0, y0, cell = self.geometry_()
        c = int((pos.x() - x0) // cell)
        r = int((pos.y() - y0) // cell)
        if 0 <= r < SIZE and 0 <= c < SIZE:
            return r * SIZE + c
        return -1

    # --- мышь ---

    def mouseMoveEvent(self, e):
        x = self.cell_at(e.position()) if self.clickable else -1
        if x != self.hover:
            self.hover = x
            self.setCursor(Qt.CursorShape.PointingHandCursor if x >= 0 and self.view[x] == UNKNOWN
                           else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, e):
        self.hover = -1
        self.update()

    def mousePressEvent(self, e):
        if not self.clickable or e.button() != Qt.MouseButton.LeftButton:
            return
        x = self.cell_at(e.position())
        if x >= 0 and self.view[x] == UNKNOWN:
            self.cellClicked.emit(x)

    # --- анимации ---

    def add_effect(self, cell, kind):
        if self.anim_ms <= 0:
            return
        self.effects.append((cell, kind, time.monotonic()))
        if not self.timer.isActive():
            self.timer.start()

    def animating(self):
        return bool(self.effects)

    def _tick(self):
        now = time.monotonic()
        self.effects = [e for e in self.effects if now - e[2] < self.anim_ms / 1000]
        if not self.effects:
            self.timer.stop()
        self.update()

    def stop(self):
        self.timer.stop()
        self.effects = []

    # --- рисование ---

    def _background(self, x0, y0, cell):
        """Неподвижная часть - подписи и вода - в кэше: перерисовка поля после выстрела в
        несколько раз быстрее (подписи в offscreen-Qt дорогие)."""
        dpr = self.devicePixelRatioF()
        key = (self.width(), self.height(), dpr, self.theme_name, self.lang, self.title)
        if getattr(self, "_bg_key", None) == key:
            return self._bg
        pix = QPixmap(max(1, round(self.width() * dpr)), max(1, round(self.height() * dpr)))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.c
        if self.title:
            f = QFont(self.font())
            f.setPointSizeF(12)
            f.setBold(True)
            p.setFont(f)
            p.setPen(c["text"])
            bt, _ = self.bands(cell)
            p.drawText(QRectF(0, y0 - bt - 28, self.width(), 24), Qt.AlignmentFlag.AlignCenter, self.title)
        f = QFont(self.font())
        f.setPixelSize(max(10, int(cell * 0.36)))
        p.setFont(f)
        p.setPen(c["coord"])
        letters = LETTERS.get(self.lang, LETTERS["ru"])
        bt, bl = self.bands(cell)
        self.label_boxes = []              # (текст, место) - закон «подписи целы и не на сетке»
        for i in range(SIZE):
            top_box = QRectF(x0 + i * cell, y0 - bt + 2, cell, bt - 4)
            left_box = QRectF(x0 - bl, y0 + i * cell, bl - 4, cell)
            p.drawText(top_box, Qt.AlignmentFlag.AlignCenter, letters[i])
            p.drawText(left_box, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(i + 1))
            self.label_boxes += [(letters[i], top_box), (str(i + 1), left_box)]
        p.fillRect(QRectF(x0, y0, cell * SIZE, cell * SIZE), c["water"])
        p.end()
        self._bg_key, self._bg = key, pix
        return pix

    def paintEvent(self, event):
        p = QPainter(self)
        c = self.c
        x0, y0, cell = self.geometry_()
        p.drawPixmap(0, 0, self._background(x0, y0, cell))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.heat is not None:
            top = max(float(max(self.heat)), 1e-9)
            for x in range(N):
                v = float(self.heat[x]) / top
                if v > 0.02 and self.view[x] == UNKNOWN:
                    h = QColor(c["heat"])
                    h.setAlphaF(min(0.75, 0.05 + 0.65 * v * v))
                    p.fillRect(self.cell_rect(x), h)
        p.setPen(QPen(c["line"], 1))
        for i in range(SIZE + 1):
            p.drawLine(QPointF(x0 + i * cell, y0), QPointF(x0 + i * cell, y0 + SIZE * cell))
            p.drawLine(QPointF(x0, y0 + i * cell), QPointF(x0 + SIZE * cell, y0 + i * cell))
        for s in self.ships:
            sunk = all(self.view[x] == SUNK for x in s)
            self.draw_ship(p, s, c["sunk"] if sunk else c["ship"], c["ship_edge"])
        for x in range(N):
            v = self.view[x]
            r = self.cell_rect(x)
            if v == MISS:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c["auto"] if x in self.auto else c["miss"])
                rad = cell * (0.09 if x in self.auto else 0.13)
                p.drawEllipse(r.center(), rad, rad)
            elif v in (HIT, SUNK):
                pen = QPen(c["hit"], max(2.0, cell * 0.09))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                m = cell * 0.24
                p.drawLine(r.topLeft() + QPointF(m, m), r.bottomRight() - QPointF(m, m))
                p.drawLine(r.topRight() + QPointF(-m, m), r.bottomLeft() + QPointF(m, -m))
        if 0 <= self.last < N:
            p.setPen(QPen(c["last"], 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(self.cell_rect(self.last).adjusted(2, 2, -2, -2), 4, 4)
        if self.clickable and 0 <= self.hover < N and self.view[self.hover] == UNKNOWN:
            p.setPen(QPen(c["hover"], 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(self.cell_rect(self.hover).adjusted(1, 1, -1, -1))
        now = time.monotonic()
        for x, kind, t0 in self.effects:
            t = min(1.0, (now - t0) / max(self.anim_ms / 1000, 1e-3))
            r = self.cell_rect(x)
            col = QColor(c["miss"] if kind == "miss" else c["hit"])
            col.setAlphaF(1 - t)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(col, max(2.0, cell * 0.08)))
            grow = (0.2 + 0.9 * t) if kind == "miss" else (0.3 + 1.4 * t if kind == "sunk" else 0.3 + 0.9 * t)
            p.drawEllipse(r.center(), cell * grow / 2, cell * grow / 2)
            if kind != "miss":
                fill = QColor(c["hit"])
                fill.setAlphaF(0.5 * (1 - t))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fill)
                p.drawEllipse(r.center(), cell * 0.35 * (1 - t / 2), cell * 0.35 * (1 - t / 2))
        p.end()

    def draw_ship(self, p, cells, fill, edge, alpha=1.0):
        rects = [self.cell_rect(x) for x in cells]
        r = rects[0].united(rects[-1]).adjusted(3, 3, -3, -3)
        f = QColor(fill)
        f.setAlphaF(alpha)
        e = QColor(edge)
        e.setAlphaF(0.55 * alpha)
        p.setPen(QPen(e, 1.5))
        p.setBrush(f)
        rad = min(r.width(), r.height()) * 0.35
        p.drawRoundedRect(r, rad, rad)


class SetupBoard(BoardWidget):
    """Расстановка: поле слева, причал с непоставленными кораблями справа (или снизу).

    ships[i] - клетки корабля i на поле или None (на причале). lengths[i] - его длина.
    Сигнал changed - после любого изменения."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = Rules()
        self.lengths = list(FLEET)
        self.placed = [None] * len(FLEET)
        self.horizontal = [True] * len(FLEET)
        self.drag = None             # (корабль, горизонтально, смещение захвата в клетках, откуда)
        self.drag_pos = None
        self.flash = None            # (корабль, до какого времени) - поворот не удался

    def sizeHint(self):
        return QSize(720, 460)

    def set_rules(self, rules):
        self.rules = rules
        self.update()

    def set_fleet(self, ships):
        """Поставить готовую расстановку (Случайно)."""
        left = list(range(len(self.lengths)))
        self.placed = [None] * len(self.lengths)
        for s in sorted(ships, key=len, reverse=True):
            i = next(k for k in left if self.lengths[k] == len(s))
            left.remove(i)
            self.placed[i] = tuple(sorted(s))
            self.horizontal[i] = len(s) == 1 or s[1] - s[0] == 1
        self.drag = None
        self.update()
        self.changed.emit()

    def clear(self):
        self.placed = [None] * len(self.lengths)
        self.horizontal = [True] * len(self.lengths)
        self.drag = None
        self.update()
        self.changed.emit()

    def fleet(self):
        return [s for s in self.placed if s is not None]

    def complete(self):
        return all(s is not None for s in self.placed)

    def others(self, i):
        return [s for k, s in enumerate(self.placed) if s is not None and k != i]

    # --- геометрия: поле слева, причал справа ---

    def geometry_(self):
        cell = max(8.0, min((self.width() - 60) / (SIZE + 6), (self.height() - 30) / SIZE))
        for _ in range(3):
            bt, bl = self.bands(cell)
            cell = max(8.0, min((self.width() - bl - 30) / (SIZE + 6), (self.height() - bt - 6) / SIZE))
        bt, bl = self.bands(cell)
        return bl + 4, bt, cell

    def dock_slots(self):
        """Прямоугольники непоставленных кораблей на причале справа от поля: по убыванию
        длины, плотно, с переносом на новую строку."""
        x0, y0, cell = self.geometry_()
        dx = x0 + SIZE * cell + cell * 0.8
        width = 5.4 * cell
        out = {}
        row, col = 0, 0.0
        last_len = None
        for i in sorted((k for k, s in enumerate(self.placed) if s is None), key=lambda k: -self.lengths[k]):
            L = self.lengths[i]
            w = L * cell * 0.8
            if (last_len is not None and L != last_len and col > 0) or col + w > width:
                row += 1
                col = 0.0
            out[i] = QRectF(dx + col, y0 + row * cell * 1.05, w, cell * 0.8)
            col += w + cell * 0.3
            last_len = L
        return out

    def ship_at(self, pos):
        x = self.cell_at(pos)
        if x >= 0:
            for i, s in enumerate(self.placed):
                if s is not None and x in s:
                    return i, "board", x
        for i, r in self.dock_slots().items():
            if self.placed[i] is None and r.contains(pos):
                return i, "dock", -1
        return None

    def target_cells(self, pos):
        """Клетки, куда лёг бы перетаскиваемый корабль, если отпустить сейчас."""
        if self.drag is None:
            return None
        i, horizontal, grab, _ = self.drag
        x = self.cell_at(pos)
        if x < 0:
            return None
        r, c = divmod(x, SIZE)
        if horizontal:
            c -= grab
        else:
            r -= grab
        return ship_cells(r, c, self.lengths[i], horizontal)

    # --- мышь ---

    def mousePressEvent(self, e):
        pos = e.position()
        if e.button() == Qt.MouseButton.RightButton:
            if self.drag is not None:
                i, horizontal, grab, origin = self.drag
                self.drag = (i, not horizontal, min(grab, self.lengths[i] - 1), origin)
                self.update()
                return
            hit = self.ship_at(pos)
            if hit and hit[1] == "board":
                self.rotate(hit[0])
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return
        hit = self.ship_at(pos)
        if hit is None:
            return
        i, where, x = hit
        if where == "board":
            s = self.placed[i]
            grab = s.index(x)
            origin = s
            self.placed[i] = None
        else:
            grab, origin = 0, None
        self.drag = (i, self.horizontal[i], grab, origin)
        self.drag_pos = pos
        self.update()

    def mouseMoveEvent(self, e):
        if self.drag is not None:
            self.drag_pos = e.position()
            self.update()
            return
        hit = self.ship_at(e.position())
        self.setCursor(Qt.CursorShape.OpenHandCursor if hit else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self.drag is None or e.button() != Qt.MouseButton.LeftButton:
            return
        i, horizontal, grab, origin = self.drag
        cells = self.target_cells(e.position())
        if cells is not None and can_place(self.others(i), cells, self.rules):
            self.placed[i] = cells
            self.horizontal[i] = horizontal
        else:
            self.placed[i] = origin            # не встал - на прежнее место (или на причал)
        self.drag = None
        self.update()
        self.changed.emit()

    def rotate(self, i):
        s = self.placed[i]
        if s is None or len(s) == 1:
            return False
        r, c = divmod(s[0], SIZE)
        cells = ship_cells(r, c, len(s), not self.horizontal[i])
        if cells is not None and can_place(self.others(i), cells, self.rules):
            self.placed[i] = cells
            self.horizontal[i] = not self.horizontal[i]
            self.update()
            self.changed.emit()
            return True
        self.flash = (i, time.monotonic() + 0.35)
        QTimer.singleShot(400, self.update)
        self.update()
        return False

    # --- рисование ---

    def paintEvent(self, event):
        self.view = [UNKNOWN] * N
        self.ships = []
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.c
        x0, y0, cell = self.geometry_()
        now = time.monotonic()
        for i, s in enumerate(self.placed):
            if s is not None:
                bad = self.flash is not None and self.flash[0] == i and now < self.flash[1]
                self.draw_ship(p, s, c["bad"] if bad else c["ship"], c["ship_edge"])
        for i, r in self.dock_slots().items():
            if not (self.drag and self.drag[0] == i):
                p.setPen(QPen(c["ship_edge"], 1.2))
                p.setBrush(c["ship"])
                p.drawRoundedRect(r, r.height() * 0.35, r.height() * 0.35)
        if self.drag is not None and self.drag_pos is not None:
            i = self.drag[0]
            cells = self.target_cells(self.drag_pos)
            if cells is not None:
                ok = can_place(self.others(i), cells, self.rules)
                self.draw_ship(p, cells, c["ok"] if ok else c["bad"], c["ship_edge"], 0.75)
            else:
                L = self.lengths[i]
                w, h = (L * cell, cell) if self.drag[1] else (cell, L * cell)
                gx = self.drag[2] * cell + cell / 2
                r = QRectF(self.drag_pos.x() - (gx if self.drag[1] else cell / 2),
                           self.drag_pos.y() - (cell / 2 if self.drag[1] else gx), w, h).adjusted(3, 3, -3, -3)
                col = QColor(c["ship"])
                col.setAlphaF(0.7)
                p.setPen(QPen(c["ship_edge"], 1.2))
                p.setBrush(col)
                p.drawRoundedRect(r, 8, 8)
        p.end()
