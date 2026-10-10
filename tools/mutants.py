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
P = "game/ai/prob.py"
TP = "tests/test_prob.py"
A = "game/ai/agents.py"
TA = "tests/test_agents.py"
TH = "tests/test_honesty.py"
MUTANTS += [
    ("prob: попадание можно не накрыть", P, "            if uncovered == 0:\n                state",
     "            if True:\n                state", TP),
    ("prob: корабль из одних попаданий", P, "ok = ~(c & blocked).any(1) & (c & ~hits).any(1)",
     "ok = ~(c & blocked).any(1)", TP),
    # «if unc & hb» в точном переборе - только отсечение: второй корабль у попадания всё равно
    # упрётся в кольцо первого. Мутант равносилен, в списке его нет.
    ("prob: потопленный не мешает соседям", P, "        blocked[neighbors(int(x), obs.corners, size)] = True",
     "        pass", TP),
    ("prob: одинаковые не делятся на k!", P, "        logw -= np.array([math.lgamma(k + 1) for k in rem[:, t]])",
     "        pass", TP),
    ("prob: касание в выборке не проверяется", P, "            F[rows] |= Hl[choice]", "            F[rows] |= Cl[choice]", TP),
    ("prob: выборка без весов", P, "            logw[rows] += np.log(tot)\n\n    if not alive",
     "            pass\n\n    if not alive", TP),
    ("prob: наибольшая не выбирается", P, "    cand = unknown[vals >= top - 1e-9 * max(top, 1e-12)]", "    cand = unknown", TP),
    ("agents: добивание без линии", A, "    if len(group) == 1:", "    if True:", TA),
    ("agents: шахматка не та", A, "== self.parity]", "!= self.parity]", TA),
    ("agents: диагонали и с углами", A, "for x in ([] if obs.corners else obs.hits()):", "for x in obs.hits():", TA),
    ("agents: сильный стреляет в известное", A, "        p[[i for i, v in enumerate(obs.grid) if v != UNKNOWN]] = 0.0\n",
     "", TA),
    ("honesty: наблюдение видит корабли", B, "        return Observation(tuple(self.view), self.remaining(), self.rules.corners, self.size)",
     "        return Observation(tuple(2 if i in self.owner and v == 0 else v for i, v in enumerate(self.view)), "
     "self.remaining(), self.rules.corners, self.size)", TH),
]
H = "game/ai/habits.py"
TB2 = "tests/test_habits.py"
MUTANTS += [
    ("habits: флот не пишется", H, "            self.cells[len(s)][list(s)] += 1", "            pass", TB2),
    ("habits: без сглаживания", H, "f = (_blur(self.cells[L]) + SMOOTH * b) / (self.games + SMOOTH)",
     "f = (self.cells[L] + 0.01 * b) / (self.games + 0.01)", TB2),
    ("placement: самый большой ореол", "game/ai/placement.py", 'order = np.argsort([fleet_score(f, rules, habits) for f in fleets], kind="stable")',
     'order = np.argsort([-fleet_score(f, rules, habits) for f in fleets], kind="stable")', TB2),
    ("placement: стрельбу игрока не видит", "game/ai/placement.py", "    if habits is not None:\n        shots",
     "    if False:\n        shots", TB2),
]
