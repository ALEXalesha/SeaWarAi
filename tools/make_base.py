"""Частота каждой клетки для каждой длины корабля при равновероятной расстановке флота
(пустое поле, все расстановки по правилам равновероятны). Нужна привычкам игрока как
точка отсчёта и расстановке ИИ как карта «куда стреляют первым».

    python tools/make_base.py        # пишет game/models/base_frequency.json

Считается выборкой prob.mc_map: 40 частей по 5000, зерно постоянное.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")

import numpy as np  # noqa: E402

from game.ai.prob import mc_map  # noqa: E402
from game.core.battle import Observation  # noqa: E402
from game.core.rules import FLEET  # noqa: E402

PARTS, PER = 40, 5000
OUT = os.path.join(ROOT, "game", "models", "base_frequency.json")


def compute(corners, parts=PARTS, per=PER, seed=20261009):
    obs = Observation(tuple([0] * 100), tuple(sorted(FLEET, reverse=True)), corners)
    rng = np.random.default_rng([seed, int(corners)])
    acc = {L: np.zeros(100) for L in set(FLEET)}
    for _ in range(parts):
        _, _, by = mc_map(obs, rng, per, by_length=True)
        for L in acc:
            acc[L] += by[L] / parts
    return acc


def main():
    data = {"note": "доля партий, в которых корабль длины L стоит в клетке, при равновероятной расстановке",
            "samples": PARTS * PER}
    for corners in (False, True):
        acc = compute(corners)
        data["corners" if corners else "strict"] = {str(L): [round(float(v), 5) for v in acc[L]] for L in sorted(acc)}
        print("corners" if corners else "strict", {L: round(float(acc[L].sum()), 3) for L in sorted(acc)})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()
