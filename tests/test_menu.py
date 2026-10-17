"""Своё стартовое меню, боковая панель боя в его стиле и растянутые настройки (автор 17.10: у
каждой игры меню своё, «боковые меню тоже разнообразить»; настройки - на всю ширину, как
статистика).

Законы:
- окно открывается меню; фон-сонар живёт, пока меню на экране, и стоит на других страницах и на
  паузе вкладки оболочки;
- меню цело (ничего за краем, текст влезает, соседи не налезают) от минимального окна до 4K, в
  обеих темах, на двух языках; сонар не заходит на колонку меню;
- боковая панель боя и расстановка - в стиле меню и целы на всех размерах;
- карточка настроек занимает почти всю ширину страницы;
- поля боя - в цветах меню.
"""
import time

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

from aikit.menu import SIZES, Backdrop, fill_share, layout_problems
from game import APP_NAME, GAME_INFO, create_widget
from game.ui import board as B
from game.ui import menu as M
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
    w.game.change("anim_ms", 0)
    w.game.change("delay_ms", 0)
    yield w
    w.game.shutdown()
    w.close()
    w.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def pump(app, seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.003)


def resize(win, w, h):
    win.resize(max(w, win.minimumWidth()), max(h, win.minimumHeight()))


def test_window_opens_with_the_menu_and_sonar_lives_only_there(app, win):
    g = win.game
    assert g.current_page() == "menu"
    assert isinstance(g.menu, Backdrop) and g.menu.running()
    t0 = g.menu.t
    pump(app, 0.2)
    assert g.menu.t > t0
    g.show_page("stats")
    assert not g.menu.running()
    g.show_page("menu")
    assert g.menu.running()
    g.pause()                          # оболочка спрятала вкладку
    assert not g.menu.running()
    g.resume()
    assert g.menu.running()


def test_menu_has_its_own_style(app, win):
    g = win.game
    assert isinstance(g.menu, M.Sonar)
    css = g.menu.styleSheet()
    assert "Corbel" in css and "border-left" in css and "QFrame#log" in css
    assert g.menu.title.family == "Cambria"
    assert g.menu.play_button.text() == "ИГРАТЬ"


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("lang", ["ru", "en"])
def test_menu_is_whole_at_every_size(app, win, theme, lang):
    g = win.game
    win.ctx.set_theme(theme)
    win.ctx.set_lang(lang)
    for w, h in SIZES:
        resize(win, w, h)
        pump(app, 0.03)
        g.menu.grab()
        assert layout_problems(g.menu) == [], (theme, lang, win.size())
        scope = g.menu.scope_rect()
        assert QRectF(g.menu.rect()).contains(scope), win.size()
        for part in (g.menu.log, g.menu.play_button, g.menu.sub, g.menu.title):
            box = QRectF(part.mapTo(g.menu, part.rect().topLeft()), part.rect().size().toSizeF())
            assert not box.intersects(scope), (part, win.size())


def test_menu_scales_up_on_big_windows(app, win):
    g = win.game
    resize(win, 1280, 800)
    pump(app, 0.03)
    small = (g.menu.play_button.width(), g.menu.title.px)
    resize(win, 3840, 2160)
    pump(app, 0.03)
    assert g.menu.play_button.width() > small[0] * 1.8 and g.menu.title.px > small[1] * 1.8


def test_sonar_glow_follows_the_beam():
    assert M.glow(100, 100) == 1.0
    assert M.glow(100, 160) > M.glow(100, 260) > 0
    assert M.glow(100, 99) == 0.0               # луч ещё не дошёл - отметка погасла
    assert abs(M.sweep_angle(M.SWEEP) - 0.0) < 1e-9


def test_settings_card_stretches_like_stats(app, win):
    g = win.game
    g.show_page("settings")
    for w, h in SIZES:
        resize(win, w, h)
        pump(app, 0.03)
        page = g.settings_page
        assert fill_share(page.box, page) > 0.9, (win.size(), page.box.width(), page.width())


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("lang", ["ru", "en"])
def test_battle_side_panel_in_menu_style_and_whole(app, win, theme, lang):
    g = win.game
    win.ctx.set_theme(theme)
    win.ctx.set_lang(lang)
    pal = M.palette(theme)
    assert "Cambria" in g.play.side.styleSheet() and pal["sonar"] in g.play.side.styleSheet()
    assert pal["bg"] in g.play.styleSheet() and pal["bg"] in g.setup.styleSheet()
    assert B.colors(theme)["water"].name() == pal["water"]
    for salvo, thoughts in ((False, False), (True, True)):
        g.change("salvo", salvo)
        g.start_battle(seed=4, fleet=HAND)
        g.change("show_thoughts", thoughts)
        for w, h in SIZES:
            resize(win, w, h)
            pump(app, 0.03)
            g.play.side.grab()
            assert g.play.body.width() <= g.play.scroll.viewport().width()
            assert layout_problems(g.play.body) == [], (salvo, thoughts, win.size())
    g.change("salvo", False)
    g.change("show_thoughts", False)


def test_setup_page_whole(app, win):
    g = win.game
    g.show_page("setup")
    for w, h in SIZES:
        resize(win, w, h)
        pump(app, 0.03)
        g.setup.grab()
        assert layout_problems(g.setup) == [], win.size()
