"""Партия в окне без Qt: флоты, кто человек, уровень ИИ, выстрелы, итог.

Режимы: 'play' - человек (игрок 0) против ИИ (игрок 1); 'demo' - ИИ против ИИ, оба флота
открыты. Привычки игрока записываются только в конце партии: пока партия идёт, ИИ не
должен знать нынешнюю расстановку даже через привычки.
"""
import numpy as np

from game.ai.placement import ai_fleet
from game.ai.prob import uniform_fleet
from game.core.battle import Match
from game.core.rules import Rules, valid_fleet

MODES = ("play", "demo")


class Session:
    def __init__(self, human_fleet=None, level="strong", rules=Rules(), seed=0, mode="play",
                 habits=None, first=0):
        if mode not in MODES:
            raise ValueError(mode)
        rng = np.random.default_rng([int(seed), 7])
        self.mode, self.level, self.rules, self.seed = mode, level, rules, seed
        self.human = 0 if mode == "play" else -1
        if mode == "demo" or human_fleet is None:
            human_fleet = uniform_fleet(rng, rules.corners)
        if not valid_fleet(human_fleet, rules):
            raise ValueError("расстановка не по правилам")
        self.fleet_ai = ai_fleet(rng, rules, habits if mode == "play" else None, level)
        self.match = Match([list(human_fleet), self.fleet_ai], rules, first)
        self.human_shots = []
        self.recorded = False

    @property
    def over(self):
        return self.match.over

    @property
    def turn(self):
        return self.match.turn

    def human_turn(self):
        return not self.over and self.match.turn == self.human

    def ai_turn(self):
        return not self.over and self.match.turn != self.human

    def obs(self, player):
        return self.match.observation(player)

    def fire(self, cell):
        p = self.match.turn
        shot = self.match.fire(cell)
        if p == self.human:
            self.human_shots.append(cell)
        return p, shot

    def outcome_for_human(self):
        if not self.over or self.human < 0:
            return None
        return "win" if self.match.winner == self.human else "loss"

    def stats_key(self):
        return f"{self.level}/{'salvo' if self.rules.salvo else 'classic'}"

    def record_habits(self, habits):
        """В конце партии против ИИ: расстановка игрока и его первые выстрелы."""
        if habits is None or self.human < 0 or not self.over or self.recorded:
            return
        habits.record_fleet(self.match.boards[self.human].ships, save=False)
        habits.record_shots(self.human_shots, save=False)
        habits.save()
