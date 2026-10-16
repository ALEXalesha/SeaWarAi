"""Журнал партий для графиков: битые данные, номера, ряды графиков."""
import json

import pytest

from aikit import gamelog


def g(n, outcome, level="novice", **kw):
    return {"n": n, "level": level, "outcome": outcome, **kw}


def test_broken_file_gives_empty_log(tmp_path):
    for text in ("", "{", "[]", '{"games": 5}', '"x"'):
        path = tmp_path / "games.json"
        path.write_text(text, encoding="utf-8")
        log = gamelog.GameLog(path)
        assert log.games == [] and log.next == 1


def test_bad_records_and_fields_are_dropped(tmp_path):
    path = tmp_path / "games.json"
    path.write_text(json.dumps({"next": 3, "games": [
        g(1, "win", moves=10, note="x" * 100, nested={"a": 1}, bad=None),
        {"n": 2, "level": "novice", "outcome": "maybe"},
        {"n": 0, "level": "novice", "outcome": "win"},
        {"n": 2, "level": "", "outcome": "win"},
        g(2, "loss", moves=True, score=1.5),
    ]}), encoding="utf-8")
    log = gamelog.GameLog(path)
    assert [x["n"] for x in log.games] == [1, 2]
    assert log.games[0] == {"n": 1, "level": "novice", "outcome": "win", "moves": 10}
    assert log.games[1]["score"] == 1.5
    assert log.next == 3


def test_numbers_continue_and_survive_reload(tmp_path):
    path = tmp_path / "games.json"
    log = gamelog.GameLog(path)
    a = log.record({"level": "strong", "outcome": "win", "moves": 30})
    b = log.record({"level": "strong", "outcome": "draw", "moves": 31, "n": 999})
    assert (a["n"], b["n"]) == (1, 2)
    again = gamelog.GameLog(path)
    assert [x["n"] for x in again.games] == [1, 2]
    assert again.record({"level": "novice", "outcome": "loss"})["n"] == 3


def test_record_without_level_or_outcome_refuses():
    log = gamelog.GameLog()
    with pytest.raises(ValueError):
        log.record({"outcome": "win"})
    with pytest.raises(ValueError):
        log.record({"level": "novice", "outcome": "lost"})


def test_cap_keeps_last_games_and_numbering(tmp_path):
    log = gamelog.GameLog(tmp_path / "g.json", cap=5)
    for _ in range(8):
        log.record({"level": "novice", "outcome": "win"})
    assert [x["n"] for x in log.games] == [4, 5, 6, 7, 8]
    assert gamelog.GameLog(tmp_path / "g.json", cap=5).next == 9


def test_rolling_share_counts_draw_as_half_and_slides():
    games = [g(1, "win"), g(2, "draw"), g(3, "loss"), g(4, "win")]
    assert gamelog.rolling_share(games, None) == [(1, 1.0), (2, 0.75), (3, 0.5), (4, 0.625)]
    assert gamelog.rolling_share(games, 2) == [(1, 1.0), (2, 0.75), (3, 0.25), (4, 0.5)]


def test_by_level_keeps_given_order_and_hides_empty_levels_and_draws():
    games = [g(1, "win", "strong"), g(2, "loss", "medium"), g(3, "win", "medium"), g(4, "loss", "strong")]
    groups, series = gamelog.by_level(games, ("novice", "medium", "strong"))
    assert groups == ["medium", "strong"]
    assert [o for o, _ in series] == ["win", "loss"]
    assert series[0][1] == [0.5, 0.5]
    groups, series = gamelog.by_level(games + [g(5, "draw", "novice")], ("novice", "medium", "strong"))
    assert groups == ["novice", "medium", "strong"] and [o for o, _ in series] == ["win", "draw", "loss"]


def test_series_best_curve_and_streaks():
    games = [g(1, "win", score=5), g(2, "win", score=3), g(3, "loss", score=8), g(4, "win"), g(5, "win", score=1)]
    assert gamelog.series(games, "score") == [(1, 5), (2, 3), (3, 8), (5, 1)]
    assert gamelog.best_curve(games, "score") == [(1, 5), (2, 5), (3, 8), (5, 8)]
    assert gamelog.best_curve(games, "score", "min") == [(1, 5), (2, 3), (3, 3), (5, 1)]
    now, top = gamelog.streaks(games)
    assert now == [(1, 1), (2, 2), (3, 0), (4, 1), (5, 2)]
    assert top == [(1, 1), (2, 2), (3, 2), (4, 2), (5, 2)]


def test_mean_by_level():
    games = [g(1, "win", "strong", moves=10), g(2, "win", "strong", moves=20), g(3, "loss", "novice")]
    assert gamelog.mean_by_level(games, "moves", ("novice", "strong")) == (["strong"], [15.0])
