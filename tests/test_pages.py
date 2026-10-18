"""Настройки и статистика в стиле «штурманской рубки» (aikit.skin, автор 17.10) и находки проверки
17.10: подписи над полем целы на 2560 и 4K, брошенный бой - вопрос и поражение, «Продолжить бой»
в меню, заголовок панели не срезан снизу."""
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QFontMetricsF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from aikit.menu import SIZES, layout_problems
from aikit.skin import DEFAULT, SkinPage, difference, page_problems
from game import APP_NAME, GAME_INFO, create_widget
from game.ui.skin import SKIN
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
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def pump(app, seconds=0.05, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until is not None and until():
            return True
        time.sleep(0.003)
    return until() if until is not None else True


def battle(app, g, shots=1):
    """Бой человека с ИИ, человек сделал shots выстрелов (ИИ отвечает сам)."""
    g.start_battle(seed=1, fleet=HAND)
    s = g.session
    done = 0
    for cell in range(100):
        if done >= shots:
            break
        assert pump(app, 20, lambda: g.session.human_turn() or g.session.over)
        if cell in s.match.legal() and s.human_turn():
            g.on_cell(cell)
            done += 1
    return s


def test_pages_are_skin_pages_unlike_aikit(app, win):
    g = win.game
    assert isinstance(g.stats, SkinPage) and isinstance(g.settings_page, SkinPage)
    assert g.stats.skin is SKIN and all(c.skin is SKIN for c in g.stats.charts.charts())
    assert SKIN.signature() != DEFAULT.signature()
    for theme in ("dark", "light"):
        for name in ("stats", "settings"):
            g.show_page(name)
            pump(app)
            page = g.pages[name]
            page.set_theme(theme)
            own = page.grab()
            page.skin = DEFAULT
            page.set_theme(theme)
            plain = page.grab()
            page.skin = SKIN
            page.set_theme(theme)
            # ночное море рубки по яркости близко к тёмной теме aikit (отличают оттенок, сетка,
            # таблички, шрифты) - порог ниже, чем у Сапёра
            assert difference(own, plain) > 0.15, (theme, name, difference(own, plain))


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("lang", ["ru", "en"])
def test_pages_clean_from_narrow_to_4k(app, win, theme, lang):
    g = win.game
    win.ctx.set_theme(theme)
    win.ctx.set_lang(lang)
    for name in ("stats", "settings"):
        g.show_page(name)
        for w, h in SIZES:
            win.resize(max(w, win.minimumWidth()), max(h, win.minimumHeight()))
            pump(app, 0.03)
            assert page_problems(g.pages[name]) == [], (name, w, h)


def test_settings_groups(app, win):
    g = win.game
    g.show_page("settings")
    sp = g.settings_page
    assert [x.text() for x in sp.box.groups] == [g.t("group_view").upper(), g.t("group_battle").upper()]
    assert set(sp.rows) == {"theme", "language", "volume", "anim", "delay", "salvo_rule", "habits"}


@pytest.mark.parametrize("size", [(1280, 800), (1920, 1080), (2560, 1440), (3840, 2160)])
def test_board_labels_whole_and_off_the_grid(app, win, size):
    """Проверка 17.10: на 2560x1440 низ букв А..К срезан краем поля, на 4K - половина букв и «1» у «10»."""
    g = win.game
    g.start_battle(seed=1, fleet=HAND)
    win.resize(*size)
    pump(app, 0.1)
    for board in (g.play.own, g.play.enemy, g.setup.board):
        board.grab()
        x0, y0, cell = board.geometry_()
        grid = board.cell_rect(0).united(board.cell_rect(99))
        fm = QFontMetricsF(board.font())
        f = board.font()
        f.setPixelSize(max(10, int(cell * 0.36)))
        fm = QFontMetricsF(f)
        for text, box in board.label_boxes:
            assert board.rect().contains(box.toRect()), (text, box)
            assert not box.intersects(grid.adjusted(1, 1, -1, -1)), (text, box)
            assert fm.horizontalAdvance(text) <= box.width() + 0.5, (text, box.width())
            assert fm.height() <= box.height() + 0.5, (text, box.height(), fm.height())


def test_side_heading_not_cut(app, win):
    """Проверка 17.10: «Морской бой · Средний · По одному» во второй строке срезано снизу
    («одномv»): у Cambria в Qt нижний вынос 0. Теперь Constantia и закон хвостов букв aikit."""
    g = win.game
    battle(app, g, 0)
    for w, h in ((900, 700), (1100, 760), (1280, 800)):
        win.resize(w, h)
        pump(app, 0.05)
        assert layout_problems(g.play.body) == [], (w, h)
    fm = QFontMetricsF(g.play.heading.font())
    assert fm.descent() >= 2


def test_menu_offers_to_continue_the_battle(app, win):
    g = win.game
    battle(app, g, 1)
    QTest.keyClick(g.play, Qt.Key.Key_Escape)
    pump(app)
    assert g.current_page() == "menu"
    assert g.menu.play_button.text() == g.t("continue_battle").upper()
    assert g.menu.new_button.isVisibleTo(g.menu)
    s = g.session
    g.menu.play_button.click()
    assert g.current_page() == "play" and g.session is s
    assert g.ctx.stats.totals()["games"] == 0


def test_give_up_from_menu_counts_a_loss(app, win):
    g = win.game
    battle(app, g, 1)
    g.show_page("menu")
    g.menu.new_button.click()
    assert g.ctx.stats.totals()["games"] == 1 and g.ctx.stats.totals()["wins"] == 0
    assert g.history.games[-1]["outcome"] == "loss" and g.history.games[-1].get("abandoned") == 1
    assert g.current_page() == "setup"


def test_n_mid_battle_asks_first(app, win):
    """Проверка 17.10: N посреди боя сразу бросал бой. Теперь первый раз - вопрос, второй - сдаться."""
    g = win.game
    s = battle(app, g, 1)
    g.play.setFocus()
    g.new_clicked()
    assert g.session is s and g.play.substatus.text() == g.t("confirm_new")
    assert g.play.again_button.text() == g.t("give_up_new")
    assert g.ctx.stats.totals()["games"] == 0
    g.new_clicked()
    assert g.ctx.stats.totals()["games"] == 1 and g.current_page() == "setup"


def test_shot_after_question_cancels_it(app, win):
    g = win.game
    s = battle(app, g, 1)
    g.new_clicked()
    assert pump(app, 20, lambda: s.human_turn() or s.over)
    cell = next(c for c in range(100) if c in s.match.legal())
    g.on_cell(cell)
    assert not g.confirm_new and g.play.again_button.text() == g.t("again")


def test_battle_without_shots_is_not_counted(app, win):
    g = win.game
    g.start_battle(seed=1, fleet=HAND)
    g.show_page("menu")
    g.menu.new_button.click()
    assert g.ctx.stats.totals()["games"] == 0


def test_n_on_stats_or_menu_does_nothing_mid_battle(app, win):
    g = win.game
    s = battle(app, g, 1)
    for page in ("stats", "settings", "menu"):
        g.show_page(page)
        g.new_clicked()
        assert g.session is s and g.current_page() == page
    assert g.ctx.stats.totals()["games"] == 0


def test_closing_mid_battle_is_a_loss(app, win):
    g = win.game
    battle(app, g, 1)
    assert g.shutdown() is True
    assert g.ctx.stats.totals()["games"] == 1
