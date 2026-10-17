"""Законы самой мутационной проверки (tools/mutate.py, tools/mutants.py).

- Каждая строка «было» есть в своём файле ровно один раз: иначе мутант не применяется,
  прогон пишет «строка найдена 0 раз», и в итоге его легко принять за пойманного (так было
  с «ui: показ не останавливается» в RockPaperAi и двумя мутантами Дурака - строки
  устарели после правок).
- Файлы проверок мутанта существуют.
- Прогон идёт через общий aikit.mutate: сначала проверки БЕЗ мутанта, красные - стоп
  (17.10: закон с неверными данными был красным и без мутанта и «ловил» всех)."""
import os
import runpy

from aikit import mutate as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mutants():
    ns = runpy.run_path(os.path.join(ROOT, "tools", "mutate.py"), run_name="mutants_table")
    return ns, ns["MUTANTS"] + ns["load_more"]()


def test_every_mutant_line_is_found_exactly_once():
    _, ms = mutants()
    assert ms
    bad = []
    for name, rel, old, new, tests in ms:
        with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as f:
            count = f.read().count(old)
        if count != 1 or old == new:
            bad.append((name, count))
    assert bad == []
    names = [m[0] for m in ms]
    assert len(names) == len(set(names))


def test_mutant_test_files_exist():
    _, ms = mutants()
    for name, _, _, _, tests in ms:
        for part in tests.split():
            if part.startswith("tests"):
                assert os.path.exists(os.path.join(ROOT, part.split("::")[0])), (name, part)


def test_run_checks_baseline_first():
    """main игры зовёт aikit.mutate; красные без мутанта проверки - код 2, файл не тронут."""
    ns, ms = mutants()
    calls = []

    def fake_main(root, chosen, argv, python=None, **kw):
        calls.append((root, len(chosen), list(argv)))
        return M.main(root, chosen[:1], argv, python, out=lambda *_: None, check=lambda *a: False)

    # старый прогон без aikit.mutate тут не зовётся: он по-настоящему правил бы файлы
    assert ns["main"].__globals__.get("run_all") is M.main
    ns["main"].__globals__["run_all"] = fake_main
    rel = ms[0][1]
    with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as f:
        before = f.read()
    assert ns["main"](["mutate.py"]) == 2
    assert calls == [(ROOT, len(ms), [])]
    with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as f:
        assert f.read() == before
