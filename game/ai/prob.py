"""Карта вероятностей: в какой неизвестной клетке вероятнее всего стоит корабль.

Рассматриваются все расстановки оставшихся кораблей, согласные с тем, что видно:
- корабли не стоят на промахах и на потопленных, не касаются потопленных и друг друга
  (по правилу касания партии);
- каждое попадание накрыто каким-то кораблём на плаву, и ни один корабль на плаву не
  состоит целиком из попаданий (иначе он уже был бы потоплен);
- два попадания рядом - один корабль: разные корабли касались бы друг друга.

Вес расстановки - произведение априорных весов мест её кораблей (привычки игрока; без них
все веса 1, и все расстановки равновероятны). Вероятность клетки - доля веса расстановок,
где в ней корабль.

Два способа счёта:
- **точный перебор**, когда раскладок мало (оценка сверху не больше exact_limit): корабли по
  убыванию длины, одинаковые - по возрастанию номера места, клетки - битами числа;
- **Монте-Карло с весами** (последовательная выборка по значимости) иначе: S раскладок сразу,
  массивами numpy. Сначала накрывается младшее ненакрытое попадание - любым подходящим
  кораблём, потом остальные корабли по убыванию длины. Вес выборки - произведение сумм
  весов допустимых мест на каждом шаге; для k одинаковых кораблей второй фазы он делится
  на k! (одну раскладку дают k! порядков). Так оценка несмещённая для того же распределения,
  что и в точном переборе, - это проверяет тест.

Проверка «не пересекается» - умножение матрицы занятых клеток на матрицу мест кораблей в
float32: суммы нулей и единиц точные, поэтому итог не зависит от числа потоков BLAS.
"""
import math
from functools import lru_cache

import numpy as np

from game.core.battle import HIT, MISS, SUNK
from game.core.rules import SIZE, halo, neighbors, placements

DEFAULT_SAMPLES = 400        # 400 и 3000 выборок дают одну силу (56.8 и 56.0 выстрела), 400 - вдвое быстрее 800
EXACT_LIMIT = 20000


class Geometry:
    """Места кораблей каждой длины на поле: клетки, кольцо вокруг, биты."""

    def __init__(self, size, corners, lengths):
        n = size * size
        self.size, self.corners, self.n = size, corners, n
        self.places, self.cells, self.halo, self.ring, self.bits, self.halobits = {}, {}, {}, {}, {}, {}
        for L in lengths:
            ps = placements(L, size)
            cells = np.zeros((len(ps), n), dtype=bool)
            hal = np.zeros((len(ps), n), dtype=bool)
            for i, p in enumerate(ps):
                cells[i, list(p)] = True
                hal[i, list(halo(p, corners, size))] = True
            self.places[L] = ps
            self.cells[L] = cells
            self.halo[L] = hal
            self.ring[L] = hal & ~cells
            self.bits[L] = [sum(1 << x for x in p) for p in ps]
            self.halobits[L] = [sum(1 << x for x in halo(p, corners, size)) for p in ps]


@lru_cache(maxsize=16)
def geometry(size=SIZE, corners=False, lengths=(1, 2, 3, 4)):
    return Geometry(size, corners, tuple(sorted(set(lengths))))


def _setup(obs, prior):
    size, n = obs.size, obs.size * obs.size
    grid = np.array(obs.grid, dtype=np.int8)
    sunk = grid == SUNK
    blocked = (grid == MISS) | sunk
    for x in np.nonzero(sunk)[0]:
        blocked[neighbors(int(x), obs.corners, size)] = True
    hits = grid == HIT
    types = sorted(set(obs.remaining), reverse=True)
    counts = [obs.remaining.count(L) for L in types]
    geo = geometry(size, obs.corners, tuple(sorted(set(obs.remaining)) or (1,)))
    allowed = {}
    for L in types:
        c = geo.cells[L]
        ok = ~(c & blocked).any(1) & (c & ~hits).any(1)
        idx = np.nonzero(ok)[0]
        w = np.ones(len(idx)) if prior is None or L not in prior else np.asarray(prior[L], float)[idx]
        allowed[L] = (idx, w)
    return geo, grid, blocked, hits, types, counts, allowed, n


def estimate_count(obs, prior=None):
    """Оценка сверху числа раскладок: произведение C(мест, кораблей) по длинам."""
    geo, grid, blocked, hits, types, counts, allowed, n = _setup(obs, prior)
    total = 1
    for L, k in zip(types, counts):
        total *= math.comb(len(allowed[L][0]), k)
    return total


def exact_map(obs, prior=None, node_limit=2_000_000):
    """Точная карта перебором. Возвращает (вероятности по клеткам, число раскладок с весом > 0)
    или None, если перебор упёрся в node_limit."""
    geo, grid, blocked, hits, types, counts, allowed, n = _setup(obs, prior)
    if not types:
        return np.zeros(n), 1
    hitbits = sum(1 << int(x) for x in np.nonzero(hits)[0])
    blockbits = sum(1 << int(x) for x in np.nonzero(blocked)[0])
    slots = [L for L, k in zip(types, counts) for _ in range(k)]
    rest_len = [sum(slots[i:]) for i in range(len(slots) + 1)]
    acc = {L: np.zeros(len(geo.places[L])) for L in types}
    lists = {L: [(int(i), geo.bits[L][i], geo.halobits[L][i], float(w)) for i, w in zip(*allowed[L])]
             for L in types}
    state = {"total": 0.0, "leaves": 0, "nodes": 0}
    chosen = []

    def rec(slot, start, forb, uncovered, weight):
        state["nodes"] += 1
        if state["nodes"] > node_limit:
            raise _Abort
        if slot == len(slots):
            if uncovered == 0:
                state["total"] += weight
                state["leaves"] += 1
                for L, i in chosen:
                    acc[L][i] += weight
            return
        if bin(uncovered).count("1") > rest_len[slot]:
            return
        L = slots[slot]
        same_next = slot + 1 < len(slots) and slots[slot + 1] == L
        for j in range(start, len(lists[L])):
            i, b, hb, w = lists[L][j]
            if b & forb:
                continue
            unc = uncovered & ~b
            if unc & hb:                     # ненакрытое попадание у борта - это был бы один корабль
                continue
            chosen.append((L, i))
            rec(slot + 1, j + 1 if same_next else 0, forb | hb, unc, weight * w)
            chosen.pop()

    try:
        rec(0, 0, blockbits, hitbits, 1.0)
    except _Abort:
        return None
    p = np.zeros(n)
    if state["total"] <= 0:
        return p, 0
    for L in types:
        p += acc[L] @ geo.cells[L]
    return p / state["total"], state["leaves"]


class _Abort(Exception):
    pass


def mc_map(obs, rng, samples=DEFAULT_SAMPLES, prior=None, by_length=False):
    """Карта Монте-Карло. Возвращает (вероятности, эффективное число выборок), а с by_length -
    ещё {длина: вероятность корабля этой длины в клетке}."""
    geo, grid, blocked, hits, types, counts, allowed, n = _setup(obs, prior)
    if not types:
        return (np.zeros(n), float(samples), {}) if by_length else (np.zeros(n), float(samples))
    S = samples
    T = len(types)
    F = np.repeat(blocked[None, :], S, axis=0)
    occ = np.zeros((S, n), dtype=np.int8)       # длина корабля в клетке, 0 - пусто
    unc = np.repeat(hits[None, :], S, axis=0)
    rem = np.tile(np.array(counts, dtype=np.int64), (S, 1))
    logw = np.zeros(S)
    alive = np.ones(S, dtype=bool)

    # все допустимые места всех длин подряд - для фазы попаданий
    cat_idx, cat_type, cat_w = [], [], []
    for t, L in enumerate(types):
        idx, w = allowed[L]
        cat_idx.append(idx)
        cat_type.append(np.full(len(idx), t))
        cat_w.append(w)
    cat_type = np.concatenate(cat_type)
    cat_w = np.concatenate(cat_w)
    C_all = np.concatenate([geo.cells[L][allowed[L][0]] for L in types])
    H_all = np.concatenate([geo.halo[L][allowed[L][0]] for L in types])
    R_all = np.concatenate([geo.ring[L][allowed[L][0]] for L in types])
    Cf = C_all.T.astype(np.float32)
    Rf = R_all.T.astype(np.float32)

    def pick(rows, weights):
        tot = weights.sum(1)
        ok = tot > 0
        r = rng.random(len(rows)) * tot
        choice = (np.cumsum(weights, axis=1) < r[:, None]).sum(1)
        choice = np.minimum(choice, weights.shape[1] - 1)
        return ok, choice, tot

    if hits.any():
        for _ in range(int(hits.sum())):
            need = alive & unc.any(1)
            if not need.any():
                break
            rows = np.nonzero(need)[0]
            target = unc[rows].argmax(1)
            overlap = F[rows].astype(np.float32) @ Cf
            touch = unc[rows].astype(np.float32) @ Rf
            valid = (overlap == 0) & (touch == 0) & C_all.T[target] & (rem[rows][:, cat_type] > 0)
            ok, choice, tot = pick(rows, valid * cat_w)
            alive[rows[~ok]] = False
            rows, choice, tot = rows[ok], choice[ok], tot[ok]
            F[rows] |= H_all[choice]
            occ[rows] += C_all[choice] * np.array(types, dtype=np.int8)[cat_type[choice]][:, None]
            unc[rows] &= ~C_all[choice]
            rem[rows, cat_type[choice]] -= 1
            logw[rows] += np.log(tot)
        alive &= ~unc.any(1)

    for t, L in enumerate(types):
        idx, w = allowed[L]
        if len(idx) == 0:
            alive &= rem[:, t] == 0
            continue
        Cl = geo.cells[L][idx]
        Hl = geo.halo[L][idx]
        Clf = Cl.T.astype(np.float32)
        logw -= np.array([math.lgamma(k + 1) for k in rem[:, t]])
        while True:
            act = alive & (rem[:, t] > 0)
            if not act.any():
                break
            rows = np.nonzero(act)[0]
            valid = (F[rows].astype(np.float32) @ Clf) == 0
            ok, choice, tot = pick(rows, valid * w)
            alive[rows[~ok]] = False
            rem[rows[~ok], t] = 0
            rows, choice, tot = rows[ok], choice[ok], tot[ok]
            F[rows] |= Hl[choice]
            occ[rows] += Cl[choice] * np.int8(L)
            rem[rows, t] -= 1
            logw[rows] += np.log(tot)

    if not alive.any():
        return (None, 0.0, None) if by_length is True else (None, 0.0)
    lw = logw[alive]
    wts = np.exp(lw - lw.max())
    occ = occ[alive]
    p = (wts[:, None] * (occ > 0)).sum(0) / wts.sum()
    ess = float(wts.sum() ** 2 / (wts ** 2).sum())
    if by_length == "raw":
        return occ, wts
    if by_length:
        return p, ess, {L: (wts[:, None] * (occ == L)).sum(0) / wts.sum() for L in types}
    return p, ess


def probability_map(obs, rng, samples=DEFAULT_SAMPLES, prior=None, exact_limit=EXACT_LIMIT):
    """Карта и как она посчитана: (p, 'exact' | 'mc' | 'density', число раскладок или ESS)."""
    if estimate_count(obs, prior) <= exact_limit:
        res = exact_map(obs, prior)
        if res is not None and res[1] > 0:
            return res[0], "exact", float(res[1])
    for k in (1, 4):
        p, ess = mc_map(obs, rng, samples * k, prior)
        if p is not None:
            return p, "mc", ess
    return density_map(obs, prior), "density", 0.0


def density_map(obs, prior=None):
    """Запасной вариант на случай, когда выборка не нашла ни одной раскладки: каждый корабль
    отдельно, без учёта соседей. Вероятностью не является - только порядок клеток."""
    geo, grid, blocked, hits, types, counts, allowed, n = _setup(obs, prior)
    p = np.zeros(n)
    for L, k in zip(types, counts):
        idx, w = allowed[L]
        c = geo.cells[L][idx]
        bonus = 1 + 10 * (c & hits).sum(1)
        p += k * ((w * bonus) @ c)
    return p / max(p.max(), 1e-12)


def best_cell(p, obs, rng):
    """Неизвестная клетка с наибольшей вероятностью; равные - случайно по зерну."""
    unknown = np.array(obs.unknown())
    if len(unknown) == 0:
        raise ValueError("стрелять некуда")
    vals = p[unknown]
    top = vals.max()
    cand = unknown[vals >= top - 1e-9 * max(top, 1e-12)]
    return int(cand[int(rng.integers(len(cand)))])


def sample_fleet(obs, rng, node_limit=200_000):
    """Одна расстановка кораблей на плаву, согласная с наблюдением (не равновероятная -
    случайный перебор до первой подходящей). Сначала накрываются попадания, потом ставятся
    остальные корабли по убыванию длины. Для тестов честности. None - не нашлось."""
    geo, grid, blocked, hits, types, counts, allowed, n = _setup(obs, None)
    if not types:
        return []
    hitbits = sum(1 << int(x) for x in np.nonzero(hits)[0])
    forb0 = sum(1 << int(x) for x in np.nonzero(blocked)[0])
    nodes = [0]

    def options(L, forb, uncovered, must=0):
        idx = allowed[L][0]
        for j in rng.permutation(len(idx)):
            i = int(idx[j])
            b, hb = geo.bits[L][i], geo.halobits[L][i]
            if b & forb or (must and not b & must):
                continue
            unc = uncovered & ~b
            if unc & hb:
                continue
            yield L, i, hb, unc

    def rec(left, forb, uncovered, chosen):
        nodes[0] += 1
        if nodes[0] > node_limit:
            return None
        if not any(left.values()):
            return list(chosen) if uncovered == 0 else None
        if uncovered:
            target = uncovered & -uncovered          # младшее ненакрытое попадание
            gens = [options(L, forb, uncovered, target) for L in left if left[L]]
            opts = [o for g in gens for o in g]
            opts = [opts[k] for k in rng.permutation(len(opts))]
        else:
            L = max(L for L in left if left[L])
            opts = options(L, forb, uncovered)
        for L, i, hb, unc in opts:
            left[L] -= 1
            got = rec(left, forb | hb, unc, chosen + [geo.places[L][i]])
            left[L] += 1
            if got is not None:
                return got
        return None

    return rec(dict(zip(types, counts)), forb0, hitbits, [])


def ships_from_cells(occupied, size=SIZE):
    """Корабли из набора занятых клеток: корабли сторонами не касаются, поэтому каждая
    связная по сторонам группа - один корабль."""
    left = set(int(x) for x in occupied)
    ships = []
    while left:
        start = min(left)
        group, stack = {start}, [start]
        left.discard(start)
        while stack:
            x = stack.pop()
            for y in neighbors(x, True, size):
                if y in left:
                    left.discard(y)
                    group.add(y)
                    stack.append(y)
        ships.append(tuple(sorted(group)))
    return sorted(ships, key=lambda s: (-len(s), s))


def uniform_fleet(rng, corners=False, fleet=None, samples=256):
    """Случайная расстановка, где все расстановки по правилам почти равновероятны: выборка
    с весами (как в карте вероятностей) и одна раскладка из неё с вероятностью по весу.
    Простая расстановка «корабль за кораблём» (rules.random_fleet) не такая: она реже ставит
    корабли к краям, чем их там бывает среди всех расстановок."""
    from game.core.battle import Observation
    from game.core.rules import FLEET
    fleet = tuple(sorted(fleet or FLEET, reverse=True))
    obs = Observation(tuple([0] * (SIZE * SIZE)), fleet, corners)
    while True:
        res = mc_map(obs, rng, samples, by_length="raw")
        if res[0] is None:
            continue
        occ, wts = res
        k = int(np.searchsorted(np.cumsum(wts), rng.random() * wts.sum(), side="right"))
        k = min(k, len(wts) - 1)
        return ships_from_cells(np.nonzero(occ[k])[0])


def uniform_fleets(rng, k, corners=False, fleet=None, samples=512):
    """k почти равновероятных расстановок из одной выборки с весами (быстрее, чем k раз
    uniform_fleet). Повторы возможны, если выборка мала."""
    from game.core.battle import Observation
    from game.core.rules import FLEET
    fleet = tuple(sorted(fleet or FLEET, reverse=True))
    obs = Observation(tuple([0] * (SIZE * SIZE)), fleet, corners)
    while True:
        occ, wts = mc_map(obs, rng, samples, by_length="raw")
        if occ is not None:
            break
    cum = np.cumsum(wts)
    picks = np.minimum(np.searchsorted(cum, rng.random(k) * cum[-1], side="right"), len(wts) - 1)
    return [ships_from_cells(np.nonzero(occ[int(j)])[0]) for j in picks]
