"""aikit.menu: живой фон идёт только видимым и не на паузе, заголовок ужимается, законы раскладки
ловят обрезку, выход за край и наложение."""
import time

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from aikit.menu import SIZES, Backdrop, Title, fill_share, layout_problems


def pump(qapp, seconds):
    end = time.time() + seconds
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.005)


class Scene(Backdrop):
    def __init__(self):
        super().__init__()
        self.seen = []

    def paint_scene(self, p, w, h, t):
        self.seen.append(t)
        super().paint_scene(p, w, h, t)


def test_backdrop_runs_only_while_visible(qapp):
    s = Scene()
    s.resize(200, 100)
    assert not s.running()
    s.show()
    assert s.running()
    pump(qapp, 0.25)
    t1 = s.t
    assert t1 > 0.05 and s.frames > 1
    s.hide()
    assert not s.running()
    pump(qapp, 0.2)
    assert s.t == t1                      # скрытый фон не тикает
    s.show()
    s.close()


def test_backdrop_pause_resume_and_freeze(qapp):
    s = Scene()
    s.resize(200, 100)
    s.show()
    s.pause()
    assert not s.running()
    t0 = s.t
    pump(qapp, 0.15)
    assert s.t == t0
    s.resume()
    assert s.running()
    s.set_time(3.5)
    assert not s.running() and s.t == 3.5
    s.repaint()
    assert s.seen[-1] == 3.5
    s.set_time(None)
    assert s.running()
    s.close()


def test_backdrop_time_does_not_jump_after_a_long_frame(qapp):
    s = Scene()
    s.show()
    s._clock.restart()
    time.sleep(0.4)
    s._advance()
    assert s.t <= Backdrop.MAX_STEP + 1e-9
    s.close()


def test_title_shrinks_to_fit_and_reports_clipping(qapp):
    t = Title("Segoe UI", 60, spacing=0.1, min_px=20)
    t.setText("A rather long English title")
    t.resize(2000, 80)
    assert t.fitted_px() == 60 and not t.clipped()
    t.resize(300, 80)
    assert 20 <= t.fitted_px() < 60
    assert t.text_width(t.fitted_px()) <= 300 or t.fitted_px() == 20
    t.resize(60, 80)
    assert t.clipped()                    # даже 20 px не влезает
    t.setText("")
    assert not t.clipped()


def _page(w, h):
    page = QWidget()
    page.resize(w, h)
    lay = QVBoxLayout(page)
    a = QPushButton("Играть", page)
    b = QLabel("Подпись", page)
    lay.addWidget(a)
    lay.addWidget(b)
    page.show()
    return page, a, b


def test_layout_problems_clean_page(qapp):
    page, a, b = _page(400, 300)
    qapp.processEvents()
    assert layout_problems(page) == []
    page.close()


def test_layout_problems_catches_edge_overlap_and_clipping(qapp):
    page = QWidget()
    page.resize(300, 200)
    out = QPushButton("За краем", page)
    out.setGeometry(250, 10, 120, 30)
    x = QLabel("Наложение", page)
    x.setGeometry(10, 100, 120, 30)
    y = QLabel("Второй", page)
    y.setGeometry(60, 110, 120, 30)
    short = QPushButton("Очень длинная надпись на кнопке", page)
    short.setGeometry(10, 150, 60, 30)
    page.show()
    qapp.processEvents()
    found = layout_problems(page)
    assert any("За краем" in s and "за краем" in s for s in found)
    assert any("налезает" in s for s in found)
    assert any("не влез" in s and "Очень длинная" in s for s in found)
    page.close()


def test_layout_problems_sees_title_clipping(qapp):
    page = QWidget()
    page.resize(200, 100)
    t = Title("Segoe UI", 40, min_px=30, parent=page)
    t.setText("Слишком длинный заголовок")
    t.setGeometry(0, 0, 200, 60)
    page.show()
    qapp.processEvents()
    assert any("Title" in s for s in layout_problems(page))
    page.close()


def test_fill_share_and_sizes(qapp):
    assert SIZES[0] == (900, 640) and SIZES[-1] == (3840, 2160)
    root = QWidget()
    root.resize(1000, 100)
    child = QWidget(root)
    child.resize(950, 10)
    assert abs(fill_share(child, root) - 0.95) < 1e-9


def test_checked_bold_button_needs_room_for_bold_text(qapp):
    """Выбранная кнопка жирная (таблица стилей), Qt считает ширину по обычному - закон видит
    обрезку жирной надписи, а fit_segments даёт ей место при любом кегле (Дурак 4K, 17.10)."""
    from aikit.widgets import fit_segments, segmented
    page = QWidget()
    page.resize(900, 200)
    box, buttons = segmented({"a": "Medium", "b": "Strong"}, lambda v: None)
    box.setParent(page)
    page.setStyleSheet("QPushButton#seg { font-family: Georgia; font-size: 34px; padding: 6px 29px; }"
                       "QPushButton#seg:checked { font-weight: 700; }")
    buttons["a"].setChecked(True)
    for b in buttons.values():
        b.setMinimumWidth(0)
        b.ensurePolished()
    lay = box.layout()
    page.show()
    qapp.processEvents()
    for b in buttons.values():
        b.setFixedWidth(b.sizeHint().width())       # ровно по обычному шрифту - жирный не влезет
    qapp.processEvents()
    assert any("Medium" in s for s in layout_problems(page))
    for b in buttons.values():
        b.setMinimumWidth(0)
        b.setMaximumWidth(16777215)
    fit_segments(buttons)
    lay.activate()
    box.adjustSize()
    qapp.processEvents()
    assert layout_problems(page) == []
    page.close()
