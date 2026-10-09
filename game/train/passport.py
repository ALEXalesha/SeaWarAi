"""Паспорт ИИ: проверки силы с зёрнами, итог в game/models/seawar-passport.json.

    python -m game.train.passport                  # полный: 10 000 партий на уровень
    python -m game.train.passport --games 200      # быстрый пробный
    python -m game.train.passport --processes 2

Проверки (spec §3):
- shots: сколько выстрелов нужно каждому уровню, чтобы потопить случайный флот (все
  расстановки равновероятны); среднее, медиана, разброс. Партия i - bench.shots_to_sink;
- duel: сильный против среднего, партия целиком, по очереди первым; доля побед сильного;
- placement: сильный и средний стреляют по расстановке ИИ - живёт ли она дольше случайной;
- habits: игрок, который любит края; сильный с привычками (выучены по 30 его партиям) и без.

Каждый исход записан партия за партией: тест пересчитывает первые партии с теми же зёрнами.
Обучения нет - паспорт только меряет. Потоки BLAS - по одному на процесс.
"""
import os

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

from game.ai import bench  # noqa: E402
from game.ai.agents import LEVELS  # noqa: E402
from game.ai.prob import DEFAULT_SAMPLES  # noqa: E402

SEED = 20261010
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "game", "models", "seawar-passport.json")
LOG = os.path.join(ROOT, "runs", "passport.log")
HABIT_GAMES = 30


def job(task):
    """Одна партия любой проверки - для процессов."""
    kind, arg, i = task
    if kind == "shots":
        return bench.shots_to_sink(arg, SEED, i)
    if kind == "duel":
        return bench.duel("strong", "medium", SEED + 1, i)
    if kind == "placement":
        return bench.shots_to_sink(arg, SEED + 2, i, placer="ai")
    if kind == "habits":
        h = bench.learned_habits(SEED + 3, HABIT_GAMES) if arg == "with" else None
        return bench.shots_to_sink("strong", SEED + 4, i, placer="edge", habits=h)
    raise ValueError(kind)


def stats(values):
    v = np.array(values, dtype=float)
    return {"games": len(v), "mean": round(float(v.mean()), 2), "median": float(np.median(v)),
            "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90)),
            "min": int(v.min()), "max": int(v.max()), "stderr": round(float(v.std() / np.sqrt(len(v))), 3)}


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(tasks, pool, label):
    t0 = time.time()
    out = []
    chunk = max(1, len(tasks) // 20)
    for k in range(0, len(tasks), chunk):
        part = tasks[k:k + chunk]
        out += pool.map(job, part) if pool is not None else [job(t) for t in part]
        done = len(out)
        rate = (time.time() - t0) / done
        log(f"{label}: {done}/{len(tasks)}, осталось ~{rate * (len(tasks) - done) / 60:.1f} мин")
    return out, time.time() - t0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Паспорт ИИ морского боя")
    ap.add_argument("--games", type=int, default=10000, help="партий на уровень (выстрелы)")
    ap.add_argument("--duel", type=int, default=1000)
    ap.add_argument("--placement", type=int, default=1000)
    ap.add_argument("--habits", type=int, default=300)
    ap.add_argument("--processes", type=int, default=2)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    pool = None
    if a.processes > 1:
        import multiprocessing as mp
        pool = mp.get_context("spawn").Pool(a.processes)
    started = time.time()
    data = {"note": "Проверки силы ИИ. Пересчёт: python -m game.train.passport",
            "seed": SEED, "samples": DEFAULT_SAMPLES, "rules": "строгие (углами не касаться), без залпа",
            "random_fleet": "все расстановки по правилам почти равновероятны (prob.uniform_fleet)",
            "processes": a.processes, "machine": platform.processor() or platform.machine(), "checks": {}}
    try:
        shots = {}
        for level in LEVELS:
            res, sec = run([("shots", level, i) for i in range(a.games)], pool, f"выстрелы {level}")
            shots[level] = {**stats(res), "seconds": round(sec, 1), "results": res}
        data["checks"]["shots"] = shots
        res, sec = run([("duel", None, i) for i in range(a.duel)], pool, "сильный против среднего")
        res = "".join(res)
        data["checks"]["duel"] = {"games": len(res), "wins": res.count("W"),
                                  "score": round(res.count("W") / max(len(res), 1), 4),
                                  "seconds": round(sec, 1), "results": res}
        place = {}
        for level in ("strong", "medium"):
            r, sec = run([("placement", level, i) for i in range(a.placement)], pool, f"расстановка ИИ, стреляет {level}")
            place[level] = {**stats(r), "random_mean": shots[level]["mean"],
                            "random_mean_same_games": round(float(np.mean(shots[level]["results"][:len(r)])), 2),
                            "seconds": round(sec, 1), "results": r}
        data["checks"]["placement"] = place
        hab = {}
        for arg in ("without", "with"):
            r, sec = run([("habits", arg, i) for i in range(a.habits)], pool, f"привычки {arg}")
            hab[arg] = {**stats(r), "seconds": round(sec, 1), "results": r}
        hab["learned_games"] = HABIT_GAMES
        data["checks"]["habits"] = hab
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    data["seconds_total"] = round(time.time() - started, 1)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    log(f"готово за {data['seconds_total'] / 60:.1f} мин: {a.out}")
    return data


if __name__ == "__main__":
    main()
