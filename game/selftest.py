"""Самопроверка без экрана: python main.py --selftest итог.txt.

Нужна прежде всего собранному exe: он без консоли, поэтому итог пишется в файл. Данные
игрока - во временной папке, его статистика не трогается. Проверяется: правила (случайные
партии), окно - ИИ отвечает на выстрелы бота, который играет за человека через окно.
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

        from PySide6.QtWidgets import QApplication

        from aikit.host import make_window
        from game import APP_NAME, GAME_INFO, create_widget
        from game.ai.agents import make_agent
        from game.ai.prob import uniform_fleet

        app = QApplication.instance() or QApplication([])
        window, ctx = make_window(GAME_INFO, create_widget, APP_NAME, root=home)
        window.show()
        g = window.game
        g.change("anim_ms", 0)
        g.change("delay_ms", 0)
        for level, thoughts in (("strong", True), ("medium", False)):
            g.change("level", level)
            g.change("show_thoughts", thoughts)
            g.start_battle(seed=7, fleet=uniform_fleet(np.random.default_rng(3)))
            bot = make_agent("medium")
            t0 = time.time()
            while not g.session.over:
                s = g.session
                if s.human_turn():
                    g.on_cell(bot.choose(s.obs(0), rng))
                end = time.time() + 30
                while g.session.ai_turn() and time.time() < end:
                    app.processEvents()
                    time.sleep(0.002)
                if g.session.ai_turn():
                    raise RuntimeError("ИИ не ответил за 30 с")
                if time.time() - t0 > 180:
                    raise RuntimeError("партия идёт дольше 3 минут")
            image = window.grab().toImage()
            if image.isNull() or image.width() < 300:
                raise RuntimeError("окно не нарисовалось")
            m = g.session.match
            lines.append(f"ИИ {level}: выстрелов бот {m.shots[0]}, ИИ {m.shots[1]}, итог «{g.play.status.text()}», "
                         f"кадр {image.width()}x{image.height()}, {time.time() - t0:.2f} с")
        t0 = time.time()
        window.close()
        app.processEvents()
        lines.append(f"окно закрыто за {time.time() - t0:.2f} с")
        lines.append("ИТОГ: работает")
    except Exception:  # noqa: BLE001 - любая ошибка должна попасть в файл
        lines.append("ИТОГ: ошибка")
        lines.append(traceback.format_exc())
        code = 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return code
