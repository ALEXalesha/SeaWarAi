"""Стрелки трёх уровней. Каждый получает только Observation - что сам узнал о чужом поле -
и генератор случайных чисел. Флота соперника стрелок не видит.

- новичок: случайная неизвестная клетка; ранил - добивает (соседи попадания, потом по линии);
- средний: «охота и добивание»: охота по шахматному шагу, добивание по линии, клетки по
  диагонали от попадания пропускает (там корабля быть не может);
- сильный: карта вероятностей (prob.probability_map) с привычками игрока; раненый корабль
  добивает в клетке с наибольшей вероятностью среди тех, где он может продолжаться.

think(obs, rng) - «Мысли ИИ»: вес каждой клетки, куда стрелок хочет выстрелить (0..1).
"""
import numpy as np

from game.ai import prob
from game.core.battle import UNKNOWN
from game.core.rules import neighbors

LEVELS = ("novice", "medium", "strong")


def hit_groups(obs):
    """Попадания по кораблям на плаву, собранные в группы соседей по стороне: соседние
    попадания - один корабль (разные корабли сторонами не касаются)."""
    hits = set(obs.hits())
    groups = []
    while hits:
        start = min(hits)
        group, stack = {start}, [start]
        hits.discard(start)
        while stack:
            x = stack.pop()
            for y in neighbors(x, True, obs.size):
                if y in hits:
                    hits.discard(y)
                    group.add(y)
                    stack.append(y)
        groups.append(sorted(group))
    return groups


def finish_cells(obs, group):
    """Куда стрелять, чтобы добить: продолжение линии, а у одиночного попадания - 4 соседа."""
    size = obs.size
    unknown = lambda x: obs.grid[x] == UNKNOWN  # noqa: E731
    if len(group) == 1:
        return [y for y in neighbors(group[0], True, size) if unknown(y)]
    horizontal = group[1] - group[0] == 1
    step = 1 if horizontal else size
    out = []
    lo, hi = group[0], group[-1]
    if (lo % size if horizontal else lo // size) > 0 and unknown(lo - step):
        out.append(lo - step)
    if (hi % size if horizontal else hi // size) < size - 1 and unknown(hi + step):
        out.append(hi + step)
    return out


def _uniform_map(obs, cells):
    p = np.zeros(obs.size * obs.size)
    if cells:
        p[list(cells)] = 1.0
    return p


class NoviceAgent:
    level = "novice"

    def candidates(self, obs):
        for g in hit_groups(obs):
            cells = finish_cells(obs, g)
            if cells:
                return cells
        return obs.unknown()

    def choose(self, obs, rng):
        cells = self.candidates(obs)
        return int(cells[int(rng.integers(len(cells)))])

    def think(self, obs, rng):
        return _uniform_map(obs, self.candidates(obs))


class MediumAgent(NoviceAgent):
    level = "medium"

    def __init__(self, parity=0):
        self.parity = parity

    def candidates(self, obs):
        size = obs.size
        for g in hit_groups(obs):
            cells = finish_cells(obs, g)
            if cells:
                return cells
        banned = set()
        for x in ([] if obs.corners else obs.hits()):     # по диагонали от попадания - пусто
            r, c = divmod(x, size)
            for dr in (-1, 1):
                for dc in (-1, 1):
                    if 0 <= r + dr < size and 0 <= c + dc < size:
                        banned.add((r + dr) * size + c + dc)
        unknown = [x for x in obs.unknown() if x not in banned]
        largest = max(obs.remaining) if obs.remaining else 1
        if largest >= 2:                     # пока есть корабли от двух палуб - через клетку
            even = [x for x in unknown if (x // size + x % size) % 2 == self.parity]
            if even:
                return even
        return unknown or obs.unknown()


class StrongAgent:
    level = "strong"

    def __init__(self, habits=None, samples=prob.DEFAULT_SAMPLES):
        self.habits = habits
        self.samples = samples
        self.last_method = None

    def prior(self, obs):
        if self.habits is None or not obs.remaining:
            return None
        geo = prob.geometry(obs.size, obs.corners, tuple(sorted(set(obs.remaining))))
        return self.habits.prior(geo, sorted(set(obs.remaining)))

    def think(self, obs, rng):
        p, how, _ = prob.probability_map(obs, rng, self.samples, self.prior(obs))
        self.last_method = how
        p = np.array(p, dtype=float)
        p[[i for i, v in enumerate(obs.grid) if v != UNKNOWN]] = 0.0
        return p

    def choose(self, obs, rng):
        """Клетка с наибольшей вероятностью. Есть раненый корабль - только среди клеток, где
        он может продолжаться: по силе то же самое (56.05 против 56.13 выстрела на 150
        партиях), но ИИ не стреляет через клетку от раненого, как будто его не заметил."""
        p = self.think(obs, rng)
        for g in hit_groups(obs):
            cells = finish_cells(obs, g)
            if cells:
                mask = np.zeros_like(p)
                mask[cells] = 1.0
                if (p * mask).max() > 0:
                    p = p * mask
                break
        return prob.best_cell(p, obs, rng)


def make_agent(level, habits=None, samples=prob.DEFAULT_SAMPLES, parity=0):
    if level == "novice":
        return NoviceAgent()
    if level == "medium":
        return MediumAgent(parity)
    if level == "strong":
        return StrongAgent(habits, samples)
    raise ValueError(level)

