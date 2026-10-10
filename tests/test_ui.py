"""Окно без экрана (Qt offscreen): расстановка мышью, бой, ИИ в потоке, залп, «Мысли ИИ»,
темы, языки, статистика, привычки, остановка за 2 секунды. Ожидания - с тайм-аутом; мышь -
собранными событиями, настоящий курсор не трогается."""
import gc
import os
import time

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

from game import APP_NAME, GAME_INFO, create_widget
from game.ai.agents import make_agent
from game.core.battle import Observation
from game.core.rules import valid_fleet
from game.ui.i18n import EN, RU
from tests.test_rules import HAND


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, tmp_path):
    from aikit.host import make_window
    w, ctx = make_window(GAME_INFO, create_widget, APP_NAME, root=str(tmp_path / "home"))
    w.resize(1280, 800)
    w.show()
    g = w.game
    g.change("anim_ms", 0)
    g.change("delay_ms", 0)
    yield w
    g.shutdown()
    w.close()
    # окно разрушается сразу и в потоке окна, а не когда-нибудь сборщиком мусора
    w.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def wait(app, cond, limit=30.0):
    end = time.time() + limit
    while not cond() and time.time() < end:
        app.processEvents()
        time.sleep(0.002)
    return cond()


def play_out(app, g, limit=120.0, cheat=False):
    """Человека играет бот среднего уровня; cheat - стреляет прямо по кораблям ИИ (для рекорда)."""
    bot = make_agent("medium")
    rng = np.random.default_rng(0)
    end = time.time() + limit
    while not g.session.over:
        assert time.time() < end, "партия не кончилась вовремя"
        s = g.session
        if s.human_turn():
            if cheat:
                target = s.match.boards[1]
                cell = next(x for x in sorted(target.owner) if target.view[x] == 0)
            else:
                cell = bot.choose(s.obs(0), rng)
            g.on_cell(cell)
        assert wait(app, lambda: g.session.over or g.session.human_turn(), 30), "ИИ не ответил"


def mouse(widget, kind, pos, button=Qt.MouseButton.LeftButton):
    types = {"press": QMouseEvent.Type.MouseButtonPress, "move": QMouseEvent.Type.MouseMove,
             "release": QMouseEvent.Type.MouseButtonRelease}
    buttons = Qt.MouseButton.NoButton if kind == "release" else button
    ev = QMouseEvent(types[kind], QPointF(pos), QPointF(pos), button, buttons, Qt.KeyboardModifier.NoModifier)
    {"press": widget.mousePressEvent, "move": widget.mouseMoveEvent, "release": widget.mouseReleaseEvent}[kind](ev)


def test_translations_complete():
    assert set(RU) == set(EN)


def test_setup_drag_from_dock_rotate_and_reject_touching(app, win):
    g = win.game
    g.show_page("setup")
    b = g.setup.board
    b.clear()
    assert not g.setup.battle_button.isEnabled()
    four = b.lengths.index(4)
    slot = b.dock_slots()[four]
    mouse(b, "press", slot.center())
    target = b.cell_rect(22).center()                  # В3: ухватились за первую палубу
    mouse(b, "move", target)
    mouse(b, "release", target)
    assert b.placed[four] == (22, 23, 24, 25)
    assert b.rotate(four) and b.placed[four] == (22, 32, 42, 52)
    one = b.lengths.index(1)
    mouse(b, "press", b.dock_slots()[one].center())
    mouse(b, "move", b.cell_rect(33).center())         # касается корабля сбоку - не встанет
    mouse(b, "release", b.cell_rect(33).center())
    assert b.placed[one] is None
    mouse(b, "press", b.dock_slots()[one].center())
    mouse(b, "release", b.cell_rect(99).center())
    assert b.placed[one] == (99,)
    # перетаскивание корабля по полю и поворот правой кнопкой во время перетаскивания
    mouse(b, "press", b.cell_rect(32).center())
    mouse(b, "press", b.cell_rect(32).center(), Qt.MouseButton.RightButton)
    mouse(b, "release", b.cell_rect(71).center())    # ухвачен за вторую палубу
    assert b.placed[four] == (70, 71, 72, 73)
    g.random_setup()
    assert b.complete() and valid_fleet(b.fleet()) and g.setup.battle_button.isEnabled()
    g.setup.board.clear()
    assert not g.setup.battle_button.isEnabled()


def test_game_vs_ai_to_the_end_records_stats_and_habits_only_at_the_end(app, win):
    g = win.game
    g.change("level", "strong")
    g.start_battle(seed=3, fleet=HAND)
    assert g.current_page() == "play" and g.habits.games == 0
    s = g.session
    assert s.match.boards[0].ships == [tuple(x) for x in HAND]
    play_out(app, g)
    e = g.ctx.stats.entry("strong/classic")
    assert e["games"] == 1 and e["wins"] + e["losses"] == 1
    assert g.habits.games == 1 and g.habits.shot_games == 1
    assert g.play.status.text()


def test_win_sets_record_and_reveals_enemy(app, win):
    g = win.game
    g.change("level", "novice")
    g.start_battle(seed=5, fleet=HAND)
    play_out(app, g, cheat=True)
    assert g.session.outcome_for_human() == "win"
    assert g.records()["novice/classic"] == g.session.match.shots[0] == 20
    assert len(g.play.enemy.ships) == 10                # после боя флот ИИ открыт


def test_ai_receives_only_observation(app, win, monkeypatch):
    g = win.game
    g.change("level", "strong")
    g.change("show_thoughts", True)
    seen = []
    orig_move, orig_th = g.ai.request_move, g.ai.request_thoughts

    def spy_move(token, obs, *a, **kw):
        seen.append(obs)
        return orig_move(token, obs, *a, **kw)

    def spy_th(token, obs, *a, **kw):
        seen.append(obs)
        return orig_th(token, obs, *a, **kw)
    monkeypatch.setattr(g.ai, "request_move", spy_move)
    monkeypatch.setattr(g.ai, "request_thoughts", spy_th)
    g.start_battle(seed=8, fleet=HAND)
    play_out(app, g)
    assert seen and all(type(o) is Observation for o in seen)
    g.change("show_thoughts", False)


def test_thoughts_heat_on_own_board(app, win):
    g = win.game
    g.change("level", "strong")
    g.change("show_thoughts", True)
    g.start_battle(seed=2, fleet=HAND)
    assert wait(app, lambda: g.session.human_turn() and g.play.own.heat is not None, 30)
    heat = np.asarray(g.play.own.heat)
    assert heat.shape == (100,) and heat.max() > 0
    assert g.play.enemy.heat is None                    # чужое поле без подсказок
    assert g.play.best.isVisible() and g.play.best.text()
    g.change("show_thoughts", False)
    assert g.play.own.heat is None


def test_salvo_gives_shots_by_ships_afloat(app, win):
    g = win.game
    assert g.settings["salvo"] is False                  # классические правила по умолчанию
    assert not hasattr(g.menu, "shots_buttons")         # залп - только в настройках
    g.show_page("settings")
    g.settings_page.salvo_box.click()
    assert g.settings["salvo"] is True
    g.change("level", "novice")
    g.start_battle(seed=4, fleet=HAND)       # чётное зерно - первым ходит человек
    s = g.session
    assert s.human_turn() and s.match.shots_left == 10
    misses = [x for x in range(100) if x not in s.match.boards[1].owner][:10]
    for k, x in enumerate(misses):
        assert s.human_turn()
        g.on_cell(x)
    assert not s.human_turn() or s.over
    assert wait(app, lambda: s.human_turn() or s.over, 30)
    assert s.match.shots[1] == 10 or s.over
    g.change("salvo", False)


def test_demo_plays_itself_without_stats(app, win):
    g = win.game
    g.change("mode", "demo")
    g.change("level", "medium")
    g.play_clicked()
    assert g.current_page() == "play"
    assert wait(app, lambda: g.session.over, 60)
    assert len(g.play.own.ships) == 10 and g.ctx.stats.totals()["games"] == 0
    g.change("mode", "play")


def test_language_and_theme_switch_on_the_fly(app, win):
    g = win.game
    g.start_battle(seed=1, fleet=HAND)
    g.ctx.set_lang("en")
    assert g.menu.play_button.text() == "Play" and g.play.own.title == "Your fleet"
    texts = [w.text() for w in win.findChildren(QLabel)]
    assert not any(t in RU for t in texts if t)          # нигде не торчит ключ вместо текста
    g.ctx.set_theme("light")
    assert g.play.own.c["water"] != g.play.own.c["ship"]
    win.grab()
    g.ctx.set_lang("ru")
    g.ctx.set_theme("dark")


def test_corners_option_changes_setup_rules(app, win):
    g = win.game
    g.change("corners", True)
    g.show_page("setup")
    assert g.setup.board.rules.corners
    assert "углами можно" in g.setup.hint.text()
    g.change("corners", False)


def test_habits_reset_from_settings(app, win):
    g = win.game
    g.habits.record_fleet(HAND)
    g.show_page("settings")
    assert g.settings_page.habits_button.isEnabled()
    g.settings_page.habits_button.click()
    assert g.habits.games == 0 and not g.settings_page.habits_button.isEnabled()


def test_stats_page_shows_tables(app, win):
    g = win.game
    g.show_page("stats")
    assert g.stats.table.rowCount() == 6


def test_shutdown_within_two_seconds_while_ai_thinks(app, win):
    g = win.game
    g.change("level", "strong")
    g.change("mode", "demo")
    g.change("delay_ms", 0)
    g.play_clicked()
    wait(app, lambda: g.ai.busy(), 5)
    t0 = time.time()
    assert g.shutdown()
    assert time.time() - t0 < 2.0
    g.change("mode", "play")


def test_window_min_size(app, win):
    assert win.minimumWidth() >= 900 and win.minimumHeight() >= 620
    win.resize(900, 700)
    app.processEvents()
    g = win.game
    g.start_battle(seed=1, fleet=HAND)
    app.processEvents()
    _, _, cell = g.play.own.geometry_()
    assert cell >= 20


def gc_state():
    return gc.get_freeze_count(), gc.isenabled(), gc.get_threshold()


def test_widget_leaves_garbage_collector_alone(app, tmp_path):
    """Игра в оболочке не трогает сборщик мусора: gc.freeze навсегда оставил бы в памяти и
    объекты оболочки (урок DurakAi 0.9.0)."""
    from aikit.host import make_window
    before = gc_state()
    w, _ = make_window(GAME_INFO, create_widget, APP_NAME, root=str(tmp_path / "gc"))
    w.game.start_battle(seed=1, fleet=HAND)
    assert gc_state() == before
    w.game.shutdown()
    w.close()


def test_game_code_never_touches_gc():
    import ast
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad = []
    for top in ("game", "aikit"):
        for folder, _, files in os.walk(os.path.join(root, top)):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(folder, name)
                for node in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
                    if (isinstance(node, ast.Attribute) and node.attr in ("freeze", "unfreeze", "disable", "set_threshold")
                            and isinstance(node.value, ast.Name) and node.value.id == "gc"):
                        bad.append(f"{os.path.relpath(path, root)}:{node.lineno} gc.{node.attr}")
    assert not bad, bad


def test_buttons_start_new_random_games(app, win):
    """Кнопка «В бой» и «Новая партия» - каждый раз новая партия, а не зерно False = 0."""
    g = win.game
    g.show_page("setup")
    g.random_setup()
    seeds = set()
    for _ in range(4):
        g.setup.battle_button.click()
        seeds.add(g.session.seed)
        g.show_page("setup")
    assert len(seeds) == 4 and False not in seeds


def test_pause_stops_everything_and_resume_continues(app, win):
    g = win.game
    g.change("anim_ms", 200)
    g.change("mode", "demo")
    g.change("level", "medium")
    g.play_clicked()
    shots = lambda: sum(g.session.match.shots)  # noqa: E731
    assert wait(app, lambda: shots() >= 4, 30)
    g.pause()
    g.pause()                                    # второй раз - ничего не ломает
    n = shots()
    assert not g.timer.isActive() and not g.play.own.timer.isActive() and not g.play.enemy.timer.isActive()
    g.change("show_thoughts", True)              # перерисовка скрытой вкладки не будит ИИ
    g.ctx.set_lang("en")
    end = time.time() + 0.8
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)
    assert shots() == n and not g.timer.isActive()
    g.ctx.set_lang("ru")
    g.change("show_thoughts", False)
    g.resume()
    g.resume()
    g.change("anim_ms", 0)
    assert wait(app, lambda: shots() >= n + 4, 30)
    g.change("mode", "play")


def test_pause_on_human_turn_ignores_clicks(app, win):
    g = win.game
    g.change("level", "novice")
    g.start_battle(seed=2, fleet=HAND)           # чётное зерно - первым ходит человек
    s = g.session
    assert s.human_turn()
    g.pause()
    g.on_cell(55)
    assert s.match.shots[0] == 0
    g.resume()
    g.on_cell(55)
    assert s.match.shots[0] == 1


def test_thread_that_ignores_stop_survives_widget_destruction(app):
    """Поток, не успевший остановиться за shutdown(), уходит в сироты: окно разрушается,
    а поток дорабатывает сам. Разрушение работающего QThread - qFatal и падение программы
    (так упал CI на Gitea, когда в окне перестал быть gc.freeze)."""
    import threading as th
    from PySide6.QtCore import QCoreApplication, QEvent
    from game.ui import ai_thread
    ctl = ai_thread.AiController()
    release = th.Event()
    ctl._start(1, "move", lambda: release.wait(5) and None)
    assert ctl.busy()
    assert ctl.shutdown(100) is False                 # не успел - и честно сказал
    assert not ctl.jobs and len(ai_thread._ORPHANS) == 1
    ctl.deleteLater()
    del ctl
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    release.set()
    assert wait(app, lambda: not ai_thread._ORPHANS, 5)


def test_finished_ai_threads_are_deleted(app, win):
    from PySide6.QtCore import QCoreApplication, QEvent, QThread
    from game.ui.ai_thread import _Job
    g = win.game
    g.change("mode", "demo")
    g.change("level", "novice")
    g.play_clicked()
    assert wait(app, lambda: g.session.over, 60)
    assert wait(app, lambda: not g.ai.jobs, 5)        # список чистит сам сигнал finished
    for _ in range(5):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    assert not g.ai.findChildren(QThread)
    assert sum(isinstance(o, _Job) for o in gc.get_objects()) <= 1
    g.change("mode", "play")
