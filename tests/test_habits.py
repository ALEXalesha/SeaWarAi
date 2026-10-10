"""Привычки игрока и расстановка ИИ."""
import json

import numpy as np

from game.ai.agents import StrongAgent
from game.ai.habits import FIRST_SHOTS, Habits, base_frequency, empty_board_map
from game.ai.placement import ai_fleet, halo_size
from game.ai.prob import geometry
from game.core.battle import Observation
from game.core.rules import FLEET, Rules, random_fleet, valid_fleet

EDGE = [(0, 1, 2, 3), (9, 19, 29), (90, 91, 92), (39, 49), (5, 6), (99, 89)]


def edge_fleet(rng):
    """Игрок, который любит края: из 40 случайных расстановок берёт ту, где больше клеток у края."""
    best = None
    for _ in range(40):
        f = random_fleet(rng)
        score = sum(1 for s in f for x in s if x // 10 in (0, 9) or x % 10 in (0, 9))
        if best is None or score > best[0]:
            best = (score, f)
    return best[1]


def test_base_frequency_table_matches_fleet():
    for corners in (False, True):
        base = base_frequency(corners)
        for L in (1, 2, 3, 4):
            assert abs(base[L].sum() - L * FLEET.count(L)) < 0.02
    m = empty_board_map().reshape(10, 10)
    assert m[0].mean() > m[1].mean() + 0.05            # у края корабли чаще, во втором ряду реже


def test_record_save_load_reset(tmp_path):
    path = tmp_path / "habits.json"
    h = Habits(str(path))
    assert h.games == 0 and h.prior(geometry(), (1, 2, 3, 4)) is None
    h.record_fleet(random_fleet(np.random.default_rng(1)))
    h.record_fleet([(0, 1)])                            # не флот - не считается
    h.record_shots([55, 44, 33] + list(range(FIRST_SHOTS + 5)))
    h2 = Habits(str(path))
    assert h2.games == 1 and h2.shot_games == 1
    assert sum(h2.cells[L].sum() for L in (1, 2, 3, 4)) == 20
    assert h2.shot_map()[55] == 1.0 and h2.shot_map()[FIRST_SHOTS + 4] == 0
    h2.reset()
    assert Habits(str(path)).games == 0


def test_broken_file_gives_empty_habits(tmp_path):
    path = tmp_path / "habits.json"
    for junk in ("{", "[]", json.dumps({"games": -1}), json.dumps({"games": 2, "shot_games": 0,
                                                                     "cells": {"1": [0] * 5}, "shots": []})):
        path.write_text(junk, encoding="utf-8")
        assert Habits(str(path)).games == 0


def test_edge_habits_raise_edge_probability():
    h = Habits()
    rng = np.random.default_rng(2)
    for _ in range(30):
        h.record_fleet(edge_fleet(rng))
    prior = h.prior(geometry(), (1, 2, 3, 4))
    geo = geometry()
    edge = [i for i, p in enumerate(geo.places[4]) if all(x // 10 == 0 for x in p)]
    inner = [i for i, p in enumerate(geo.places[4]) if all(x // 10 == 4 for x in p) and p[0] % 10 in (3, 4)]
    assert prior[4][edge].mean() > 1.5 * prior[4][inner].mean()
    o = Observation(tuple([0] * 100), tuple(sorted(FLEET, reverse=True)))
    rim = [x for x in range(100) if x // 10 in (0, 9) or x % 10 in (0, 9)]
    plain = StrongAgent(samples=3000).think(o, np.random.default_rng(1))
    learned = StrongAgent(h, samples=3000).think(o, np.random.default_rng(1))
    assert learned[rim].sum() > plain[rim].sum() + 1.0


def test_few_games_weigh_little():
    h = Habits()
    h.record_fleet(EDGE + [(55,), (57,), (77,), (75,)])
    prior = h.prior(geometry(), (1, 2, 3, 4))
    for L in (1, 2, 3, 4):
        assert 0.3 < prior[L].min() and prior[L].max() < 3


def test_ai_fleet_valid_varied_and_small_halo():
    rng = np.random.default_rng(4)
    fleets = [ai_fleet(rng) for _ in range(25)]
    assert all(valid_fleet(f) for f in fleets)
    assert len({tuple(sorted(f)) for f in fleets}) >= 24
    rand = [random_fleet(rng) for _ in range(25)]
    assert np.mean([halo_size(f) for f in fleets]) < np.mean([halo_size(f) for f in rand]) - 5


def test_ai_fleet_fast_enough_for_game_start():
    import time
    rng = np.random.default_rng(1)
    t0 = time.perf_counter()
    for _ in range(5):
        ai_fleet(rng)
    assert (time.perf_counter() - t0) / 5 < 0.5


def test_ai_fleet_avoids_where_player_shoots_first():
    h = Habits()
    hot = [x for x in range(100) if x // 10 in (0, 9) or x % 10 in (0, 9)][:FIRST_SHOTS]
    for _ in range(10):
        h.record_shots(hot)
    rng = np.random.default_rng(5)
    with_h = [ai_fleet(rng, Rules(), h) for _ in range(20)]
    without = [ai_fleet(rng, Rules(), None) for _ in range(20)]
    count = lambda fs: sum(1 for f in fs for s in f for x in s if x in set(hot))  # noqa: E731
    assert count(with_h) < count(without)


def test_lower_levels_place_randomly():
    a = ai_fleet(np.random.default_rng(1), level="novice")
    assert a == random_fleet(np.random.default_rng(1))
