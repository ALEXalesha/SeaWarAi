"""Поле, корабли, касания, расстановка - каждое правило отдельным случаем."""
import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as hs

from game.core.rules import (FLEET, LETTERS, Rules, can_place, cell_name, fleet_problems, halo, is_straight,
                             neighbors, orientation, placements, random_fleet, ship_cells, valid_fleet)

CORNERS = Rules(corners=True)

# Ручная расстановка по правилам: ряды 0, 2, 4, 6 через пустой ряд, в ряду - через клетку.
HAND = [(0, 1, 2, 3), (20, 21, 22), (24, 25, 26), (40, 41), (43, 44), (46, 47), (60,), (62,), (64,), (66,)]


def test_fleet_is_russian():
    assert sorted(FLEET, reverse=True) == [4, 3, 3, 2, 2, 2, 1, 1, 1, 1] and sum(FLEET) == 20


def test_letters_without_short_i():
    assert LETTERS["ru"] == "АБВГДЕЖЗИК" and "Й" not in LETTERS["ru"]
    assert cell_name(0) == "А1" and cell_name(99) == "К10" and cell_name(9) == "К1"
    assert cell_name(90) == "А10" and cell_name(99, "en") == "J10"


@pytest.mark.parametrize("length,count", [(1, 100), (2, 180), (3, 160), (4, 140)])
def test_placements_count_and_unique(length, count):
    ps = placements(length)
    assert len(ps) == count and len(set(ps)) == count
    assert all(is_straight(p) and len(p) == length for p in ps)


def test_ship_cells_bounds():
    assert ship_cells(0, 6, 4, True) == (6, 7, 8, 9)
    assert ship_cells(0, 7, 4, True) is None
    assert ship_cells(6, 0, 4, False) == (60, 70, 80, 90)
    assert ship_cells(7, 0, 4, False) is None
    assert ship_cells(-1, 0, 1, True) is None and ship_cells(0, 10, 1, True) is None
    assert ship_cells(0, 0, 0, True) is None


def test_is_straight_rejects_wrap_gap_diagonal_duplicates():
    assert is_straight((8, 9)) and is_straight((9, 19)) and is_straight((5,))
    assert not is_straight((9, 10))            # с конца строки на начало следующей
    assert not is_straight((0, 2))
    assert not is_straight((0, 11))
    assert not is_straight((3, 3))
    assert not is_straight((99, 100))
    assert not is_straight(())
    assert is_straight((12, 2, 22))            # порядок клеток не важен


def test_orientation():
    assert orientation((3, 4)) and not orientation((3, 13)) and orientation((7,))


@pytest.mark.parametrize("cell,eight,four", [(0, 3, 2), (9, 3, 2), (99, 3, 2), (5, 5, 3), (55, 8, 4), (50, 5, 3)])
def test_neighbors(cell, eight, four):
    assert len(neighbors(cell)) == eight and len(neighbors(cell, corners=True)) == four
    assert cell not in neighbors(cell)


def test_halo_of_ship():
    assert halo((44, 45)) == {33, 34, 35, 36, 43, 44, 45, 46, 53, 54, 55, 56}
    assert halo((44, 45), corners=True) == {34, 35, 43, 44, 45, 46, 54, 55}


def test_can_place_side_corner_overlap_gap():
    base = [(44, 45)]
    assert not can_place(base, (46,)) and not can_place(base, (46,), CORNERS)       # сторона
    assert not can_place(base, (35, 36)) and not can_place(base, (34,), CORNERS)    # сторона сверху
    assert not can_place(base, (56,))                                                # угол
    assert can_place(base, (56,), CORNERS)                                           # угол можно
    assert not can_place(base, (45, 46)) and not can_place(base, (45, 46), CORNERS)  # налезает
    assert can_place(base, (47,)) and can_place(base, (24, 25))                      # через клетку
    assert not can_place(base, (9, 10))                                              # кривой


def test_hand_fleet_valid_and_problems_found():
    assert valid_fleet(HAND) and valid_fleet(HAND, CORNERS)
    assert fleet_problems(HAND[:-1]) == ["состав флота"]
    bad = HAND[:-1] + [(65,)]                 # касается (64,) стороной
    assert any("касаются" in p for p in fleet_problems(bad))
    diag = HAND[:-1] + [(75,)]                # касается (64,) углом
    assert any("касаются" in p for p in fleet_problems(diag))
    assert valid_fleet(diag, CORNERS)
    crooked = HAND[:-2] + [(9, 10), (66,)]
    assert any("кривой" in p for p in fleet_problems(crooked))
    extra = HAND + [(99,)]
    assert "состав флота" in fleet_problems(extra)


@given(hs.integers(0, 2 ** 32 - 1), hs.booleans())
def test_random_fleet_always_valid(seed, corners):
    rules = Rules(corners=corners)
    ships = random_fleet(np.random.default_rng(seed), rules)
    assert valid_fleet(ships, rules)


def test_random_fleet_varies_and_repeats_with_seed():
    a = random_fleet(np.random.default_rng(1))
    b = random_fleet(np.random.default_rng(1))
    c = random_fleet(np.random.default_rng(2))
    assert a == b and a != c
    seen = {tuple(random_fleet(np.random.default_rng(s))) for s in range(50)}
    assert len(seen) == 50


def test_random_fleet_with_corners_can_touch_corners():
    rng = np.random.default_rng(0)
    touched = False
    for _ in range(300):
        ships = random_fleet(rng, CORNERS)
        if not valid_fleet(ships):           # по строгим правилам нельзя - значит углы касаются
            touched = True
            break
    assert touched


def test_small_board_custom_fleet():
    ships = random_fleet(np.random.default_rng(3), Rules(), fleet=(2, 1), size=4)
    assert valid_fleet(ships, Rules(), fleet=(2, 1), size=4)
    with pytest.raises(RuntimeError):
        random_fleet(np.random.default_rng(3), Rules(), fleet=(4, 4, 4, 4), size=4, attempts=20)
