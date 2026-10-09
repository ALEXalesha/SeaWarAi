# Мутанты для tools/mutate.py: (имя, файл, было, стало, проверки). Каждый ломает одно правило.
R = "game/core/rules.py"
B = "game/core/battle.py"
TR = "tests/test_rules.py"
TB = "tests/test_battle.py tests/test_rules.py"
MUTANTS = [
    ("rules: углы можно всегда", R, "if (dr, dc) == (0, 0) or (corners and dr and dc):",
     "if (dr, dc) == (0, 0) or (dr and dc):", TR),
    ("rules: углы нельзя и с опцией", R, "if (dr, dc) == (0, 0) or (corners and dr and dc):",
     "if (dr, dc) == (0, 0):", TR),
    ("rules: сосед за краем", R, "if 0 <= rr < size and 0 <= cc < size:", "if 0 <= rr < size:", TR),
    ("rules: корабль за правый край", R, "if c + length > size:", "if c + length > size + 1:", TR),
    ("rules: корабль за нижний край", R, "if r + length > size:", "if r + length > size + 1:", TR),
    ("rules: однопалубный дважды", R, "for horizontal in ((True,) if length == 1 else (True, False)):",
     "for horizontal in (True, False):", TR),
    ("rules: перенос строки прямой", R, "and c0 + len(ship) <= size)", ")", TR),
    ("rules: касание не проверяется", R, "return not (set(ship) & taken)", "return True", TR),
    ("rules: состав не проверяется", R,
     "if sorted((len(s) for s in ships), reverse=True) != sorted(fleet, reverse=True):", "if False:", TR),
    ("rules: случайная касается", R, "            taken |= hb", "            taken |= b", TR),
    ("rules: флот другой", R, "FLEET = (4, 3, 3, 2, 2, 2, 1, 1, 1, 1)", "FLEET = (4, 3, 3, 2, 2, 1, 1, 1, 1, 1)", TR),
    ("battle: попадание мимо", B, "if i is None:", "if i is None or i == 0:", TB),
    ("battle: повтор выстрела", B, "if self.view[cell] != UNKNOWN:", "if self.view[cell] == SUNK:", TB),
    ("battle: тонет раньше", B, "if self.hit_count[i] < len(ship):", "if self.hit_count[i] < len(ship) - 1:", TB),
    ("battle: нет автоотметки", B, "                if self.view[y] == UNKNOWN:\n                    self.view[y] = MISS",
     "                if False:\n                    self.view[y] = MISS", TB),
    ("battle: автоотметка 8 и с углами", B, "for y in neighbors(x, self.rules.corners, self.size):",
     "for y in neighbors(x, False, self.size):", TB),
    ("battle: попал - ход переходит", B, 'elif shot.result == "miss":', "else:", TB),
    ("battle: промах - ход остаётся", B, 'elif shot.result == "miss":', 'elif shot.result == "none":', TB),
    ("battle: залп всегда 10", B, "return len(self.boards[player].remaining()) if self.rules.salvo else 1",
     "return 10 if self.rules.salvo else 1", TB),
    ("battle: залп за попадание ещё", B, "            if self.shots_left <= 0:",
     '            if self.shots_left <= 0 and shot.result == "miss":', TB),
    ("battle: победы нет", B, "if self.target(p).all_sunk():", "if False:", TB),
    ("battle: потопленный на плаву", B,
     "return tuple(sorted((len(s) for s, d in zip(self.ships, self.sunk) if not d), reverse=True))",
     "return tuple(sorted((len(s) for s in self.ships), reverse=True))", TB),
]
