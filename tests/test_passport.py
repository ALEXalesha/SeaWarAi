"""Паспорт ИИ пересчитывается: первые партии каждой проверки с теми же зёрнами дают те же
исходы, что записаны в game/models/seawar-passport.json."""
import json
import os

import numpy as np
import pytest

from game.ai import bench
from game.ai.agents import LEVELS
from game.ai.prob import DEFAULT_SAMPLES
from game.train import passport as pp

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def data():
    if not os.path.exists(pp.OUT):
        pytest.skip("паспорт ещё не посчитан")
    with open(pp.OUT, encoding="utf-8") as f:
        return json.load(f)


def test_passport_is_full_and_consistent(data):
    assert data["seed"] == pp.SEED and data["samples"] == DEFAULT_SAMPLES
    shots = data["checks"]["shots"]
    for level in LEVELS:
        s = shots[level]
        assert s["games"] == len(s["results"]) >= 10000
        assert abs(np.mean(s["results"]) - s["mean"]) < 0.01
        assert all(20 <= x <= 100 for x in s["results"])
    assert shots["strong"]["mean"] < shots["medium"]["mean"] < shots["novice"]["mean"]
    duel = data["checks"]["duel"]
    assert duel["wins"] == duel["results"].count("W") and duel["score"] > 0.5


@pytest.mark.parametrize("level", LEVELS)
def test_first_games_recomputed(data, level):
    res = data["checks"]["shots"][level]["results"]
    for i in range(3):
        assert bench.shots_to_sink(level, pp.SEED, i) == res[i], (level, i)


def test_duel_placement_habits_recomputed(data):
    c = data["checks"]
    for i in range(2):
        assert pp.job(("duel", None, i)) == c["duel"]["results"][i]
        assert pp.job(("placement", "strong", i)) == c["placement"]["strong"]["results"][i]
    for arg in ("without", "with"):
        assert pp.job(("habits", arg, 0)) == c["habits"][arg]["results"][0]
