"""Выстрелы, автоотметка вокруг потопленного, очередь хода, залп, победа."""
import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as hs

from game.core.battle import HIT, MISS, SUNK, UNKNOWN, Board, Match
from game.core.rules import FLEET, Rules, random_fleet
from tests.test_rules import HAND

OTHER = random_fleet(np.random.default_rng(5))


def test_miss_hit_sunk_and_auto_marks():
    b = Board(HAND)
    s = b.shoot(99)
    assert s.result == "miss" and b.view[99] == MISS and not s.auto
    s = b.shoot(40)
    assert s.result == "hit" and b.view[40] == HIT
    s = b.shoot(41)
    assert s.result == "sunk" and s.ship == (40, 41)
    assert b.view[40] == SUNK and b.view[41] == SUNK
    assert set(s.auto) == {30, 31, 32, 42, 50, 51, 52}
    assert all(b.view[x] == MISS for x in s.auto) and b.auto == set(s.auto)
    assert b.remaining() == (4, 3, 3, 2, 2, 1, 1, 1, 1)


def test_auto_marks_only_sides_when_corners_allowed():
    b = Board(HAND, Rules(corners=True))
    b.shoot(40)
    s = b.shoot(41)
    assert set(s.auto) == {30, 31, 42, 50, 51}


def test_auto_marks_skip_already_shot_cells():
    b = Board(HAND)
    b.shoot(51)
    s = b.shoot(60)
    assert s.result == "sunk" and 51 not in s.auto and set(s.auto) == {50, 61, 70, 71}


def test_single_deck_sunk_at_once_and_repeat_shot_rejected():
    b = Board(HAND)
    assert b.shoot(66).result == "sunk"
    with pytest.raises(ValueError):
        b.shoot(66)
    with pytest.raises(ValueError):
        b.shoot(67)                 # отмечена сама - стрелять туда уже нельзя
    with pytest.raises(ValueError):
        b.shoot(100)
    with pytest.raises(ValueError):
        b.shoot(-1)


def test_hit_keeps_turn_miss_passes():
    m = Match([HAND, OTHER])
    assert m.turn == 0 and m.shots_left == 1
    m.fire(next(x for x in range(100) if x in m.boards[1].owner))
    assert m.turn == 0
    m.fire(next(x for x in m.legal() if x not in m.boards[1].owner))
    assert m.turn == 1
    m.fire(99)                      # мимо HAND
    assert m.turn == 0 and m.shots == [2, 1]


def test_sunk_keeps_turn_too():
    m = Match([HAND, OTHER], first=1)
    assert m.fire(66).result == "sunk" and m.turn == 1


def test_win_and_no_shots_after():
    m = Match([HAND, OTHER])
    targets = sorted(m.boards[1].owner)
    for x in targets:
        assert m.turn == 0 and not m.over
        m.fire(x)
    assert m.over and m.winner == 0 and m.shots[0] == 20 and m.legal() == []
    with pytest.raises(ValueError):
        m.fire(next(i for i, v in enumerate(m.boards[1].view) if v == UNKNOWN))


def test_salvo_shots_equal_ships_afloat_and_no_bonus_for_hits():
    m = Match([HAND, OTHER], Rules(salvo=True))
    assert m.shots_left == 10
    own = sorted(m.boards[1].owner)
    for x in own[:9]:               # девять попаданий подряд - ход всё равно кончается после 10 выстрелов
        m.fire(x)
        assert m.turn == 0
    m.fire(own[9])
    afloat = len(m.boards[1].remaining())
    assert m.turn == 1 and m.shots_left == afloat < 10    # у соперника часть флота уже потоплена
    for x in (66, 64, 62):          # соперник топит три моих однопалубных
        m.fire(x)
    while m.turn == 1:
        m.fire(next(c for c in range(100) if m.boards[0].view[c] == UNKNOWN and c not in m.boards[0].owner))
    assert m.shots[1] == afloat and m.shots_left == 7


def test_salvo_win_mid_turn():
    m = Match([HAND, [(0, 1, 2, 3)]], Rules(salvo=True))
    m.boards[1] = Board([(0, 1, 2, 3)], Rules(salvo=True))
    for x in (0, 1, 2, 3):
        m.fire(x)
    assert m.winner == 0


def test_observation_has_no_fleet():
    b = Board(HAND)
    b.shoot(40)
    o = b.observation()
    assert o.grid[40] == HIT and o.hits() == [40] and len(o.unknown()) == 99
    assert o.remaining == tuple(sorted(FLEET, reverse=True))
    assert set(vars(o)) == {"grid", "remaining", "corners", "size"}


@given(hs.integers(0, 2 ** 32 - 1), hs.booleans(), hs.booleans())
def test_random_games_keep_invariants(seed, corners, salvo):
    rules = Rules(corners=corners, salvo=salvo)
    rng = np.random.default_rng(seed)
    m = Match([random_fleet(rng, rules), random_fleet(rng, rules)], rules, first=seed % 2)
    turns = 0
    while not m.over:
        p, left = m.turn, m.shots_left
        legal = m.legal()
        cell = legal[int(rng.integers(len(legal)))]
        shot = m.fire(cell)
        if m.over:
            break
        if salvo:
            assert (m.turn != p) == (left == 1)
        else:
            assert (m.turn != p) == (shot.result == "miss")
        turns += 1
        assert turns < 400
    w = m.winner
    board = m.boards[1 - w]
    assert board.all_sunk() and board.remaining() == ()
    assert sum(v == SUNK for v in board.view) == 20
    loser_view = m.boards[w].view
    assert sum(v in (HIT, SUNK) for v in loser_view) < 20
    assert m.shots[w] == sum(v != UNKNOWN for v in board.view) - len(board.auto)
