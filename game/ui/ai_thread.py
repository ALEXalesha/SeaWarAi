"""Выстрел ИИ и «Мысли ИИ» в отдельном потоке: окно не подвисает.

Каждый запрос получает номер (token); ответ со старым номером (партию начали заново, вышли
в меню) выбрасывается. Остановка - флагом; при закрытии окна потоки ждут не дольше 2 секунд
(контракт aikit). В поток уходит только наблюдение (Observation) - не флот игрока.
"""
import threading
import time

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from game.ai.agents import make_agent


_ORPHANS = []
_UNDERTAKER = None


class _Undertaker(QObject):
    """Живёт в потоке окна: сигнал finished сироты приходит сюда очередью, а не в сам поток."""

    def bury(self):
        for j in list(_ORPHANS):
            if j.isFinished():
                j.wait()
                _ORPHANS.remove(j)


def _undertaker():
    global _UNDERTAKER
    if _UNDERTAKER is None:
        _UNDERTAKER = _Undertaker()
    return _UNDERTAKER


class _Job(QThread):
    done = Signal(int, str, object)

    def __init__(self, token, kind, fn):
        super().__init__()
        self.token = token
        self.kind = kind
        self.fn = fn
        self.stop_event = threading.Event()

    def run(self):
        try:
            payload = self.fn()
        except Exception as e:  # noqa: BLE001 - ошибку покажет окно
            payload = e
        if not self.stop_event.is_set():
            self.done.emit(self.token, self.kind, payload)


class AiController(QObject):
    """request_move(token, obs, level, seed, habits, parity) -> ready(token, 'move', {'cell', 'map'});
    request_thoughts(token, obs, level, seed, habits) -> ready(token, 'thoughts', {'map', 'method'})."""

    ready = Signal(int, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.jobs = []

    def _start(self, token, kind, fn):
        self._reap()
        # Без родителя: поток живёт, пока на него есть ссылка в self.jobs (или в _ORPHANS).
        # Дочерний QThread разрушался вместе со старым окном, когда до окна добирался сборщик
        # мусора, - а разрушение ещё работающего QThread это qFatal «Destroyed while thread is
        # still running» и падение всей программы (CI на Gitea, c93c07f; тот же урок у DurakAi).
        job = _Job(token, kind, fn)
        job.done.connect(self.ready)
        job.finished.connect(self._reap)        # слот контроллера: выполняется в потоке окна
        self.jobs.append(job)
        job.start()
        return job

    def _reap(self):
        """Кончившиеся потоки - из списка; последняя ссылка уходит, объект удаляется."""
        alive = []
        for j in self.jobs:
            if j.isFinished():
                j.wait()                        # поток вышел целиком, удалять безопасно
            elif j.isRunning():
                alive.append(j)
        self.jobs = alive

    def request_move(self, token, obs, level, seed, habits=None, parity=0):
        agent = make_agent(level, habits=habits, parity=parity)

        def fn():
            p = agent.think(obs, np.random.default_rng([seed, 1]))
            cell = agent.choose(obs, np.random.default_rng([seed, 2]))
            return {"cell": cell, "map": p, "method": getattr(agent, "last_method", None)}
        return self._start(token, "move", fn)

    def request_thoughts(self, token, obs, level, seed, habits=None, parity=0):
        agent = make_agent(level, habits=habits, parity=parity)

        def fn():
            p = agent.think(obs, np.random.default_rng([seed, 1]))
            return {"map": p, "method": getattr(agent, "last_method", None)}
        return self._start(token, "thoughts", fn)

    def cancel(self):
        for j in self.jobs:
            j.stop_event.set()

    def busy(self):
        self._reap()
        return bool(self.jobs)

    def shutdown(self, timeout_ms=2000):
        """Остановить расчёты и дождаться потоков (не дольше timeout_ms на всё). Не успевшие
        (машина перегружена) уходят в _ORPHANS: окно можно разрушать, поток доработает сам и
        только потом удалится. False - кто-то не успел."""
        self.cancel()
        deadline = time.monotonic() + timeout_ms / 1000
        for j in self.jobs:
            j.wait(max(0, int((deadline - time.monotonic()) * 1000)))
        self._reap()
        for j in self.jobs:
            j.done.disconnect(self.ready)
            _ORPHANS.append(j)
            j.finished.connect(_undertaker().bury)
        self.jobs = []
        _undertaker().bury()
        return not _ORPHANS
