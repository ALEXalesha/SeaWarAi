"""Графики статистики aikit: заглушка без данных, подписи целы, тема, сетка карточек.

Законы рисуют карточки без экрана (grab) и смотрят и на пиксели, и на chart.clipped -
список подписей, которые не влезли бы на настоящем экране (с запасом ширины SLACK)."""
import random

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

LEVELS = ("novice", "medium", "strong")
NAMES = {"ru": {"novice": "Новичок", "medium": "Средний", "strong": "Сильный"},
         "en": {"novice": "Novice", "medium": "Medium", "strong": "Strong"}}


def games(count=40, seed=1):
    rnd = random.Random(seed)
    out = []
    for i in range(count):
        out.append({"n": i + 1, "level": rnd.choice(LEVELS), "outcome": rnd.choice(("win", "loss", "draw")),
                    "moves": rnd.randint(10, 120), "score": rnd.randint(100, 250000)})
    return out


def colours(img):
    out = set()
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = img.pixelColor(x, y)
            out.add((c.red(), c.green(), c.blue()))
    return out


def near(colour, found, tol=12):
    c = QColor(colour)
    return any(abs(r - c.red()) + abs(g - c.green()) + abs(b - c.blue()) <= tol for r, g, b in found)


def drawn(chart, width=560):
    chart.resize(width, chart.height())
    return chart.grab().toImage()


def test_line_without_data_or_with_one_point_says_why_and_draws_no_line(qapp):
    from aikit import theme
    from aikit.charts import LineChart
    good = theme.palette("dark")["good"]
    for pts in ([], [(1, 0.5)]):
        c = LineChart("Доля", "Сыграйте две партии")
        c.set_points(pts)
        img = drawn(c)
        assert c.shown_empty, pts
        assert not near(good, colours(img), 30), "одна точка не должна рисовать график"
    c = LineChart("Доля", "Сыграйте две партии")
    c.set_points([(1, 0.2), (2, 0.6)])
    img = drawn(c)
    assert not c.shown_empty and near(good, colours(img))


def test_bar_without_groups_is_a_stub(qapp):
    from aikit.charts import BarChart
    c = BarChart("Итоги", "Здесь будут итоги")
    c.set_data([], [("победы", "good", [])])
    drawn(c)
    assert c.shown_empty
    c.set_data(["Новичок"], [("победы", "good", [0.5])])
    drawn(c)
    assert not c.shown_empty


@pytest.mark.parametrize("lang", ["ru", "en"])
@pytest.mark.parametrize("width", [330, 560, 900])
def test_standard_charts_keep_all_labels(qapp, lang, width):
    from aikit.charts import GameCharts
    for score in (None, "score"):
        g = GameCharts(LEVELS, score_key=score, learning=True, passport=True)
        learning = [("лучший" if lang == "ru" else "best", "good", [(k * 5000, k * k * 31.5) for k in range(60)]),
                    ("средний" if lang == "ru" else "mean", "muted", [(k * 5000, k * k * 20.0) for k in range(60)])]
        passport = ([NAMES[lang][lv] for lv in LEVELS],
                    [("против случайного бота", "good", [0.5, 0.8, 0.97]), ("против жадного", "accent", [0.2, 0.4, 0.6])])
        for data in (games(), []):
            g.refresh(data, lang, NAMES[lang], learning=learning if data else None,
                      passport=passport if data else None)
            for c in g.charts():
                drawn(c, width)
                assert c.clipped == [], (type(c).__name__, c.title, c.clipped)
                assert c.shown_empty == (not data)


def test_clipping_is_noticed(qapp):
    """Закон выше не пустой: длинная подпись попадает в clipped."""
    from aikit.charts import BarChart, LineChart
    c = LineChart("Очень длинный заголовок графика, который в узкую карточку никак не войдёт", "x")
    c.set_points([(1, 0.1), (2, 0.2)])
    drawn(c, 280)
    assert c.clipped
    b = BarChart("Итоги", "x")
    b.set_data(["Противник-с-невероятно-длинным-названием"] * 6, [("победы", "good", [0.5] * 6)])
    drawn(b, 300)
    assert b.clipped


def test_long_legend_moves_to_second_line_instead_of_cutting_title(qapp):
    from aikit.charts import LineChart
    c = LineChart("Доля выигранных раундов по матчам", "x", names=("последние двадцать", "за всё время"))
    c.set_points([(1, 0.1), (2, 0.2)], [(1, 0.3), (2, 0.4)])
    drawn(c, 360)
    assert c.clipped == []


def test_big_numbers_fit_left_margin(qapp):
    from aikit.charts import LineChart
    c = LineChart("Очки", "x", percent=False, y_label="очки")
    c.set_points([(1, 0), (2, 1250000), (3, 980000)])
    drawn(c, 330)
    assert c.clipped == []


def test_theme_changes_card_colour(qapp):
    from aikit import theme
    from aikit.charts import LineChart
    c = LineChart("Доля", "x")
    c.set_points([(1, 0.1), (2, 0.9)])
    for name in ("dark", "light"):
        c.set_theme(name)
        img = drawn(c)
        assert img.pixelColor(img.width() - 8, 120) == QColor(theme.palette(name)["surface"])


def test_grid_two_columns_wide_one_narrow_and_nothing_overlaps_in_scroll_area(qapp):
    from aikit.charts import GameCharts
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(QLabel("сверху"))
    grid = GameCharts(LEVELS, learning=True, passport=True)
    grid.refresh(games(), "ru", NAMES["ru"])
    lay.addWidget(grid)
    below = QLabel("снизу")
    lay.addWidget(below)
    lay.addStretch()
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(page)
    for width, cols in ((1000, 2), (420, 1), (1000, 2)):
        area.resize(width, 700)
        area.show()
        qapp.processEvents()
        assert grid.columns(grid.width()) == cols
        assert page.width() <= area.viewport().width() + 1, "сетка не должна держать страницу широкой"
        rects = [c.geometry() for c in grid.charts()]
        for i, a in enumerate(rects):
            assert a.right() <= grid.width()
            for b in rects[i + 1:]:
                assert not a.intersects(b)
        bottom = max(r.bottom() for r in rects)
        assert grid.height() >= bottom
        assert below.geometry().top() >= grid.geometry().top() + bottom
    area.close()


def test_grid_tops_of_a_row_are_aligned(qapp):
    from aikit.charts import GameCharts
    grid = GameCharts(LEVELS)
    grid.resize(1000, grid.heightForWidth(1000))
    grid.show()
    qapp.processEvents()
    tops = sorted({c.geometry().top() for c in grid.charts()})
    assert len(tops) == 2
    grid.close()


def test_scales():
    from aikit.charts import clean, group, x_ticks, y_scale
    lo, hi, ticks, step = y_scale(3, 97)
    assert lo == 0 and hi >= 97 and step in (20, 25)
    assert x_ticks(1, 60, 4)[-1] <= 60 and len(x_ticks(1, 60, 4)) <= 4
    assert clean([(2, 1), (1, float("nan")), ("a", 1), (1, 2), (True, 1)]) == [(1.0, 2.0), (2.0, 1.0)]
    assert group(1250000) == "1 250 000"


def test_texts_have_both_languages():
    from aikit.charts import TEXTS, texts
    assert set(TEXTS["ru"]) == set(TEXTS["en"])
    assert texts("de") == TEXTS["ru"]


def test_flat_zero_line_stays_above_zero_and_integer_steps():
    """Кадр RockPaperAi: серия побед из одних нулей рисовалась на шкале -0,50..0,50."""
    from aikit.charts import y_scale
    lo, hi, ticks, step = y_scale(0, 0)
    assert lo == 0 and hi > 0 and min(ticks) >= 0
    lo, hi, ticks, step = y_scale(0, 2, integer=True)
    assert step >= 1 and all(float(v).is_integer() for v in ticks)
    lo, hi, ticks, step = y_scale(-3, -3)
    assert lo < -3 < hi


def test_numbers_in_legend_have_no_trailing_zero():
    """Кадр SaperAi: «последняя 86.0 с» - лишний ноль."""
    from aikit.charts import num
    assert num(86.04, " с") == "86 с"
    assert num(86.4) == "86.4" and num(3.25) == "3.25" and num(12500) == "12 500" and num(-4) == "-4"
