"""Карта вероятностей: точный перебор совпадает с полным перебором флотов на малом поле,
Монте-Карло совпадает с точным, привычки (априорные веса) учитываются одинаково."""
import itertools
from functools import lru_cache

import numpy as np
import pytest

from game.ai.prob import best_cell, estimate_count, exact_map, geometry, mc_map, probability_map
from game.core.battle import HIT, MISS, SUNK, UNKNOWN, Board, Observation
from game.core.rules import Rules, halo, placements, random_fleet, valid_fleet

SMALL = 5
FLEETS = [(3, 2, 1), (2, 2, 1, 1)]


@lru_cache(maxsize=None)
def all_fleets(fleet, corners):
    """Все расстановки флота на малом поле - простым перебором: каждый корабль на каждое место,
    одинаковые - сочетаниями, касания - по rules.halo. Итог сверяется с valid_fleet выборочно."""
    rules = Rules(corners=corners)
    places = {L: [(p, sum(1 << x for x in p), sum(1 << x for x in halo(p, corners, SMALL)))
                  for p in placements(L, SMALL)] for L in set(fleet)}
    groups = [list(itertools.combinations(places[L], fleet.count(L))) for L in sorted(set(fleet), reverse=True)]
    out = []
    for combo in itertools.product(*groups):
        ships = [s for g in combo for s in g]
        if all(not (a[1] & b[2]) for a, b in itertools.combinations(ships, 2)):
            out.append([s[0] for s in ships])
    assert all(valid_fleet(f, rules, fleet, SMALL) for f in out[::97])
    return out


def brute_posterior(fleet, corners, shots, view):
    """Доля флотов, которые на те же выстрелы дали бы то же поле, с кораблём на плаву в каждой клетке."""
    rules = Rules(corners=corners)
    p = np.zeros(SMALL * SMALL)
    n = 0
    for ships in all_fleets(fleet, corners):
        b = Board(ships, rules, SMALL)
        try:
            for x in shots:
                b.shoot(x)
        except ValueError:
            continue
        if b.view == view:
            n += 1
            for s, sunk in zip(b.ships, b.sunk):
                if not sunk:                 # карта - про корабли на плаву
                    p[list(s)] += 1
    return p / n, n


def scenario(fleet, corners, seed):
    rng = np.random.default_rng(seed)
    rules = Rules(corners=corners)
    ships = random_fleet(rng, rules, fleet, SMALL)
    b = Board(ships, rules, SMALL)
    shots = []
    k = int(rng.integers(0, 10))
    hits_first = seed % 3 == 0           # треть случаев - с попаданием в начале
    for i in range(k):
        cand = [x for x in range(SMALL * SMALL) if b.view[x] == UNKNOWN]
        if hits_first and i == 0:
            cand = [x for x in cand if x in b.owner] or cand
        x = int(cand[int(rng.integers(len(cand)))])
        b.shoot(x)
        shots.append(x)
        if b.all_sunk():
            break
    return b, shots


@pytest.mark.parametrize("fleet", FLEETS)
@pytest.mark.parametrize("corners", [False, True])
def test_exact_equals_brute_force(fleet, corners):
    checked = 0
    for seed in range(12):
        b, shots = scenario(fleet, corners, seed)
        if b.all_sunk():
            continue
        want, n = brute_posterior(fleet, corners, shots, b.view)
        got, leaves = exact_map(b.observation())
        assert leaves == n, (seed, shots)
        assert np.allclose(got, want, atol=1e-12), (seed, shots)
        checked += 1
    assert checked >= 8


@pytest.mark.parametrize("corners", [False, True])
def test_monte_carlo_matches_exact_on_small_board(corners):
    for seed in (0, 3, 6, 9, 4):
        b, shots = scenario((3, 2, 1), corners, seed)
        if b.all_sunk():
            continue
        o = b.observation()
        want, _ = exact_map(o)
        got, ess = mc_map(o, np.random.default_rng(seed), 6000)
        assert ess > 100
        assert np.abs(got - want).max() < 0.05, (seed, shots)


def test_monte_carlo_matches_exact_with_duplicates_and_hits_on_full_board():
    """Поле 10x10, поздняя партия: два двухпалубных и однопалубный, одно попадание."""
    grid = [MISS] * 100
    free = [x for x in range(100) if (x // 10) in (1, 2, 3, 6, 7) and (x % 10) < 7]
    for x in free:
        grid[x] = UNKNOWN
    grid[22] = HIT
    o = Observation(tuple(grid), (2, 2, 1))
    want, n = exact_map(o)
    assert n > 100
    assert abs(want[22] - 1) < 1e-12
    assert abs(want.sum() - 5) < 1e-9
    got, ess = mc_map(o, np.random.default_rng(1), 20000)
    assert np.abs(got - want).max() < 0.03


def test_adjacent_hits_are_one_ship_and_diagonals_of_hit_are_empty():
    grid = [UNKNOWN] * 100
    grid[44] = HIT
    grid[45] = HIT
    o = Observation(tuple(grid), (4, 3, 3, 2, 2, 2, 1, 1, 1, 1))
    p, how, _ = probability_map(o, np.random.default_rng(0))
    for x in (33, 35, 36, 53, 55, 56, 34, 54):          # клетки над и под попаданиями - пусто
        assert p[x] < 1e-12, x
    assert p[43] + p[46] > 0.5                           # корабль продолжается по линии
    assert best_cell(p, o, np.random.default_rng(0)) in (43, 46)


def test_sunk_neighbourhood_is_empty_and_probabilities_sum():
    rules = Rules()
    b = Board(random_fleet(np.random.default_rng(7), rules), rules)
    one = next(s for s in b.ships if len(s) == 1)
    b.shoot(one[0])
    o = b.observation()
    p, how, _ = probability_map(o, np.random.default_rng(1), samples=3000)
    assert how == "mc"
    for x in halo(one, False):
        assert p[x] == 0
    assert abs(p.sum() - 19) < 1e-6


def test_no_remaining_ships_gives_zeros():
    o = Observation(tuple([MISS] * 100), ())
    p, how, _ = probability_map(o, np.random.default_rng(0))
    assert not p.any()


def test_prior_weights_exact_and_monte_carlo_agree():
    """Привычки: места у края в 5 раз вероятнее - и перебор, и выборка считают одно и то же."""
    grid = [UNKNOWN] * 100
    for x in range(100):
        if not (x // 10 < 4 and x % 10 < 6):
            grid[x] = MISS
    o = Observation(tuple(grid), (3, 2, 1))
    geo = geometry(10, False, (1, 2, 3))
    prior = {L: np.array([5.0 if any(x % 10 == 0 or x // 10 == 0 for x in p) else 1.0
                          for p in geo.places[L]]) for L in (1, 2, 3)}
    plain, _ = exact_map(o)
    want, _ = exact_map(o, prior)
    got, _ = mc_map(o, np.random.default_rng(3), 20000, prior)
    assert np.abs(got - want).max() < 0.03
    edge = [x for x in range(100) if grid[x] == UNKNOWN and (x % 10 == 0 or x // 10 == 0)]
    assert want[edge].sum() > plain[edge].sum() + 0.5


def test_best_cell_only_unknown_and_ties_by_seed():
    grid = [UNKNOWN] * 100
    grid[0] = MISS
    o = Observation(tuple(grid), (1,))
    p = np.ones(100)
    picks = {best_cell(p, o, np.random.default_rng(s)) for s in range(40)}
    assert 0 not in picks and len(picks) > 20
    assert best_cell(p, o, np.random.default_rng(5)) == best_cell(p, o, np.random.default_rng(5))
    p[57] = 2
    assert best_cell(p, o, np.random.default_rng(0)) == 57


def test_map_is_deterministic_for_seed():
    o = Observation(tuple([UNKNOWN] * 100), (4, 3, 3, 2, 2, 2, 1, 1, 1, 1))
    a, _ = mc_map(o, np.random.default_rng(11), 300)
    b, _ = mc_map(o, np.random.default_rng(11), 300)
    assert np.array_equal(a, b)


def test_sunk_ship_blocks_neighbours_even_without_marks():
    """Наблюдение собрано вручную, клетки вокруг потопленного не отмечены - всё равно пусто."""
    grid = [UNKNOWN] * 100
    grid[44] = grid[45] = SUNK
    o = Observation(tuple(grid), (3, 1))
    p, _ = exact_map(o) if estimate_count(o) < 50000 else (None, 0)
    q, _ = mc_map(o, np.random.default_rng(0), 2000)
    for x in (33, 34, 35, 36, 43, 46, 53, 54, 55, 56):
        assert p[x] == 0 and q[x] == 0, x


def test_identical_ships_after_hits_weigh_right():
    """Попадание накрыто трёхпалубным или одним из двух двухпалубных - и во второй фазе
    выборки остаётся разное число одинаковых кораблей. Без деления веса на k! выборка
    ошибается на 0.06 (проверено), с делением - меньше 0.01. (Однопалубный попадание не
    накрывает никогда: он был бы уже потоплен.)"""
    grid = [MISS] * 100
    for x in range(100):
        if x // 10 in (2, 3, 4) and x % 10 < 8:
            grid[x] = UNKNOWN
    grid[33] = HIT
    o = Observation(tuple(grid), (3, 2, 2))
    want, _ = exact_map(o)
    got, _ = mc_map(o, np.random.default_rng(2), 20000)
    assert np.abs(got - want).max() < 0.02
