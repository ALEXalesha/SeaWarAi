"""Привычки игрока: где он ставит корабли и куда стреляет первым.

Хранятся в ctx.data_dir/habits.json, сбрасываются из настроек. Две части:

- **расстановка**: по каждой длине корабля - сколько раз корабль этой длины стоял в каждой
  клетке. Отсюда априорный вес каждого места корабля для карты вероятностей сильного ИИ:
  среднее геометрическое по клеткам места отношения «частота у игрока / частота при
  случайной расстановке». Частоты сглажены: к счёту прибавляются SMOOTH партий случайной
  расстановки и немного соседних клеток - после двух-трёх партий привычки весят мало;
- **стрельба**: куда игрок стреляет в первые FIRST_SHOTS выстрелов партии - это учитывает
  расстановка ИИ.
"""
import json
import os
from functools import lru_cache

import numpy as np

from aikit.storage import is_int, load_json, save_json
from game.core.rules import FLEET, SIZE

LENGTHS = (1, 2, 3, 4)
SMOOTH = 6.0            # сколько «случайных партий» подмешано к счёту
BLUR = 0.25             # доля счёта, уходящая соседним клеткам
FIRST_SHOTS = 12
N = SIZE * SIZE


BASE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models",
                         "base_frequency.json")


@lru_cache(maxsize=4)
def base_frequency(corners=False):
    """Доля партий, в которых корабль длины L стоит в клетке, при равновероятной расстановке
    (таблица tools/make_base.py)."""
    with open(BASE_FILE, encoding="utf-8") as f:
        data = json.load(f)["corners" if corners else "strict"]
    return {L: np.array(data[str(L)], dtype=float) for L in LENGTHS}


def empty_board_map(corners=False):
    """Вероятность корабля в клетке на пустом поле - куда сильный ИИ стреляет в начале."""
    base = base_frequency(corners)
    return sum(base[L] for L in LENGTHS)


def _blur(v):
    g = v.reshape(SIZE, SIZE)
    acc = np.zeros_like(g)
    cnt = np.zeros_like(g)
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        sh = np.zeros_like(g)
        ones = np.zeros_like(g)
        rs = slice(max(dr, 0), SIZE + min(dr, 0))
        rd = slice(max(-dr, 0), SIZE + min(-dr, 0))
        cs = slice(max(dc, 0), SIZE + min(dc, 0))
        cd = slice(max(-dc, 0), SIZE + min(-dc, 0))
        sh[rd, cd] = g[rs, cs]
        ones[rd, cd] = 1
        acc += sh
        cnt += ones
    return ((1 - BLUR) * g + BLUR * acc / cnt).ravel()


class Habits:
    def __init__(self, path=None):
        self.path = path
        self.reset(save=False)
        if path is not None:
            self._load(load_json(path))

    def reset(self, save=True):
        self.games = 0
        self.cells = {L: np.zeros(N) for L in LENGTHS}
        self.shot_games = 0
        self.shots = np.zeros(N)
        if save:
            self.save()

    def _load(self, raw):
        if not isinstance(raw, dict):
            return
        try:
            games, shot_games = raw.get("games"), raw.get("shot_games")
            cells = {L: np.array(raw["cells"][str(L)], dtype=float) for L in LENGTHS}
            shots = np.array(raw["shots"], dtype=float)
        except (KeyError, TypeError, ValueError):
            return
        if not (is_int(games) and is_int(shot_games) and games >= 0 and shot_games >= 0):
            return
        if any(v.shape != (N,) or (v < 0).any() or not np.isfinite(v).all() for v in [*cells.values(), shots]):
            return
        self.games, self.cells, self.shot_games, self.shots = games, cells, shot_games, shots

    def to_json(self):
        return {"games": self.games, "cells": {str(L): self.cells[L].tolist() for L in LENGTHS},
                "shot_games": self.shot_games, "shots": self.shots.tolist()}

    def save(self):
        if self.path is None:
            return False
        return save_json(self.path, self.to_json())

    def record_fleet(self, ships, save=True):
        if sorted(len(s) for s in ships) != sorted(FLEET):
            return
        for s in ships:
            self.cells[len(s)][list(s)] += 1
        self.games += 1
        if save:
            self.save()

    def record_shots(self, cells, save=True):
        """Первые выстрелы игрока в партии (по порядку)."""
        cells = list(cells)[:FIRST_SHOTS]
        if not cells:
            return
        for k, x in enumerate(cells):
            self.shots[x] += 1.0 - k / (2 * FIRST_SHOTS)      # ранние весят чуть больше
        self.shot_games += 1
        if save:
            self.save()

    def ratios(self, corners=False):
        """По длине: отношение сглаженной частоты игрока к частоте случайной расстановки."""
        base = base_frequency(corners)
        out = {}
        for L in LENGTHS:
            b = np.maximum(base[L], 1e-6)
            f = (_blur(self.cells[L]) + SMOOTH * b) / (self.games + SMOOTH)
            out[L] = f / b
        return out

    def prior(self, geo, lengths):
        """Априорные веса мест для prob.probability_map или None, если партий ещё нет."""
        if self.games == 0:
            return None
        r = self.ratios(geo.corners)
        out = {}
        for L in lengths:
            logs = np.log(r[L])
            out[L] = np.exp(geo.cells[L].astype(float) @ logs / L)
        return out

    def shot_map(self):
        """Где игрок стреляет первым: доля, 0..1 (максимум - 1). Нули, если данных нет."""
        if self.shot_games == 0 or self.shots.max() <= 0:
            return np.zeros(N)
        return self.shots / self.shots.max()
