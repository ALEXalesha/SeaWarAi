"""Поле, корабли и расстановка: чистый Python, без Qt.

Клетка - число r * size + c (r - строка 0..9 сверху, c - столбец 0..9 слева). Корабль -
кортеж клеток по возрастанию. Флот по русским правилам: 4, 3, 3, 2, 2, 2, 1, 1, 1, 1.

Правило касания. По умолчанию корабли не касаются друг друга даже углами: вокруг корабля
занято кольцо из 8 соседей каждой клетки. С опцией corners («классические»: углами можно)
занято только 4 соседа - сторонами касаться нельзя по-прежнему.
"""
from dataclasses import dataclass
from functools import lru_cache

SIZE = 10
FLEET = (4, 3, 3, 2, 2, 2, 1, 1, 1, 1)
LETTERS = {"ru": "АБВГДЕЖЗИК", "en": "ABCDEFGHIJ"}


@dataclass(frozen=True)
class Rules:
    corners: bool = False      # корабли могут касаться углами
    salvo: bool = False        # залп: за ход столько выстрелов, сколько своих кораблей на плаву


def rc(cell, size=SIZE):
    return divmod(cell, size)


def cell_name(cell, lang="ru", size=SIZE):
    r, c = rc(cell, size)
    return f"{LETTERS[lang][c]}{r + 1}"


def neighbors(cell, corners=False, size=SIZE):
    """Клетки, которых не может касаться другой корабль: 8 соседей, а с corners - 4."""
    r, c = rc(cell, size)
    out = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if (dr, dc) == (0, 0) or (corners and dr and dc):
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < size and 0 <= cc < size:
                out.append(rr * size + cc)
    return out


def halo(cells, corners=False, size=SIZE):
    """Клетки корабля и все клетки вокруг него, где другого корабля быть не может."""
    out = set(cells)
    for x in cells:
        out.update(neighbors(x, corners, size))
    return out


def ship_cells(r, c, length, horizontal, size=SIZE):
    """Клетки корабля от (r, c) вправо или вниз; None - если не помещается."""
    if not (0 <= r < size and 0 <= c < size) or length < 1:
        return None
    if horizontal:
        if c + length > size:
            return None
        return tuple(r * size + c + i for i in range(length))
    if r + length > size:
        return None
    return tuple((r + i) * size + c for i in range(length))


def placements(length, size=SIZE):
    """Все места корабля этой длины на пустом поле, без повторов (однопалубный - один раз)."""
    out = []
    for horizontal in ((True,) if length == 1 else (True, False)):
        for r in range(size):
            for c in range(size):
                s = ship_cells(r, c, length, horizontal, size)
                if s is not None:
                    out.append(s)
    return out


def is_straight(ship, size=SIZE):
    """Клетки идут подряд по одной строке или одному столбцу."""
    ship = sorted(ship)
    if not ship or len(set(ship)) != len(ship) or not all(0 <= x < size * size for x in ship):
        return False
    r0, c0 = rc(ship[0], size)
    if len(ship) == 1:
        return True
    return (ship == [r0 * size + c0 + i for i in range(len(ship))] and c0 + len(ship) <= size) or \
        ship == [(r0 + i) * size + c0 for i in range(len(ship))]


def orientation(ship, size=SIZE):
    """True - горизонтальный (однопалубный тоже считается горизонтальным)."""
    return len(ship) == 1 or ship[1] - ship[0] == 1


def can_place(ships, ship, rules=Rules(), size=SIZE):
    """Можно ли добавить корабль к уже стоящим: прямой, в поле, не налезает и не касается."""
    if not is_straight(ship, size):
        return False
    taken = set()
    for s in ships:
        taken |= halo(s, rules.corners, size)
    return not (set(ship) & taken)


def fleet_problems(ships, rules=Rules(), fleet=FLEET, size=SIZE):
    """Что не так с расстановкой; пустой список - всё по правилам."""
    problems = []
    if sorted((len(s) for s in ships), reverse=True) != sorted(fleet, reverse=True):
        problems.append("состав флота")
    for i, s in enumerate(ships):
        if not is_straight(s, size):
            problems.append(f"корабль {i} кривой или за краем")
    for i in range(len(ships)):
        for j in range(i + 1, len(ships)):
            if set(ships[j]) & halo(ships[i], rules.corners, size):
                problems.append(f"корабли {i} и {j} касаются")
    return problems


def valid_fleet(ships, rules=Rules(), fleet=FLEET, size=SIZE):
    return not fleet_problems(ships, rules, fleet, size)


@lru_cache(maxsize=32)
def placement_bits(length, size=SIZE, corners=False):
    """Места корабля с битами клеток и битами кольца вокруг (для быстрых проверок)."""
    return [(p, sum(1 << x for x in p), sum(1 << x for x in halo(p, corners, size)))
            for p in placements(length, size)]


def random_fleet(rng, rules=Rules(), fleet=FLEET, size=SIZE, attempts=1000):
    """Случайная расстановка: корабли по убыванию длины, каждый на случайное свободное
    место; тупик - начать заново. rng - numpy.random.Generator."""
    for _ in range(attempts):
        ships, taken = [], 0
        for L in sorted(fleet, reverse=True):
            free = [(p, b, hb) for p, b, hb in placement_bits(L, size, rules.corners) if not b & taken]
            if not free:
                break
            s, b, hb = free[int(rng.integers(len(free)))]
            ships.append(s)
            taken |= hb
        else:
            return ships
    raise RuntimeError("не удалось расставить флот")
