"""Проверки силы: сколько выстрелов нужно, чтобы потопить флот, и партии стрелок против стрелка.

У партии i свои генераторы: флот - default_rng([seed, i, 0]), стрелок - default_rng([seed, i, 1]),
второй флот и второй стрелок - [seed, i, 2] и [seed, i, 3]. Любую партию можно пересчитать
отдельно и сверить с паспортом.
"""
from functools import lru_cache

import numpy as np

from game.ai.agents import make_agent
from game.ai.placement import ai_fleet
from game.ai.prob import uniform_fleet
from game.core.battle import Board, Match
from game.core.rules import Rules, random_fleet


def rngs(seed, i):
    return [np.random.default_rng([int(seed), int(i), k]) for k in range(4)]


def make_fleet(placer, rng, rules=Rules(), habits=None):
    """'random' - все расстановки равновероятны; 'sequential' - корабль за кораблём на
    случайное свободное место; 'ai' - расстановка сильного ИИ."""
    if placer == "random":
        return uniform_fleet(rng, rules.corners)
    if placer == "sequential":
        return random_fleet(rng, rules)
    if placer == "ai":
        return ai_fleet(rng, rules, habits)
    if placer == "edge":
        return edge_lover_fleet(rng, rules)
    if placer == "centre":
        return centre_lover_fleet(rng, rules)
    raise ValueError(placer)


def edge_lover_fleet(rng, rules=Rules(), tries=40):
    """Игрок с привычкой ставить к краям: из tries случайных расстановок берёт ту, где
    больше всего клеток у края поля."""
    best = None
    for _ in range(tries):
        f = random_fleet(rng, rules)
        score = sum(1 for s in f for x in s if x // 10 in (0, 9) or x % 10 in (0, 9))
        if best is None or score > best[0]:
            best = (score, f)
    return best[1]


def centre_lover_fleet(rng, rules=Rules(), tries=40):
    """Игрок с привычкой ставить в середину: из tries случайных расстановок берёт ту, где
    больше всего клеток во внутреннем квадрате 6 x 6."""
    best = None
    for _ in range(tries):
        f = random_fleet(rng, rules)
        score = sum(1 for s in f for x in s if 2 <= x // 10 <= 7 and 2 <= x % 10 <= 7)
        if best is None or score > best[0]:
            best = (score, f)
    return best[1]


@lru_cache(maxsize=4)
def learned_habits(seed, games, rules=Rules(), player="edge"):
    """Привычки, выученные по games расстановкам игрока (одни на процесс)."""
    from game.ai.habits import Habits
    h = Habits()
    rng = np.random.default_rng([int(seed), 999])
    make = edge_lover_fleet if player == "edge" else centre_lover_fleet
    for _ in range(games):
        h.record_fleet(make(rng, rules), save=False)
    return h


def shots_to_sink(level, seed, i, rules=Rules(), placer="random", samples=None, habits=None):
    """Выстрелов уровня level до гибели всего флота. habits - привычки, которые знает
    сильный стрелок."""
    r_fleet, r_shoot, _, _ = rngs(seed, i)
    fleet = make_fleet(placer, r_fleet, rules)
    kw = {} if samples is None else {"samples": samples}
    agent = make_agent(level, habits=habits, parity=i % 2, **kw)
    board = Board(fleet, rules)
    shots = 0
    while not board.all_sunk():
        board.shoot(agent.choose(board.observation(), r_shoot))
        shots += 1
        if shots > 100:
            raise RuntimeError("больше 100 выстрелов")
    return shots


def duel(level_a, level_b, seed, i, rules=Rules(), samples=None):
    """Партия: a против b, флоты случайные, первым ходит a в чётных партиях. 'W' - выиграл a."""
    ra_fleet, ra_shoot, rb_fleet, rb_shoot = rngs(seed, i)
    kw = {} if samples is None else {"samples": samples}
    agents = [make_agent(level_a, parity=i % 2, **kw), make_agent(level_b, parity=(i + 1) % 2, **kw)]
    shoot = [ra_shoot, rb_shoot]
    m = Match([uniform_fleet(ra_fleet, rules.corners), uniform_fleet(rb_fleet, rules.corners)], rules, first=i % 2)
    while not m.over:
        p = m.turn
        m.fire(agents[p].choose(m.observation(p), shoot[p]))
    return "W" if m.winner == 0 else "L"
