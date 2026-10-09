"""Самопроверка без экрана: python main.py --selftest итог.txt.

Нужна прежде всего собранному exe: он без консоли, поэтому итог пишется в файл. Данные
игрока - во временной папке, его статистика не трогается.
"""
import os
import tempfile
import time
import traceback


def selftest(out_path):
    lines = []
    code = 0
    try:
        from aikit import offscreen
        offscreen.setup(force=True)
        home = tempfile.mkdtemp(prefix="seawarai-selftest-")
        os.environ["SEAWARAI_HOME"] = home
        import numpy as np

        import aikit
        from game.core.battle import Match
        from game.core.rules import Rules, random_fleet, valid_fleet
        from game.version import VERSION

        lines.append(f"SeaWarAi {VERSION} самопроверка (aikit {aikit.__version__})")
        lines.append(f"собранная версия: {'да' if aikit.frozen() else 'нет'}")
        started = time.time()
        rng = np.random.default_rng(1)
        for i in range(200):
            rules = Rules(corners=i % 2 == 1, salvo=i % 4 >= 2)
            fleets = [random_fleet(rng, rules), random_fleet(rng, rules)]
            if not all(valid_fleet(f, rules) for f in fleets):
                raise RuntimeError("случайная расстановка не по правилам")
            m = Match(fleets, rules, first=i % 2)
            while not m.over:
                legal = m.legal()
                m.fire(legal[int(rng.integers(len(legal)))])
        lines.append(f"правила: 200 случайных партий без нарушений, {time.time() - started:.2f} с")
        lines.append("ИТОГ: работает")
    except Exception:  # noqa: BLE001 - любая ошибка должна попасть в файл
        lines.append("ИТОГ: ошибка")
        lines.append(traceback.format_exc())
        code = 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return code
