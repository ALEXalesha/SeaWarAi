"""Закон честности: стреляющий ИИ не видит поле игрока, только результаты своих выстрелов.

Берётся партия на середине. Строится ДРУГОЙ флот игрока, который на те же выстрелы дал бы
те же ответы (потопленные на месте, остальные корабли переставлены куда угодно по
правилам). Тогда наблюдение ИИ то же самое, и следующий выстрел каждого уровня при том же
зерне - тот же. Если бы ИИ подглядывал во флот, выстрелы разошлись бы.
"""
import numpy as np
import pytest

from game.ai.agents import LEVELS, make_agent
from game.ai.prob import sample_fleet, ships_from_cells, uniform_fleet
from game.core.battle import SUNK, Board
from game.core.rules import Rules, valid_fleet


def midgame(seed, shots, corners=False):
    rules = Rules(corners=corners)
    rng = np.random.default_rng(seed)
    b = Board(uniform_fleet(rng, corners), rules)
    shooter = make_agent("medium", parity=seed % 2)
    fired = []
    while len(fired) < shots and not b.all_sunk():
        x = shooter.choose(b.observation(), rng)
        b.shoot(x)
        fired.append(x)
    return b, fired, rules


def another_fleet(board, rules, rng):
    """Другой флот с теми же ответами: потопленные - те же, остальные - по наблюдению."""
    o = board.observation()
    sunk = ships_from_cells([i for i, v in enumerate(o.grid) if v == SUNK])
    for _ in range(20):
        rest = sample_fleet(o, rng)
        assert rest is not None
        ships = sunk + rest
        if sorted(ships) != sorted(board.ships):
            return ships
    return None


@pytest.mark.parametrize("seed,shots,corners", [(1, 10, False), (2, 25, False), (3, 40, False),
                                                (4, 18, True), (5, 33, True), (6, 3, False)])
def test_other_fleet_with_same_answers_gives_same_shot(seed, shots, corners):
    board, fired, rules = midgame(seed, shots, corners)
    other = another_fleet(board, rules, np.random.default_rng(seed))
    assert other is not None and valid_fleet(other, rules)
    twin = Board(other, rules)
    for x in fired:
        twin.shoot(x)
    assert twin.view == board.view                    # ответы на все выстрелы совпали
    o1, o2 = board.observation(), twin.observation()
    assert o1 == o2
    for level in LEVELS:
        a1 = make_agent(level, samples=300, parity=1)
        a2 = make_agent(level, samples=300, parity=1)
        assert a1.choose(o1, np.random.default_rng(77)) == a2.choose(o2, np.random.default_rng(77)), level
        assert np.array_equal(a1.think(o1, np.random.default_rng(5)), a2.think(o2, np.random.default_rng(5)))


def test_observation_does_not_depend_on_unshot_ships():
    """Корабль, в который ещё не стреляли, сдвинутый на свободное место, наблюдения не меняет."""
    board, fired, rules = midgame(9, 12)
    o = board.observation()
    assert len(o.grid) == 100 and set(o.grid) <= {0, 1, 2, 3}
    assert sum(o.remaining) == 20 - sum(1 for v in o.grid if v == SUNK)
