"""Виджет игры (create_widget по контракту): меню, расстановка, бой, статистика, настройки.

Окно ему даёт оболочка (aikit.run_standalone или ИИ-Игротека). Тема и язык приходят из
ctx и меняются на лету по ctx.changed. Файлы - только в ctx.data_dir: settings.json,
habits.json (привычки игрока), records.json (меньше всего выстрелов до победы).
"""
import json
import os
import random

import numpy as np
from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QListWidget, QScrollArea, QSlider, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from aikit import settings as st
from aikit import gamelog, theme
from aikit.charts import GameCharts
from aikit.storage import is_int, load_json, save_json
from aikit.widgets import Combo, button, card, label, restyle
from game.ai.agents import LEVELS
from game.ai.habits import Habits
from game.ai.prob import uniform_fleet
from game.core.rules import Rules, cell_name, valid_fleet
from game.ui.ai_thread import AiController
from game.ui.board import BoardWidget, SetupBoard
from game.ui.i18n import translator
from aikit.skin import SettingsList, SkinPage, StatTiles
from game.ui.skin import SKIN
from game.ui.menu import MenuPage, page_qss, side_qss
from game.ui.menu import palette as sea_palette
from game.ui.session import Session
from game.version import VERSION

SCHEMA = {
    "level": ("medium", st.choice(*LEVELS)),
    "mode": ("play", st.choice("play", "demo")),
    "corners": (False, st.boolean()),
    "salvo": (False, st.boolean()),
    "show_thoughts": (False, st.boolean()),
    "anim_ms": (450, st.int_range(0, 1200)),
    "delay_ms": (500, st.int_range(0, 3000)),
}
PASSPORT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "seawar-passport.json")


def page_widget():
    w = QWidget()
    w.setObjectName("page")
    w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return w


def scroll_page(margins=(26, 22, 26, 22)):
    """Страница с прокруткой: (внешний виджет, колонка для содержимого)."""
    outer = QWidget()
    lay = QVBoxLayout(outer)
    lay.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    lay.addWidget(scroll)
    body = page_widget()
    scroll.setWidget(body)
    col = QVBoxLayout(body)
    col.setContentsMargins(*margins)
    col.setSpacing(14)
    return outer, col


def load_passport():
    with open(PASSPORT, encoding="utf-8") as f:
        return json.load(f)


# --- расстановка ---


class SetupPage(QWidget):
    def __init__(self, gw):
        super().__init__()
        self.gw = gw
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        col = QVBoxLayout(self)
        col.setContentsMargins(26, 20, 26, 20)
        col.setSpacing(10)
        self.heading = label("", "heading")
        col.addWidget(self.heading)
        self.hint = label("", "muted", wrap=True)
        col.addWidget(self.hint)
        self.board = SetupBoard()
        self.board.changed.connect(self.on_changed)
        col.addWidget(self.board, 1)
        bottom = QHBoxLayout()
        self.status = label("", "section")
        bottom.addWidget(self.status)
        bottom.addStretch(1)
        # слоты - только через lambda: clicked(False) иначе уходит в первый аргумент (урок DurakAi:
        # start_game(seed=False) - одна и та же раздача)
        self.random_button = button("", None, lambda: gw.random_setup())
        self.clear_button = button("", None, self.board.clear)
        self.menu_button = button("", None, lambda: gw.show_page("menu"))
        self.battle_button = button("", "primary", lambda: gw.start_battle())
        for b in (self.random_button, self.clear_button, self.menu_button, self.battle_button):
            bottom.addWidget(b)
        col.addLayout(bottom)

    def on_changed(self):
        t = self.gw.t
        left = sum(1 for s in self.board.placed if s is None)
        ok = left == 0 and valid_fleet(self.board.fleet(), self.board.rules)
        self.status.setText(t("setup_ready") if ok else t("setup_left", n=left))
        self.battle_button.setEnabled(ok)
        # выключенная «основная» кнопка выглядит как включённая - красится, только когда можно
        restyle(self.battle_button, "primary" if ok else "")

    def retranslate(self):
        t = self.gw.t
        self.heading.setText(t("setup_title"))
        corners = self.gw.settings["corners"]
        self.hint.setText(t("setup_hint", corners=t("setup_hint_corners" if corners else "setup_hint_strict")))
        self.random_button.setText(t("random"))
        self.clear_button.setText(t("clear"))
        self.menu_button.setText(t("menu"))
        self.battle_button.setText(t("battle"))
        self.on_changed()


# --- бой ---


class PlayPage(QWidget):
    def __init__(self, gw):
        super().__init__()
        self.gw = gw
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)
        boards = QHBoxLayout()
        boards.setSpacing(10)
        self.own = BoardWidget()
        self.enemy = BoardWidget()
        self.enemy.cellClicked.connect(gw.on_cell)
        boards.addWidget(self.own, 1)
        boards.addWidget(self.enemy, 1)
        root.addLayout(boards, 1)

        side = card()
        side.setFixedWidth(290)
        outer = QVBoxLayout(side)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        outer.addWidget(scroll)
        body = QWidget()
        self.body = body
        self.scroll = scroll
        scroll.setWidget(body)
        body.installEventFilter(self)        # ширина тела панели сменилась - подписи заново
        col = QVBoxLayout(body)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(6)
        self.heading = label("", "section", wrap=True)
        col.addWidget(self.heading)
        self.status = label("", "status", wrap=True)
        col.addWidget(self.status)
        self.substatus = label("", "muted", wrap=True)
        self.substatus.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        col.addWidget(self.substatus)
        self.counts = label("", "hint", wrap=True)
        col.addWidget(self.counts)
        self.thoughts_box = QCheckBox("")
        self.thoughts_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.thoughts_box.toggled.connect(lambda on: gw.change("show_thoughts", on))
        col.addWidget(self.thoughts_box)
        self.thoughts_hint = label("", "hint", wrap=True)
        col.addWidget(self.thoughts_hint)
        self.best = label("", "hint", wrap=True)
        col.addWidget(self.best)
        self.log_caption = label("", "muted")
        col.addWidget(self.log_caption)
        self.log = QListWidget()
        self.log.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.log.setMinimumHeight(120)
        col.addWidget(self.log, 1)
        self.pause_button = button("", None, lambda: gw.toggle_pause())
        col.addWidget(self.pause_button)
        last = QHBoxLayout()
        self.again_button = button("", "primary", lambda: gw.new_clicked())
        self.menu_button = button("", None, lambda: gw.show_page("menu"))
        last.addWidget(self.again_button, 1)
        last.addWidget(self.menu_button, 1)
        col.addLayout(last)
        root.addWidget(side)
        self.side = side

    def fit_labels(self):
        """Подписи с переносом - по своей ширине (ловушка qt-wrapped-label-height: только минимум).
        Тело панели - сразу по новой наименьшей высоте: заголовок «Морской бой · Средний · По
        одному» во второй строке срезался снизу («одномv», проверка 17.10), пока ширина тела
        менялась после resizeEvent страницы."""
        for w in self.side.findChildren(QLabel):
            if w.wordWrap() and w.width() > 0:
                w.setMinimumHeight(w.heightForWidth(w.width()))
        lay = self.body.layout()
        if lay is not None:
            lay.activate()
            need = self.body.minimumSizeHint().height()
            if self.body.height() < need:
                self.body.resize(self.body.width(), need)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_labels()

    def eventFilter(self, obj, event):
        if obj is self.body and event.type() == QEvent.Type.Resize:
            self.fit_labels()
        return False

    def retranslate(self):
        t = self.gw.t
        self.thoughts_box.setText(t("thoughts"))
        self.log_caption.setText(t("log"))
        self.again_button.setText(t("again"))
        self.menu_button.setText(t("menu"))
        self.pause_button.setText(t("resume") if self.gw.paused else t("pause"))
        self.fit_labels()


# --- статистика ---


def table_widget(cols):
    tw = QTableWidget(0, cols)
    tw.verticalHeader().setVisible(False)
    tw.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tw.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    tw.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    tw.setShowGrid(False)
    tw.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    tw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    header = tw.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setHighlightSections(False)
    return tw


def fit_height(tw):
    tw.resizeRowsToContents()
    tw.setFixedHeight(tw.horizontalHeader().height() + sum(tw.rowHeight(r) for r in range(tw.rowCount())) + 4)


def item(text, align=Qt.AlignmentFlag.AlignCenter):
    it = QTableWidgetItem(text)
    it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    return it


class StatsPage(SkinPage):
    """Статистика в стиле «штурманской рубки» (aikit.skin, game/ui/skin.py): морская карта на фоне,
    таблички с полосой сонара, плитки с крупными числами."""

    def __init__(self, gw):
        super().__init__(SKIN, back=lambda: gw.show_page("menu"))
        self.gw = gw
        self.menu_button = self.back_button
        col = self.col
        self.tiles = StatTiles(4, min_tile=170)
        col.addWidget(self.tiles)
        mine = card()
        mc = QVBoxLayout(mine)
        mc.setContentsMargins(18, 14, 18, 14)
        self.mine_title = label("", "section")
        mc.addWidget(self.mine_title)
        self.table = table_widget(6)
        mc.addWidget(self.table)
        col.addWidget(mine)
        # графики (правило автора 10.10 - графики в статистике всех игр с ИИ): доля побед,
        # итоги по уровням, выстрелов за партию, выстрелов до победы с рекордом, паспорт
        cc = card()
        cl = QVBoxLayout(cc)
        cl.setContentsMargins(18, 14, 18, 14)
        cl.setSpacing(10)
        self.charts_title = label("", "section")
        cl.addWidget(self.charts_title)
        self.charts = GameCharts(LEVELS, length_key="shots", score_key="win_shots", score_better="min",
                                 passport=True)
        self.charts.passport.percent = False             # паспорт - среднее число выстрелов
        cl.addWidget(self.charts)
        col.addWidget(cc)
        pc = card()
        pl = QVBoxLayout(pc)
        pl.setContentsMargins(18, 14, 18, 14)
        self.pass_title = label("", "section")
        self.pass_text = label("", "muted", wrap=True)
        self.checks = table_widget(3)
        self.pass_foot = label("", "hint", wrap=True)
        for w in (self.pass_title, self.pass_text, self.checks, self.pass_foot):
            pl.addWidget(w)
        col.addWidget(pc)
        col.addStretch(1)

    def refresh_tiles(self):
        t = self.gw.t
        data = self.gw.ctx.stats.data.values()
        games = sum(e["games"] for e in data)
        wins = sum(e["wins"] for e in data)
        streak = max((e["best_streak"] for e in data), default=0)
        recs = self.gw.records()
        best = min(recs.values()) if recs else None
        self.tiles.set_tile(0, games, t("tile_games"), t("tile_games_note"))
        self.tiles.set_tile(1, wins, t("tile_wins"), t("tile_rate", p=round(100 * wins / games)) if games else "")
        self.tiles.set_tile(2, best if best else "-", t("tile_record"), "" if best else t("tile_record_none"))
        self.tiles.set_tile(3, streak, t("tile_streak"))
        self.set_tag(t("menu_tag_stats"))

    def refresh(self):
        t = self.gw.t
        self.heading.setText(t("stats_title"))
        self.menu_button.setText(t("menu"))
        self.refresh_tiles()
        self.mine_title.setText(t("your_games"))
        self.table.setHorizontalHeaderLabels([t(k) for k in ("col_setup", "col_games", "col_wins", "col_losses",
                                                               "col_streak", "col_best")])
        rows = [(lv, v) for lv in LEVELS for v in ("classic", "salvo")]
        self.table.setRowCount(len(rows))
        stats = self.gw.ctx.stats
        records = self.gw.records()
        for r, (lv, v) in enumerate(rows):
            key = f"{lv}/{v}"
            e = stats.entry(key)
            self.table.setItem(r, 0, item(f"{t(lv)} · {t(v)}", Qt.AlignmentFlag.AlignLeft))
            for c, f in enumerate(("games", "wins", "losses", "best_streak"), start=1):
                self.table.setItem(r, c, item(str(e[f])))
            self.table.setItem(r, 5, item(str(records[key]) if key in records else "-"))
        fit_height(self.table)
        self.refresh_charts()
        self.pass_title.setText(t("passport"))
        try:
            pp = load_passport()
            shots = pp["checks"]["shots"]
        except (OSError, ValueError, KeyError):
            self.pass_text.setText(t("not_measured"))
            self.checks.hide()
            self.pass_foot.hide()
            return
        n = min(v["games"] for v in shots.values())
        self.pass_text.setText(t("passport_text", n=f"{n:,}".replace(",", " ")))
        self.checks.setHorizontalHeaderLabels([t("col_level"), t("col_mean"), t("col_median")])
        self.checks.setRowCount(len(LEVELS))
        for r, lv in enumerate(LEVELS):
            s = shots.get(lv, {})
            self.checks.setItem(r, 0, item(t(lv), Qt.AlignmentFlag.AlignLeft))
            self.checks.setItem(r, 1, item(f"{s.get('mean', 0):.1f}"))
            self.checks.setItem(r, 2, item(f"{s.get('median', 0):g}"))
        fit_height(self.checks)
        self.checks.show()
        foot = []
        duel = pp["checks"].get("duel")
        if duel:
            foot.append(t("duel_text", p=f"{100 * duel['score']:.1f}", n=duel["games"]))
        place = pp["checks"].get("placement", {}).get("strong")
        if place:
            foot.append(t("placement_text", a=f"{place['mean']:.1f}", b=f"{place['random_mean']:.1f}"))
        self.pass_foot.setText(" ".join(foot))
        self.pass_foot.setVisible(bool(foot))

    def refresh_charts(self):
        t = self.gw.t
        self.charts_title.setText(t("charts"))
        self.charts.set_theme(self.gw.ctx.theme)
        try:
            shots = load_passport()["checks"]["shots"]
            levels = [lv for lv in LEVELS if lv in shots]
            passport = ([t(lv) for lv in levels], [(t("ch_mean_shots"), "accent", [shots[lv]["mean"] for lv in levels])])
        except (OSError, ValueError, KeyError, TypeError):
            passport = None
        self.charts.refresh(self.gw.history.games, self.gw.ctx.lang, {lv: t(lv) for lv in LEVELS},
                            labels={"length": t("ch_shots"), "length_empty": t("ch_shots_empty"),
                                    "length_y": t("ch_shots_y"), "score": t("ch_win_shots"),
                                    "score_empty": t("ch_win_shots_empty"), "score_y": t("ch_shots_y"),
                                    "points": t("ch_win"), "passport": t("ch_passport"),
                                    "passport_empty": t("not_measured")},
                            passport=passport)


# --- настройки ---


class SettingsPage(SkinPage):
    """Настройки в стиле «штурманской рубки»: таблички на всю ширину (как статистика; автор 17.10),
    две группы - вид и звук, бой."""

    def __init__(self, gw):
        super().__init__(SKIN, back=lambda: gw.show_page("menu"))
        self.gw = gw
        self.menu_button = self.back_button
        box = SettingsList()
        self.box = box
        self.rows = box.rows
        box.group("")
        self.theme_combo = Combo()
        for k in theme.THEMES:
            self.theme_combo.addItem("", k)
        self.theme_combo.currentIndexChanged.connect(lambda i: gw.ctx.set_theme(self.theme_combo.itemData(i)))
        self._row("theme", self.theme_combo)
        self.lang_combo = Combo()
        self.lang_combo.addItem("Русский", "ru")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.currentIndexChanged.connect(lambda i: gw.ctx.set_lang(self.lang_combo.itemData(i)))
        self._row("language", self.lang_combo)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(gw.ctx.sound.volume)
        self.volume.valueChanged.connect(gw.ctx.set_volume)
        self._row("volume", self.volume)
        self.anim = QSlider(Qt.Orientation.Horizontal)
        self.anim.setRange(0, 1200)
        self.anim.valueChanged.connect(lambda v: gw.change("anim_ms", int(v)))
        self._row("anim", self.anim)
        box.group("")
        self.delay = QSlider(Qt.Orientation.Horizontal)
        self.delay.setRange(0, 3000)
        self.delay.valueChanged.connect(lambda v: gw.change("delay_ms", int(v)))
        self._row("delay", self.delay)
        self.salvo_box = QCheckBox("")
        self.salvo_box.toggled.connect(lambda on: gw.change("salvo", on))
        self._row("salvo_rule", self.salvo_box)
        self.habits_button = button("", None, lambda: gw.forget_habits())
        self._row("habits", self.habits_button)
        self.col.addWidget(box)
        self.note = label("", "hint")
        self.col.addWidget(self.note)
        self.col.addStretch(1)

    def _row(self, key, widget):
        self.box.add(key, widget)

    def retranslate(self):
        t = self.gw.t
        self.heading.setText(t("settings_title"))
        self.menu_button.setText(t("menu"))
        self.set_tag(t("menu_tag_settings"))
        self.box.set_group(0, t("group_view"))
        self.box.set_group(1, t("group_battle"))
        for key, (title, hint) in self.rows.items():
            title.setText(t(key))
            hint.setText(t(key + "_hint", n=self.gw.habits.games) if key == "habits" else t(key + "_hint"))
            hint.setVisible(bool(hint.text()))
        for i, k in enumerate(theme.THEMES):
            self.theme_combo.setItemText(i, t(k))
        self.habits_button.setText(t("habits_reset"))
        self.note.setText(t("saved_note"))
        self.sync()

    def sync(self):
        g = self.gw
        for combo, value in ((self.theme_combo, g.ctx.theme), (self.lang_combo, g.ctx.lang)):
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(value))
            combo.blockSignals(False)
        for w, value in ((self.anim, g.settings["anim_ms"]), (self.delay, g.settings["delay_ms"])):
            w.blockSignals(True)
            w.setValue(value)
            w.blockSignals(False)
        self.salvo_box.blockSignals(True)
        self.salvo_box.setChecked(g.settings["salvo"])
        self.salvo_box.blockSignals(False)
        self.rows["habits"][1].setText(g.t("habits_hint", n=g.habits.games))
        self.habits_button.setEnabled(g.habits.games > 0 or g.habits.shot_games > 0)


# --- сам виджет игры ---


class GameWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.t = translator(ctx.lang)
        self.settings = st.Settings(SCHEMA, ctx.file("settings.json"))
        self.habits = Habits(ctx.file("habits.json"))
        self.session = None
        self.token = 0
        self.paused = False            # пауза показа «ИИ против ИИ» (кнопка)
        self.hidden = False            # оболочка спрятала вкладку: pause() / resume()
        self.thoughts = None           # {'map', 'method', 'board'} - на каком поле
        self.last = {0: -1, 1: -1}     # последний выстрел по полю игрока
        self.rng = random.Random()
        self.ai = AiController(self)
        self.ai.ready.connect(self.on_ai)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._step)
        self.stack = QStackedWidget(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self.menu = MenuPage(self)
        self.setup = SetupPage(self)
        self.play = PlayPage(self)
        self.history = gamelog.GameLog(ctx.file("games.json"))
        self.stats = StatsPage(self)
        self.settings_page = SettingsPage(self)
        self.pages = {"menu": self.menu, "setup": self.setup, "play": self.play, "stats": self.stats,
                      "settings": self.settings_page}
        for p in self.pages.values():
            self.stack.addWidget(p)
        self.confirm_new = False       # N/«Новая партия» посреди боя: второй раз - сдаться
        for keys, slot in (("Escape", lambda: self.show_page("menu")), ("N", self.new_clicked),
                           ("R", self.random_setup)):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)
        ctx.changed.connect(self.on_ctx_changed)
        self.apply_anim()
        self.apply_theme()
        self.retranslate()
        self.show_page("menu")

    def minimumSizeHint(self):
        return QSize(900, 620)

    # --- общее ---

    def rules(self):
        return Rules(corners=self.settings["corners"], salvo=self.settings["salvo"])

    def current_page(self):
        w = self.stack.currentWidget()
        return next(k for k, p in self.pages.items() if p is w)

    def show_page(self, name):
        if name != "play":
            self._invalidate()
        self.stack.setCurrentWidget(self.pages[name])
        if name == "stats":
            self.stats.refresh()
        elif name == "settings":
            self.settings_page.sync()
        elif name == "menu":
            self.menu.sync(self.settings)
            self.menu.set_battle(self.in_battle())
            self.refresh_menu()
        elif name == "setup":
            self.setup.board.set_rules(self.rules())
            if not valid_fleet(self.setup.board.fleet(), self.rules()) and self.setup.board.complete():
                self.setup.board.clear()
            self.setup.retranslate()

    def refresh_menu(self):
        """Нижняя строка меню: партии, победы, рекорд (меньше всего выстрелов до победы)."""
        t = self.t
        totals = self.ctx.stats.totals()
        recs = self.records()
        best = min(recs.values()) if recs else None
        text = t("menu_foot", games=totals["games"], wins=totals["wins"])
        text += " · " + (t("menu_best", n=best) if best else t("menu_no_best"))
        self.menu.set_foot(text + " · " + t("footer", v=VERSION))

    def change(self, key, value):
        if self.settings[key] == value:
            return
        self.settings.set(key, value)
        if key in ("level", "mode", "corners", "salvo"):
            self.menu.sync(self.settings)
        if key == "corners":
            self.setup.board.set_rules(self.rules())
            self.setup.retranslate()
        elif key in ("anim_ms",):
            self.apply_anim()
        elif key == "show_thoughts":
            self.thoughts = None
            self.after_change()

    def apply_anim(self):
        for b in (self.play.own, self.play.enemy):
            b.anim_ms = self.settings["anim_ms"]

    def on_ctx_changed(self, what):
        if what == "theme":
            self.apply_theme()
        elif what == "lang":
            self.t = translator(self.ctx.lang)
            self.retranslate()

    def apply_theme(self):
        c = theme.palette(self.ctx.theme)
        sea = sea_palette(self.ctx.theme)
        self.menu.set_theme(self.ctx.theme)
        # расстановка, бой и боковая панель - в стиле меню (автор 17.10: и боковые панели свои)
        for page in (self.setup, self.play):
            page.setStyleSheet(page_qss(sea))
        self.play.side.setStyleSheet(side_qss(sea))
        for b in (self.play.own, self.play.enemy, self.setup.board):
            b.set_theme(self.ctx.theme, self.ctx.lang)
        for combo in self.findChildren(Combo):
            combo.set_arrow_color(c["text"])
        # настройки и статистика - в стиле «штурманской рубки» (aikit.skin; автор 17.10)
        SKIN.lang = self.ctx.lang
        self.stats.set_theme(self.ctx.theme)
        self.settings_page.set_theme(self.ctx.theme)
        self.update()

    def retranslate(self):
        for b in (self.play.own, self.play.enemy, self.setup.board):
            b.set_theme(self.ctx.theme, self.ctx.lang)
        SKIN.lang = self.ctx.lang                  # буквы сетки на фоне страниц - на языке окна
        self.stats.set_theme(self.ctx.theme)
        self.settings_page.set_theme(self.ctx.theme)
        self.menu.retranslate()
        self.refresh_menu()
        self.setup.retranslate()
        self.play.retranslate()
        self.settings_page.retranslate()
        if self.current_page() == "stats":
            self.stats.refresh()
        if self.session is not None:
            self.refresh()

    def pause(self):
        """Оболочка спрятала вкладку (переключились на другую игру, свернули окно): ИИ не
        думает и не стреляет, таймеры и анимации стоят. Партия ждёт."""
        if self.hidden:
            return
        self.hidden = True
        self.menu.pause()
        self._invalidate()
        for b in (self.play.own, self.play.enemy):
            b.stop()

    def resume(self):
        """Вкладку показали снова: партия идёт дальше с того же места."""
        if not self.hidden:
            return
        self.hidden = False
        self.menu.resume()
        if self.session is not None and self.current_page() == "play":
            self.after_change()

    def shutdown(self):
        """Окно закрывается: таймеры стоп, расчёты ИИ остановить и дождаться (не дольше 2 с).
        Начатый бой (был выстрел человека) - поражение."""
        self.give_up()
        self._invalidate()
        for b in (self.play.own, self.play.enemy):
            b.stop()
        return self.ai.shutdown(2000)

    def _invalidate(self):
        self.token += 1
        self.timer.stop()
        self.ai.cancel()

    def forget_habits(self):
        self.habits.reset()
        self.settings_page.sync()

    def records(self):
        raw = load_json(self.ctx.file("records.json"))
        if not isinstance(raw, dict):
            return {}
        return {k: v for k, v in raw.items() if isinstance(k, str) and is_int(v) and v > 0}

    # --- партия ---

    def in_battle(self):
        """Бой человека с ИИ начат и не кончен: в меню «Продолжить бой», новый - только сдавшись."""
        s = self.session
        return s is not None and s.mode == "play" and not s.over and not s.recorded

    def menu_play(self):
        """Главная кнопка меню: идёт бой - вернуться в него (проверка 17.10: после Esc бой пропадал)."""
        if self.in_battle():
            self.show_page("play")
            self.after_change()
        else:
            self.play_clicked()

    def give_up(self):
        """Сдаться: брошенный после первого выстрела человека бой - поражение (как в Дураке и КНБ;
        проверка 17.10: Esc/N посреди боя бросали его без записи)."""
        s = self.session
        if not self.in_battle():
            return False
        if s.human_shots:
            self.ctx.stats.record(s.stats_key(), "loss")
            level, variant = s.stats_key().split("/")[:2]
            self.history.record({"level": level, "variant": variant, "outcome": "loss",
                                 "shots": s.match.shots[s.human], "abandoned": 1})
        s.recorded = True
        self.session = None
        self._invalidate()
        return True

    def new_clicked(self):
        """N и «Новая партия»: посреди боя сначала вопрос, второй раз - сдаться и новый бой."""
        if self.current_page() == "play" and self.in_battle() and self.session.human_shots:
            if not self.confirm_new:
                self.confirm_new = True
                self.play.substatus.setText(self.t("confirm_new"))
                self.play.again_button.setText(self.t("give_up_new"))
                self.play.fit_labels()
                return
            self.give_up()
        elif self.current_page() not in ("play", "setup", "menu") or self.in_battle():
            return                       # в статистике и настройках N ничего не делает, в меню
                                         # при начатом бое - тоже (сдаться - своей кнопкой)
        self.confirm_new = False
        self.play_clicked()

    def play_clicked(self):
        if self.in_battle():
            self.give_up()
        self.confirm_new = False
        self.play.again_button.setText(self.t("again"))
        if self.settings["mode"] == "demo":
            self.start_battle()
        else:
            self.show_page("setup")

    def random_setup(self):
        if self.current_page() != "setup":
            return
        rng = np.random.default_rng(self.rng.randrange(2 ** 31))
        self.setup.board.set_fleet(uniform_fleet(rng, self.settings["corners"]))

    def start_battle(self, seed=None, fleet=None):
        s = self.settings
        mode = s["mode"]
        if seed is None:
            seed = self.rng.randrange(2 ** 31)
        if mode == "play":
            fleet = fleet if fleet is not None else self.setup.board.fleet()
            if not valid_fleet(fleet, self.rules()):
                self.show_page("setup")
                return
        self.session = Session(fleet, s["level"], self.rules(), seed, mode,
                               self.habits if s["level"] == "strong" else None, first=seed % 2)
        self.paused = False
        self.thoughts = None
        self.last = {0: -1, 1: -1}
        self.play.log.clear()
        for b in (self.play.own, self.play.enemy):
            b.stop()
        self._invalidate()
        self.stack.setCurrentWidget(self.play)
        self.play.retranslate()
        self.after_change()

    def on_cell(self, cell):
        s = self.session
        if s is None or self.hidden or not s.human_turn() or cell not in s.match.legal():
            return
        self._fire(cell)

    def _fire(self, cell):
        s = self.session
        if self.confirm_new:                 # выстрелил - значит, передумал сдаваться
            self.confirm_new = False
            self.play.again_button.setText(self.t("again"))
        p, shot = s.fire(cell)
        target = 1 - p
        self.last[target] = cell
        board = self.play.enemy if target == 1 else self.play.own
        board.add_effect(cell, shot.result)
        self.ctx.sound.play("move" if shot.result == "miss" else "capture")
        self.play.log.insertItem(0, f"{self.names()[p]}: {cell_name(cell, self.ctx.lang)} - {self.t('res_' + shot.result)}")
        if self.thoughts is not None and self.thoughts["board"] == target:
            self.thoughts = None
        self.after_change()

    def names(self):
        if self.session is not None and self.session.mode == "demo":
            return [self.t("ai_n", n=1), self.t("ai_n", n=2)]
        return [self.t("you"), self.t("ai")]

    def after_change(self):
        """После любого изменения партии: перерисовать, записать итог, запустить ИИ."""
        self.token += 1
        self.timer.stop()
        self.ai.cancel()
        s = self.session
        if s is None:
            return
        self.refresh()
        if s.over:
            self._finish()
            return
        if self.hidden:                    # resume() запустит ИИ заново
            return
        show = self.settings["show_thoughts"]
        if s.human_turn():
            if show and self.thoughts is None:      # куда ИИ хочет выстрелить по вашему полю
                ai = 1 - s.human
                self.ai.request_thoughts(self.token, s.obs(ai), s.level, self.rng.randrange(2 ** 31),
                                         self._habits(), parity=ai)
            return
        if s.mode == "demo" and self.paused:
            return
        self.timer.start(self._delay())

    def _habits(self):
        s = self.session
        return self.habits if (s is not None and s.mode == "play" and s.level == "strong") else None

    def _delay(self):
        busy = self.play.own.animating() or self.play.enemy.animating()
        return max(self.settings["delay_ms"], (self.settings["anim_ms"] + 40) if busy else 0)

    def _step(self):
        s = self.session
        if s is None or s.over or s.human_turn():
            return
        p = s.turn
        self.ai.request_move(self.token, s.obs(p), s.level, self.rng.randrange(2 ** 31),
                             self._habits(), parity=p)

    def on_ai(self, token, kind, payload):
        if token != self.token or self.session is None:
            return
        s = self.session
        if isinstance(payload, Exception):
            self.play.substatus.setText(self.t("error", e=payload))
            return
        if kind == "thoughts":
            self.thoughts = {"map": payload["map"], "method": payload["method"], "board": s.human}
            self.refresh()
            return
        if s.ai_turn() and payload["cell"] in s.match.legal():
            if self.settings["show_thoughts"]:
                self.thoughts = {"map": payload["map"], "method": payload["method"], "board": 1 - s.turn}
            self._fire(payload["cell"])

    def _finish(self):
        s = self.session
        outcome = s.outcome_for_human()
        if outcome and not s.recorded:
            self.ctx.stats.record(s.stats_key(), outcome)
            level, variant = s.stats_key().split("/")[:2]
            game = {"level": level, "variant": variant, "outcome": outcome, "shots": s.match.shots[s.human]}
            if outcome == "win":
                game["win_shots"] = game["shots"]
            self.history.record(game)                    # журнал для графиков статистики
            if outcome == "win":
                rec = self.records()
                key = s.stats_key()
                n = s.match.shots[s.human]
                if key not in rec or n < rec[key]:
                    rec[key] = n
                    save_json(self.ctx.file("records.json"), rec)
            s.record_habits(self.habits)
            s.recorded = True
            self.ctx.sound.play(outcome)
            self.settings_page.sync()

    def toggle_pause(self):
        self.paused = not self.paused
        self.play.pause_button.setText(self.t("resume") if self.paused else self.t("pause"))
        if not self.paused:
            self.after_change()
        else:
            self._invalidate()

    # --- вид ---

    def refresh(self):
        s = self.session
        if s is None:
            return
        t = self.t
        pp = self.play
        m = s.match
        demo = s.mode == "demo"
        names = self.names()
        show = self.settings["show_thoughts"]
        th = self.thoughts if show else None
        for idx, board in ((0, pp.own), (1, pp.enemy)):
            b = m.boards[idx]
            open_ = demo or idx == s.human or s.over
            ships = b.ships if open_ else [sh for sh, d in zip(b.ships, b.sunk) if d]
            heat = th["map"] if th is not None and th["board"] == idx else None
            board.set_state(b.view, ships, b.auto, heat, self.last[idx])
        if demo:
            pp.own.title, pp.enemy.title = t("fleet_n", n=1), t("fleet_n", n=2)
        else:
            pp.own.title, pp.enemy.title = t("your_fleet"), t("enemy_fleet")
        pp.enemy.clickable = s.human_turn()
        rules = t("shots_salvo") if s.rules.salvo else t("shots_single")
        pp.heading.setText(f"{t('app_title')} · {t(s.level)} · {rules}")
        if s.over:
            outcome = s.outcome_for_human()
            if outcome:
                restyle(pp.status, "statusWin" if outcome == "win" else "statusLoss")
                pp.status.setText(t(outcome))
            else:
                restyle(pp.status, "status")
                pp.status.setText(t("winner_is", n=m.winner + 1))
        else:
            restyle(pp.status, "status")
            if s.human_turn():
                pp.status.setText(t("your_salvo", n=m.shots_left) if s.rules.salvo else t("your_turn"))
            else:
                pp.status.setText(t("ai_n_turn", n=m.turn + 1) if demo else t("ai_turn"))
        if demo:
            pp.substatus.setText(t("demo_text", level=t(s.level).lower()))
            pp.counts.setText(t("shots_count_demo", a=m.shots[0], b=m.shots[1]))
        else:
            key = "play_text_salvo" if s.rules.salvo else "play_text"
            pp.substatus.setText(t(key, level=t(s.level).lower()))
            pp.counts.setText(t("shots_count", a=m.shots[0], b=m.shots[1]) + "\n"
                              + t("afloat", a=len(m.boards[0].remaining()), b=len(m.boards[1].remaining())))
        pp.thoughts_box.blockSignals(True)
        pp.thoughts_box.setChecked(show)
        pp.thoughts_box.blockSignals(False)
        pp.thoughts_hint.setText(t("thoughts_hint_demo") if demo else t("thoughts_hint"))
        pp.thoughts_hint.setVisible(show)
        best = ""
        if th is not None and not s.over:
            hm = np.asarray(th["map"])
            board = m.boards[th["board"]]
            unknown = [i for i, v in enumerate(board.view) if v == 0]
            if unknown and hm[unknown].max() > 0:
                x = max(unknown, key=lambda i: hm[i])
                if th["method"] in ("exact", "mc", "density"):
                    best = t("best_here", cell=cell_name(x, self.ctx.lang), p=f"{100 * hm[x]:.0f}") + \
                        f" · {t('thought_method_' + th['method'])}"
        pp.best.setText(best)
        pp.best.setVisible(bool(best))
        pp.pause_button.setVisible(demo)
        pp.fit_labels()
        pp.own.update()
        pp.enemy.update()
