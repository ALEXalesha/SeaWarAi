"""Мутационная проверка: нарочно ломает продукт и смотрит, что проверки это ловят.

    python tools/mutate.py            # все мутанты
    python tools/mutate.py rules      # только с этим словом в имени

Каждый мутант - замена строки в файле. Файл правится на месте, гоняются указанные
проверки, затем файл восстанавливается (в finally - и при Ctrl+C). Мутант «выжил», если
проверки остались зелёными: значит, этот кусок продукта не проверен.

Прогон - общий aikit.mutate: сначала те же проверки БЕЗ мутанта (красные - прогон
останавливается, код 2: «пойман» на уже красных проверках ничего не значит; так закон с
неверными данными «ловил» мутантов графиков 17.10), зависание дольше 900 с - пойман.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from aikit.mutate import main as run_all  # noqa: E402

# (имя, файл, было, стало, проверки)
MUTANTS = []


def load_more():
    """Мутанты движка и ИИ лежат рядом, чтобы список не разрастался в одном месте."""
    extra = os.path.join(ROOT, "tools", "mutants.py")
    if os.path.exists(extra):
        ns = {}
        with open(extra, encoding="utf-8") as f:
            exec(f.read(), ns)
        return ns["MUTANTS"]
    return []


def main(argv):
    return run_all(ROOT, MUTANTS + load_more(), argv[1:], python=sys.executable)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
