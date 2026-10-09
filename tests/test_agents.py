"""Стрелки: добивание, шахматная охота, карта вероятностей, только допустимые клетки, зерно."""
import numpy as np
import pytest

from game.ai.agents import LEVELS, MediumAgent, NoviceAgent, StrongAgent, finish_cells, hit_groups, make_agent
from game.ai.prob import uniform_fleet
from game.core.battle import HIT, MISS, SUNK, UNKNOWN, Board, Observation

FULL = (4, 3, 3, 2, 2, 2, 1, 1, 1, 1)


def obs_with(hits=(), misses=(), sunk=(), remaining=FULL, corners=False):
    g = [UNKNOWN] * 100
    for x in hits:
        g[x] = HIT
    for x in misses:
        g[x] = MISS
    for x in sunk:
        g[x] = SUNK
    return Observation(tuple(g), remaining, corners)


def test_hit_groups_join_side_neighbours_only():
    o = obs_with(hits=(44, 45, 77, 0))
    assert hit_groups(o) == [[0], [44, 45], [77]]


def test_finish_cells_single_line_and_edges():
    assert sorted(finish_cells(obs_with(hits=(44,)), [44])) == [34, 43, 45, 54]
    assert sorted(finish_cells(obs_with(hits=(0,)), [0])) == [1, 10]
    assert sorted(finish_cells(obs_with(hits=(44, 45)), [44, 45])) == [43, 46]
    assert finish_cells(obs_with(hits=(8, 9)), [8, 9]) == [7]                     # у края - одна сторона
    assert sorted(finish_cells(obs_with(hits=(34, 44)), [34, 44])) == [24, 54]   # вертикальный
    assert finish_cells(obs_with(hits=(44, 45), misses=(43,)), [44, 45]) == [46]


@pytest.mark.parametrize("agent", [NoviceAgent(), MediumAgent(0), MediumAgent(1), StrongAgent(samples=300)])
def test_every_level_finishes_wounded_ship_along_the_line(agent):
    rng = np.random.default_rng(0)
    for _ in range(5):
        assert agent.choose(obs_with(hits=(44,)), rng) in (34, 43, 45, 54)
        assert agent.choose(obs_with(hits=(44, 45)), rng) in (43, 46)


def test_medium_hunts_on_its_colour_while_big_ships_are_afloat():
    for parity in (0, 1):
        a = MediumAgent(parity)
        rng = np.random.default_rng(parity)
        for _ in range(30):
            x = a.choose(obs_with(), rng)
            assert (x // 10 + x % 10) % 2 == parity
    singles = obs_with(remaining=(1, 1))
    picks = {MediumAgent(0).choose(singles, np.random.default_rng(s)) for s in range(60)}
    assert {(x // 10 + x % 10) % 2 for x in picks} == {0, 1}


def test_medium_skips_diagonals_of_hits_only_with_strict_rule():
    # попадание, у которого все четыре соседа уже промахи: добивать некуда, охота идёт дальше
    o = obs_with(hits=(44,), misses=(34, 43, 45, 54), remaining=(2, 1))
    cells = set(MediumAgent(0).candidates(o))
    assert not cells & {33, 35, 53, 55}
    oc = obs_with(hits=(44,), misses=(34, 43, 45, 54), remaining=(2, 1), corners=True)
    assert set(MediumAgent(0).candidates(oc)) & {33, 35, 53, 55}


def test_strong_takes_the_only_possible_cell():
    misses = [x for x in range(100) if x not in (57, 58)]
    o = obs_with(misses=misses, remaining=(1,))
    assert StrongAgent().choose(o, np.random.default_rng(0)) in (57, 58)
    o = obs_with(misses=[x for x in range(100) if x not in (12, 13, 14)], hits=(13,), remaining=(3,))
    assert StrongAgent().choose(o, np.random.default_rng(0)) in (12, 14)


def test_strong_prefers_edges_on_empty_board():
    """При равновероятной расстановке корабль у края чаще - первый выстрел туда."""
    a = StrongAgent(samples=2000)
    firsts = [a.choose(obs_with(), np.random.default_rng(s)) for s in range(6)]
    edge_or_third = lambda x: x // 10 in (0, 2, 7, 9) or x % 10 in (0, 2, 7, 9)  # noqa: E731
    assert all(edge_or_third(x) for x in firsts), firsts


@pytest.mark.parametrize("level", LEVELS)
def test_think_is_zero_on_known_cells(level):
    o = obs_with(hits=(44,), misses=(0, 1, 2))
    p = make_agent(level, samples=200).think(o, np.random.default_rng(1))
    assert p.shape == (100,) and p[[0, 1, 2, 44]].sum() == 0 and p.max() > 0


@pytest.mark.parametrize("level", LEVELS)
def test_full_game_only_legal_shots_and_same_seed_same_game(level):
    def play(seed):
        b = Board(uniform_fleet(np.random.default_rng(seed)))
        a = make_agent(level, samples=200, parity=seed % 2)
        rng = np.random.default_rng(seed + 100)
        shots = []
        while not b.all_sunk():
            o = b.observation()
            x = a.choose(o, rng)
            assert o.grid[x] == UNKNOWN
            b.shoot(x)
            shots.append(x)
            assert len(shots) <= 100
        return shots
    a = play(3)
    assert a == play(3) and 20 <= len(a) <= 100


def test_make_agent_rejects_unknown_level():
    with pytest.raises(ValueError):
        make_agent("genius")
