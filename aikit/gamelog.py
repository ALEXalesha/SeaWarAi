"""Журнал партий игрока - данные для графиков статистики (aikit.charts).

Файл (обычно games.json в ctx.data_dir): {"next": номер следующей партии, "games": [...]}.
В каждой партии обязательно n (сквозной номер, с 1), level (уровень ИИ, строка) и outcome
('win' / 'loss' / 'draw' - для человека); остальное - числа или короткие строки игры
(ходов, секунд, очков, режим...). Хранятся последние cap партий. Битый файл - пустой
журнал, битая запись пропускается, поле не того вида отбрасывается. Пишутся только те
партии, что идут и в статистику (не показ «ИИ против ИИ», не подсмотренные).

Ряды для графиков считаются здесь же чистыми функциями: их законы проверяются без Qt.
"""
import math

from aikit.storage import is_int, load_json, save_json

OUTCOMES = ("win", "loss", "draw")
VALUE = {"win": 1.0, "draw": 0.5, "loss": 0.0}
CAP = 5000
TEXT_MAX = 40


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _field_ok(v):
    return is_num(v) or isinstance(v, bool) or (isinstance(v, str) and len(v) <= TEXT_MAX)


def valid(g):
    return (isinstance(g, dict) and g.get("outcome") in OUTCOMES
            and isinstance(g.get("level"), str) and 0 < len(g["level"]) <= TEXT_MAX)


def _tidy(g):
    return {k: v for k, v in g.items() if isinstance(k, str) and k != "n" and _field_ok(v)}


class GameLog:
    def __init__(self, path=None, cap=CAP):
        self.path = path
        self.cap = cap
        self.games = []
        self.next = 1
        raw = load_json(path) if path else None
        if isinstance(raw, dict) and isinstance(raw.get("games"), list):
            for g in raw["games"]:
                if valid(g) and is_int(g.get("n")) and g["n"] >= 1:
                    self.games.append({"n": g["n"], **_tidy(g)})
            self.games.sort(key=lambda g: g["n"])
            self.games = self.games[-cap:]
            last = max((g["n"] for g in self.games), default=0)
            self.next = max(last + 1, raw["next"] if is_int(raw.get("next")) else 1)

    def record(self, game):
        """Записать партию; возвращает запись с номером n. Без level/outcome - ValueError."""
        if not valid(game):
            raise ValueError(f"битая запись партии: {game!r}")
        g = {"n": self.next, **_tidy(game)}
        self.next += 1
        self.games.append(g)
        del self.games[:-self.cap]
        self.save()
        return g

    def save(self):
        if self.path is None:
            return False
        return save_json(self.path, {"next": self.next, "games": self.games})


def rolling_share(games, window=20):
    """Доля очков (победа 1, ничья 1/2) по последним window партиям; None - за все партии.
    Точка на каждую партию: (номер партии, доля)."""
    out = []
    total = 0.0
    vals = [VALUE[g["outcome"]] for g in games]
    for k, g in enumerate(games):
        total += vals[k]
        if window is not None and k >= window:
            total -= vals[k - window]
        n = k + 1 if window is None else min(k + 1, window)
        out.append((g["n"], total / n))
    return out


def by_level(games, levels):
    """Доли побед, ничьих и поражений по уровням ИИ в порядке levels (не по алфавиту:
    «средний» не должен встать раньше «новичка»). Уровни без партий не показываются, ничьи -
    только если они были. Возвращает (уровни, [(итог, [доли по уровням])])."""
    count = {lv: {o: 0 for o in OUTCOMES} for lv in levels}
    for g in games:
        if g["level"] in count:
            count[g["level"]][g["outcome"]] += 1
    groups = [lv for lv in levels if sum(count[lv].values())]
    shown = [o for o in ("win", "draw", "loss") if o != "draw" or any(count[lv]["draw"] for lv in groups)]
    series = [(o, [count[lv][o] / sum(count[lv].values()) for lv in groups]) for o in shown]
    return groups, series


def series(games, key):
    """(номер партии, значение поля) - длина партии, очки, время. Партии без числа в этом
    поле пропускаются."""
    return [(g["n"], g[key]) for g in games if is_num(g.get(key))]


def best_curve(games, key, better="max"):
    """Рекорд к каждой партии: лучшее значение поля среди этой и прежних (better="min" -
    меньше лучше, например время)."""
    out = []
    best = None
    for n, v in series(games, key):
        if best is None or (v > best if better == "max" else v < best):
            best = v
        out.append((n, best))
    return out


def streaks(games):
    """Серия побед подряд после каждой партии и лучшая серия к этому моменту - график
    рекордов там, где у партии нет очков. Ничья и поражение обрывают серию (как aikit.stats)."""
    cur = best = 0
    now, top = [], []
    for g in games:
        cur = cur + 1 if g["outcome"] == "win" else 0
        best = max(best, cur)
        now.append((g["n"], cur))
        top.append((g["n"], best))
    return now, top


def mean_by_level(games, key, levels):
    """Среднее числового поля по уровням в порядке levels: (уровни, [средние])."""
    vals = {lv: [] for lv in levels}
    for g in games:
        if g["level"] in vals and is_num(g.get(key)):
            vals[g["level"]].append(g[key])
    groups = [lv for lv in levels if vals[lv]]
    return groups, [sum(vals[lv]) / len(vals[lv]) for lv in groups]
