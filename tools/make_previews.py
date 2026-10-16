"""Кадры для README: окно без экрана в нескольких состояниях.

    python tools/make_previews.py [папка]     # по умолчанию docs/
"""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from aikit import offscreen  # noqa: E402

offscreen.setup(force=True)
os.environ["SEAWARAI_HOME"] = tempfile.mkdtemp(prefix="seawarai-previews-")


def settle(app, ms=300):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def play_until(app, g, shots, bot, rng):
    """Бот за человека стреляет, пока у него не будет shots выстрелов (ИИ отвечает)."""
    while not g.session.over and g.session.match.shots[0] < shots:
        s = g.session
        if s.human_turn():
            g.on_cell(bot.choose(s.obs(0), rng))
        end = time.time() + 30
        while g.session.ai_turn() and time.time() < end:
            app.processEvents()
            time.sleep(0.002)
    end = time.time() + 30                      # «Мысли ИИ» досчитываются
    while g.settings["show_thoughts"] and g.play.own.heat is None and time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def sample_games(g):
    """Журнал партий для кадра графиков: 16 партий против разных уровней (как в статистике -
    и в stats.json, и в games.json)."""
    import random
    rng = random.Random(7)
    for k in range(16):
        level = ("novice", "medium", "strong")[k % 3]
        won = rng.random() < (0.8, 0.55, 0.35)[k % 3]
        shots = rng.randint(45, 75) if won else rng.randint(60, 95)
        game = {"level": level, "variant": "classic", "outcome": "win" if won else "loss", "shots": shots}
        if won:
            game["win_shots"] = shots
        g.ctx.stats.record(f"{level}/classic", game["outcome"])
        g.history.record(game)


def main(out):
    import numpy as np
    from PySide6.QtWidgets import QApplication

    from aikit.host import make_window
    from game import APP_NAME, GAME_INFO, create_widget
    from game.ai.agents import make_agent
    from game.ai.prob import uniform_fleet

    os.makedirs(out, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window, ctx = make_window(GAME_INFO, create_widget, APP_NAME, root=os.environ["SEAWARAI_HOME"])
    window.resize(1280, 800)
    window.show()
    g = window.game
    shots = []
    for theme_name in ("dark", "light"):
        ctx.set_theme(theme_name)
        suffix = "" if theme_name == "dark" else "_light"
        g.change("anim_ms", 0)
        g.change("delay_ms", 0)
        g.change("level", "strong")
        g.show_page("menu")
        settle(app)
        shots.append((window.grab(), f"preview_menu{suffix}.png"))
        g.show_page("setup")
        g.setup.board.set_fleet(uniform_fleet(np.random.default_rng(21))[:7])
        settle(app)
        shots.append((window.grab(), f"preview_setup{suffix}.png"))
        g.change("show_thoughts", True)
        g.start_battle(seed=12, fleet=uniform_fleet(np.random.default_rng(5)))
        play_until(app, g, 24, make_agent("medium"), np.random.default_rng(1))
        settle(app)
        shots.append((window.grab(), f"preview_battle{suffix}.png"))
        g.change("show_thoughts", False)
        if not g.history.games:
            sample_games(g)
        g.show_page("stats")
        settle(app)
        shots.append((window.grab(), f"preview_stats{suffix}.png"))
        card = g.stats.charts.parentWidget()
        h = card.heightForWidth(1180)
        card.resize(1180, h if h > 0 else card.sizeHint().height())
        shots.append((card.grab(), f"preview_charts{suffix}.png"))
    ctx.set_theme("dark")
    window.resize(1280, 720)                    # для списка игр ИИ-Игротеки: 16:9
    g.change("show_thoughts", True)
    g.start_battle(seed=12, fleet=uniform_fleet(np.random.default_rng(5)))
    play_until(app, g, 24, make_agent("medium"), np.random.default_rng(1))
    settle(app)
    shots.append((window.grab(), "preview.png"))
    g.change("show_thoughts", False)
    for pix, name in shots:
        pix.save(os.path.join(out, name))
        print(name)
    g.shutdown()
    window.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs"))
