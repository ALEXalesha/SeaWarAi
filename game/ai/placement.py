"""Расстановка флота ИИ.

Сильный стрелок начинает с клеток, где корабль вероятнее при равновероятной расстановке
(края поля и третьи ряды, habits.empty_board_map), а игрок может иметь свои привычки -
например, бить сначала в центр. ИИ берёт CANDIDATES случайных расстановок, оценивает риск
каждой (сумма по клеткам кораблей: карта пустого поля плюс SHOT_WEIGHT × где игрок стреляет
первым) и выбирает случайно одну из лучших TOP. Так нет одного узнаваемого шаблона:
каждая партия - новая расстановка, только смещённая туда, куда стреляют позже.

level 'novice' и 'medium' ставят просто случайно.
"""
import numpy as np

from game.ai.habits import empty_board_map
from game.core.rules import Rules, random_fleet

CANDIDATES = 60
TOP = 6
SHOT_WEIGHT = 0.15


def risk_map(rules=Rules(), habits=None):
    base = empty_board_map(rules.corners)
    risk = base / base.max()
    if habits is not None:
        risk = risk + SHOT_WEIGHT * habits.shot_map() * 4
    return risk


def fleet_risk(ships, risk):
    return float(sum(risk[list(s)].sum() for s in ships))


def ai_fleet(rng, rules=Rules(), habits=None, level="strong", candidates=CANDIDATES, top=TOP):
    if level != "strong":
        return random_fleet(rng, rules)
    risk = risk_map(rules, habits)
    fleets = [random_fleet(rng, rules) for _ in range(candidates)]
    order = np.argsort([fleet_risk(f, risk) for f in fleets], kind="stable")
    return fleets[int(order[int(rng.integers(min(top, len(order))))])]
