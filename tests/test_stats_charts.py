"""Графики статистики из общего aikit.charts (правило автора 10.10 - графики во всех играх с ИИ).

Законы: на странице статистики графики aikit; партия против ИИ пишется в журнал (уровень,
режим, итог, выстрелы; выстрелы до победы - только у победы), показ «ИИ против ИИ» - нет; без
партий - заглушки словами; подписи целы (chart.clipped пуст) в обеих темах, на обоих языках, в
широком и самом узком окне; рекорд - наименьшее число выстрелов до победы."""
from aikit.charts import ChartCard, all_charts
from tests.test_ui import HAND, app, play_out, win  # noqa: F401 - фикстуры окна


def labels_intact(app, win, g):
    for theme in ("dark", "light"):
        for lang in ("ru", "en"):
            win.ctx.set_theme(theme)
            win.ctx.set_lang(lang)
            for width in (1400, 3840, win.minimumWidth()):
                win.resize(width, 820)
                app.processEvents()
                for c in all_charts(g.stats):
                    c.grab()
                    assert c.clipped == [], (theme, lang, width, c.title, c.clipped)
                    assert c.overlaps() == [], (theme, lang, width, c.title, c.overlaps())
                    assert c.theme == theme
    win.ctx.set_theme("dark")
    win.ctx.set_lang("ru")


def test_charts_are_aikit_and_stubs_without_games(app, win):
    g = win.game
    g.show_page("stats")
    charts = all_charts(g.stats)
    assert len(charts) >= 5 and all(isinstance(c, ChartCard) for c in charts)
    ch = g.stats.charts
    for c in (ch.share, ch.by_level, ch.length, ch.records):
        c.grab()
        assert c.shown_empty and c.empty_text, c.title
    ch.passport.grab()
    assert not ch.passport.shown_empty and not ch.passport.percent
    labels_intact(app, win, g)


def test_games_go_to_the_log_and_charts(app, win):
    g = win.game
    for level, seed, cheat in (("novice", 5, True), ("strong", 3, False), ("novice", 6, True)):
        g.change("level", level)
        g.start_battle(seed=seed, fleet=HAND)
        play_out(app, g, cheat=cheat)
    games = g.history.games
    assert [x["level"] for x in games] == ["novice", "strong", "novice"]
    assert all(x["variant"] == "classic" and x["shots"] > 0 for x in games)
    assert games[0]["outcome"] == "win" and games[0]["win_shots"] == games[0]["shots"] == 20
    assert all(("win_shots" in x) == (x["outcome"] == "win") for x in games)
    g.show_page("stats")
    ch = g.stats.charts
    for c in (ch.share, ch.by_level, ch.length, ch.records):
        c.grab()
        assert not c.shown_empty, c.title
    wins = [x["win_shots"] for x in games if "win_shots" in x]
    assert [y for _, y in ch.records.second] == [min(wins[:i + 1]) for i in range(len(wins))]
    labels_intact(app, win, g)


def test_demo_stays_out_of_the_log(app, win):
    g = win.game
    g.change("mode", "demo")
    g.change("level", "medium")
    g.play_clicked()
    from tests.test_ui import wait
    assert wait(app, lambda: g.session.over, 60)
    assert g.history.games == []
    g.change("mode", "play")


def test_record_is_the_fewest_shots_to_win(app, win):
    g = win.game
    for shots, outcome in ((60, "win"), (70, "loss"), (40, "win"), (50, "win")):
        game = {"level": "strong", "variant": "classic", "outcome": outcome, "shots": shots}
        if outcome == "win":
            game["win_shots"] = shots
        g.history.record(game)
    g.show_page("stats")
    rec = g.stats.charts.records
    assert [y for _, y in rec.points] == [60, 40, 50]
    assert [y for _, y in rec.second] == [60, 40, 40]
