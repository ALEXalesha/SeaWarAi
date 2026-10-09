"""Бой: поле под выстрелами, партия на двоих и то, что видит стреляющий.

Стреляющий (и ИИ тоже) получает только Observation: что он сам узнал о чужом поле -
промахи, попадания, потопленные корабли, - и какие корабли ещё на плаву. Флот соперника
в Observation не попадает, это проверяет закон-тест честности.
"""
from dataclasses import dataclass

from game.core.rules import FLEET, SIZE, Rules, neighbors

UNKNOWN, MISS, HIT, SUNK = 0, 1, 2, 3
RESULTS = ("miss", "hit", "sunk")


@dataclass(frozen=True)
class Shot:
    cell: int
    result: str             # 'miss' | 'hit' | 'sunk'
    auto: tuple = ()        # клетки, отмеченные сами вокруг потопленного
    ship: tuple = ()        # клетки потопленного корабля


@dataclass(frozen=True)
class Observation:
    """Что стреляющий знает о чужом поле."""
    grid: tuple             # size*size значений UNKNOWN / MISS / HIT / SUNK
    remaining: tuple        # длины кораблей на плаву, по убыванию
    corners: bool = False
    size: int = SIZE

    def unknown(self):
        return [i for i, v in enumerate(self.grid) if v == UNKNOWN]

    def hits(self):
        """Попадания по кораблям, которые ещё не потоплены."""
        return [i for i, v in enumerate(self.grid) if v == HIT]


class Board:
    """Флот одного игрока и выстрелы по нему."""

    def __init__(self, ships, rules=Rules(), size=SIZE):
        self.ships = [tuple(sorted(s)) for s in ships]
        self.rules = rules
        self.size = size
        self.owner = {}
        for i, s in enumerate(self.ships):
            for x in s:
                self.owner[x] = i
        self.view = [UNKNOWN] * (size * size)
        self.hit_count = [0] * len(self.ships)
        self.sunk = [False] * len(self.ships)
        self.auto = set()

    def shoot(self, cell):
        if not (0 <= cell < self.size * self.size):
            raise ValueError(f"клетка {cell} вне поля")
        if self.view[cell] != UNKNOWN:
            raise ValueError(f"в клетку {cell} уже стреляли")
        i = self.owner.get(cell)
        if i is None:
            self.view[cell] = MISS
            return Shot(cell, "miss")
        self.view[cell] = HIT
        self.hit_count[i] += 1
        ship = self.ships[i]
        if self.hit_count[i] < len(ship):
            return Shot(cell, "hit")
        self.sunk[i] = True
        auto = []
        for x in ship:
            self.view[x] = SUNK
        for x in ship:
            for y in neighbors(x, self.rules.corners, self.size):
                if self.view[y] == UNKNOWN:
                    self.view[y] = MISS
                    self.auto.add(y)
                    auto.append(y)
        return Shot(cell, "sunk", tuple(sorted(set(auto))), ship)

    def remaining(self):
        return tuple(sorted((len(s) for s, d in zip(self.ships, self.sunk) if not d), reverse=True))

    def all_sunk(self):
        return all(self.sunk)

    def observation(self):
        return Observation(tuple(self.view), self.remaining(), self.rules.corners, self.size)


class Match:
    """Партия на двоих. boards[p] - флот игрока p, по нему стреляет соперник.

    Обычные правила: попал - стреляешь ещё, промах - ход переходит. Залп (rules.salvo):
    за ход столько выстрелов, сколько у стреляющего кораблей на плаву (считается в начале
    хода), результат каждого виден сразу, лишних выстрелов за попадания нет.
    """

    def __init__(self, fleets, rules=Rules(), first=0, size=SIZE):
        self.rules = rules
        self.size = size
        self.boards = [Board(fleets[0], rules, size), Board(fleets[1], rules, size)]
        self.turn = first
        self.winner = None
        self.log = []                  # (стрелявший, Shot)
        self.shots = [0, 0]
        self.shots_left = self.shots_per_turn(first)

    @property
    def over(self):
        return self.winner is not None

    def shots_per_turn(self, player):
        return len(self.boards[player].remaining()) if self.rules.salvo else 1

    def target(self, player):
        """Поле, по которому стреляет player."""
        return self.boards[1 - player]

    def observation(self, player):
        return self.target(player).observation()

    def legal(self):
        return [] if self.over else self.observation(self.turn).unknown()

    def fire(self, cell):
        if self.over:
            raise ValueError("партия окончена")
        p = self.turn
        shot = self.target(p).shoot(cell)
        self.shots[p] += 1
        self.log.append((p, shot))
        if self.target(p).all_sunk():
            self.winner = p
            self.shots_left = 0
            return shot
        if self.rules.salvo:
            self.shots_left -= 1
            if self.shots_left <= 0:
                self._pass_turn()
        elif shot.result == "miss":
            self._pass_turn()
        return shot

    def _pass_turn(self):
        self.turn = 1 - self.turn
        self.shots_left = self.shots_per_turn(self.turn)


def fleet_size(fleet=FLEET):
    return sum(fleet)
