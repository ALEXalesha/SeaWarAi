"""Расстановка флота ИИ.

Сколько выстрелов нужно стрелку, решает в основном то, сколько клеток откроется само вокруг
потопленных кораблей: около 100 - автоотметки - неизвестные в конце. Корабль у края или в
углу открывает вокруг себя меньше клеток, чем корабль посреди воды, поэтому флот с малым
ореолом живёт дольше.

Сильный ИИ берёт CANDIDATES почти равновероятных расстановок (одна выборка с весами,
prob.uniform_fleets) и выбирает случайно одну из TOP с наименьшей оценкой. Оценка - ореол
(клетки кораблей и вокруг них) плюс SHOT_WEIGHT за каждую клетку корабля там, куда игрок
обычно стреляет первым (привычки). Узнаваемого шаблона нет: каждая партия - своя
расстановка, только с малым ореолом.

Проверка на партиях (паспорт): против сильного и среднего стрелка такой флот живёт дольше
случайного. Первая версия (60 расстановок «корабль за кораблём», подальше от клеток, куда
стреляют первым) жила МЕНЬШЕ случайной - 54.6 выстрела против 55.9 у сильного: корабли
уходили в середину поля, а там у них большие ореолы.

Новичок и средний ставят просто случайно.
"""
import numpy as np

from game.ai.prob import uniform_fleets
from game.core.rules import Rules, halo, random_fleet

CANDIDATES = 40
TOP = 3
SHOT_WEIGHT = 2.0


def halo_size(ships, corners=False):
    cells = set()
    for s in ships:
        cells |= halo(s, corners)
    return len(cells)


def fleet_score(ships, rules=Rules(), habits=None):
    score = float(halo_size(ships, rules.corners))
    if habits is not None:
        shots = habits.shot_map()
        score += SHOT_WEIGHT * float(sum(shots[list(s)].sum() for s in ships))
    return score


def ai_fleet(rng, rules=Rules(), habits=None, level="strong", candidates=CANDIDATES, top=TOP):
    if level != "strong":
        return random_fleet(rng, rules)
    fleets = uniform_fleets(rng, candidates, rules.corners)
    order = np.argsort([fleet_score(f, rules, habits) for f in fleets], kind="stable")
    return fleets[int(order[int(rng.integers(min(top, len(order))))])]
