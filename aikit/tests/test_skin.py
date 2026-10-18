"""aikit.skin: страницы настроек и статистики в стиле игры. Разные игры - разный вид, подписи с
переносом не обрезаются, в узком окне ничего не уходит за край, графики берут вид у игры."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QCheckBox, QGridLayout, QSlider, QVBoxLayout, QWidget

from aikit.charts import ChartGrid, LineChart
from aikit.menu import SIZES
from aikit.skin import (BUTTON_STYLES, CARD_STYLES, DEFAULT, SettingsList, Skin, SkinPage, StatTiles, difference,
                        page_problems)
from aikit.widgets import Combo, button, card, label, segmented

LONG = ("Подпись с переносом, которая в узком окне занимает несколько строк и не должна обрезаться "
        "ни сверху, ни снизу, даже если на настоящем экране буквы шире, чем в кадре без экрана.")


class Field(Skin):
    """Стиль «другой игры»: свой фон, фаска, рубленый шрифт."""
    key = "field"
    palettes = {
        "dark": {"bg": "#121611", "surface": "#2c3427", "surface2": "#3d4835", "border": "#56603f",
                 "text": "#e9ecdf", "muted": "#a3a98f", "accent": "#d9c26a", "accent_text": "#1a1c10"},
        "light": {"bg": "#d9dccb", "surface": "#eceee2", "surface2": "#c4c9b0", "border": "#8e9471",
                  "text": "#1d2216", "muted": "#555b45", "accent": "#6f5f12", "accent_text": "#fbf8e8"},
    }
    heading_family = "Bahnschrift"
    heading_upper = True
    heading_spacing = 0.08
    card_style = "bevel"
    button_style = "bevel"
    radius = 0
    painted = 0

    def paint_backdrop(self, p, w, h, pal, theme):
        Field.painted += 1
        p.fillRect(0, 0, w, h, QColor(pal["bg"]))
        c = 28
        p.setPen(QColor(pal["border"]))
        for x in range(0, w, c):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, c):
            p.drawLine(0, y, w, y)


def stats_page(skin):
    page = SkinPage(skin)
    page.heading.setText("Статистика")
    page.back_button.setText("Назад")
    page.set_tag("ПОЛЕ 9×9 · МИН 10")
    tiles = StatTiles(4)
    for i, (v, c) in enumerate((("12", "партий сыграно"), ("7", "побед"), ("58%", "доля побед"),
                                ("41 с", "рекорд поля «Новичок»"))):
        tiles.set_tile(i, v, c, "без подсказок" if i == 0 else "")
    page.col.addWidget(tiles)
    box = card()
    lay = QVBoxLayout(box)
    lay.addWidget(label("Графики", "section"))
    grid = ChartGrid()
    a = grid.add(LineChart(percent=True))
    a.set_texts("Доля ваших побед", "Сыграйте две партии - здесь появится график.")
    a.set_points([(i, (i % 5) / 5) for i in range(1, 30)])
    b = grid.add(LineChart(percent=False))
    b.set_texts("Время партии", "Пусто")
    lay.addWidget(grid)
    page.col.addWidget(box)
    page.col.addStretch(1)
    return page


def settings_page(skin):
    page = SkinPage(skin)
    page.heading.setText("Настройки")
    page.back_button.setText("Назад")
    box = card()
    grid = QGridLayout(box)
    grid.setColumnStretch(0, 3)
    grid.setColumnStretch(1, 2)
    rows = [("Тема", Combo()), ("Громкость", QSlider()), ("Поле без угадываний", QCheckBox("Включено")),
            ("Уровень", segmented({"a": "Новичок", "b": "Средний", "c": "Сильный"}, lambda v: None)[0])]
    for r, (name, w) in enumerate(rows):
        names = QVBoxLayout()
        names.addWidget(label(name, "section"))
        names.addWidget(label(LONG if r == 0 else "Короткое пояснение", "hint", wrap=True))
        grid.addLayout(names, r, 0)
        grid.addWidget(w, r, 1)
    page.col.addWidget(box)
    rows = SettingsList()
    rows.group("Вид и звук")
    t, h = rows.add("lang", Combo())
    t.setText("Язык")
    h.setText(LONG)
    rows.group("Игра")
    t, h = rows.add("speed", QSlider(Qt.Orientation.Horizontal))
    t.setText("Скорость ИИ")
    h.setText("Пауза между ходами")
    page.col.addWidget(rows)
    page.col.addWidget(button("Сбросить статистику", "primary"))
    page.col.addStretch(1)
    return page


def show(qapp, page, w, h, theme="dark"):
    page.set_theme(theme)
    page.resize(w, h)
    page.show()
    for _ in range(4):
        qapp.processEvents()
    return page


def test_skin_fills_missing_colors_from_aikit_theme():
    pal = Field().palette("dark")
    for key in ("good", "bad", "warn", "grid", "hi", "lo", "stripe", "button", "field"):
        assert key in pal
    assert pal["bg"] == "#121611"
    assert Field().palette("light")["bg"] != pal["bg"]
    assert DEFAULT.palette("dark")["bg"] == "#1f242e"


def test_different_games_look_different(qapp):
    """Закон автора 17.10: страницы статистики разных игр не одинаковые."""
    a = show(qapp, stats_page(DEFAULT), 1180, 780)
    b = show(qapp, stats_page(Field()), 1180, 780)
    share = difference(a.grab(), b.grab())
    assert share > 0.3, share
    assert DEFAULT.signature() != Field().signature()
    same = difference(a.grab(), a.grab())
    assert same == 0.0
    a.close()
    b.close()


def test_heading_uses_game_font_and_case(qapp):
    page = show(qapp, stats_page(Field()), 1180, 780)
    assert page.heading.family == "Bahnschrift"
    assert page.heading.text() == "СТАТИСТИКА"
    assert not page.heading.clipped()
    page.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_pages_clean_from_narrow_to_4k(qapp, theme):
    """Ничего не обрезано, не за краем и не налезает - от 900×640 до 3840×2160."""
    for make in (stats_page, settings_page):
        for skin in (DEFAULT, Field()):
            page = make(skin)
            for w, h in SIZES:
                show(qapp, page, w, h, theme)
                assert page_problems(page) == [], (make.__name__, skin.key, w, h)
            page.close()


def test_every_card_and_button_style_is_clean(qapp):
    for cs in CARD_STYLES:
        for bs in BUTTON_STYLES:
            skin = Field()
            skin.card_style, skin.button_style = cs, bs
            page = show(qapp, settings_page(skin), 900, 640)
            assert page_problems(page) == [], (cs, bs)
            page.close()


def test_wrapped_label_with_height_cap_is_caught(qapp):
    page = settings_page(Field())
    capped = label(LONG, "hint", wrap=True)
    capped.setMaximumHeight(18)
    page.col.insertWidget(1, capped)
    show(qapp, page, 900, 640)
    problems = page_problems(page)
    assert any("потолок высоты" in p for p in problems), problems
    page.close()


def test_too_wide_page_is_caught(qapp):
    """В узком окне содержимое шире окна - правый край обрезан (горизонтальной полосы нет)."""
    page = settings_page(Field())
    wide = QWidget()
    wide.setMinimumWidth(1400)
    page.col.insertWidget(1, wide)
    show(qapp, page, 900, 640)
    assert any("шире окна" in p for p in page_problems(page))
    page.close()


def test_clipped_chart_title_is_caught(qapp):
    page = stats_page(Field())
    grid = page.findChild(ChartGrid)
    grid.charts()[0].set_texts("Очень длинный заголовок графика " * 6, "пусто")
    show(qapp, page, 900, 640)
    assert any("не влезло" in p for p in page_problems(page))
    page.close()


def test_charts_take_card_colors_and_fonts_from_skin(qapp):
    page = show(qapp, stats_page(Field()), 1180, 780)
    chart = page.findChild(ChartGrid).charts()[1]          # пустой - в середине только фон карточки
    assert chart.skin is not None and chart.pal()["surface"] == "#2c3427"
    assert chart.fonts()[0].family() == "Bahnschrift"
    img = chart.grab().toImage()
    inner = img.pixelColor(chart.width() // 2, 60)
    assert inner == QColor("#2c3427")
    edge = img.pixelColor(1, chart.height() // 2)          # фаска слева - светлая
    assert edge == QColor(Field().palette("dark")["hi"])
    plain = LineChart(percent=True)
    assert plain.pal()["surface"] == DEFAULT.palette("dark")["surface"]
    page.close()


def test_theme_switch_restyles_page_and_charts(qapp):
    page = show(qapp, stats_page(Field()), 1180, 780, "dark")
    dark = page.grab()
    show(qapp, page, 1180, 780, "light")
    assert difference(dark, page.grab()) > 0.5
    chart = page.findChild(ChartGrid).charts()[0]
    assert chart.theme == "light"
    page.close()


def test_backdrop_painted_once_per_size_and_theme(qapp):
    Field.painted = 0
    page = show(qapp, stats_page(Field()), 1180, 780)
    for _ in range(3):
        page.repaint()
    assert Field.painted == 1
    show(qapp, page, 1000, 700)
    page.repaint()
    assert Field.painted == 2
    page.close()


def test_tiles_wrap_to_two_columns_in_narrow_window(qapp):
    page = show(qapp, stats_page(Field()), 1180, 780)
    tiles = page.findChild(StatTiles)
    assert tiles.cols == 4
    frame = tiles.tiles[3][0]                               # плитка - в форме карточек игры
    img = frame.grab().toImage()
    assert img.pixelColor(frame.width() - 12, frame.height() - 12) == QColor("#2c3427")
    assert img.pixelColor(1, frame.height() // 2) == QColor(Field().palette("dark")["hi"])
    show(qapp, page, 640, 640)
    assert tiles.cols in (1, 2)
    assert page_problems(page) == []
    page.close()


def test_combo_arrow_follows_skin_text(qapp):
    page = show(qapp, settings_page(Field()), 1180, 780, "light")
    combo = page.findChild(Combo)
    assert combo.arrow_color == QColor(Field().palette("light")["text"])
    page.close()


def test_heading_paint_hook(qapp):
    seen = []

    class Shadow(Field):
        def paint_heading(self, p, rect, text, font, pal, align):
            seen.append((text, font.family()))
            super().paint_heading(p, rect, text, font, pal, align)

    page = show(qapp, stats_page(Shadow()), 1180, 780)
    page.heading.repaint()
    assert seen and seen[-1] == ("СТАТИСТИКА", "Bahnschrift")
    page.close()


def test_checkbox_text_is_not_measured_bold(qapp):
    """Флажок не пишется жирным при выборе - закон жирной ширины его не трогает."""
    from aikit.menu import text_clipped
    box = QCheckBox("Мысли ИИ")
    f = QFont("Segoe UI")
    f.setPixelSize(14)
    box.setFont(f)
    box.setChecked(True)
    box.resize(box.sizeHint())
    assert not text_clipped(box)


def test_settings_rows_are_plates_with_groups(qapp):
    page = show(qapp, settings_page(Field()), 900, 640)
    rows = page.findChild(SettingsList)
    assert set(rows.rows) == {"lang", "speed"}
    assert [g.text() for g in rows.groups] == ["ВИД И ЗВУК", "ИГРА"]
    assert all(f.objectName() == "settingRow" for f in rows.frames.values())
    assert "QFrame#settingRow" in Field().qss("dark")
    assert page_problems(page) == []
    page.close()


def test_table_header_in_game_colors(qapp):
    """Шапка таблицы - цвет карточки игры, а не белая заливка Fusion (поймано на Сапёре 17.10)."""
    from PySide6.QtWidgets import QTableWidget
    page = stats_page(Field())
    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels(["Поле", "Партий", "Побед"])
    page.col.insertWidget(1, table)
    show(qapp, page, 1180, 780)
    head = table.horizontalHeader()
    img = head.grab().toImage()
    assert img.pixelColor(head.width() - 4, 3) == QColor("#2c3427")
    show(qapp, page, 1180, 780, "light")
    img = head.grab().toImage()
    assert img.pixelColor(head.width() - 4, 3) == QColor("#eceee2")
    page.close()
