from __future__ import annotations

import random
from collections import defaultdict


class FrontierSampler:
    def __init__(self, seed: int = 0, calibration_weight: float = 0.15):
        self.rng = random.Random(seed)
        self.calibration_weight = calibration_weight
        self.stats = defaultdict(lambda: [0, 0])

    @staticmethod
    def _key(task_or_difficulty):
        if hasattr(task_or_difficulty, "difficulty"):
            grammar = getattr(task_or_difficulty, "grammar", "unknown")
            difficulty = task_or_difficulty.difficulty
        else:
            grammar = "unknown"
            difficulty = task_or_difficulty
        return (grammar, difficulty.key() if hasattr(difficulty, "key") else tuple(difficulty))

    def observe(self, difficulty, passed: bool) -> None:
        key = self._key(difficulty)
        self.stats[key][0] += int(bool(passed))
        self.stats[key][1] += 1

    def score(self, task) -> float:
        passed, total = self.stats[self._key(task)]
        if total == 0:
            return 1.0
        rate = passed / total
        uncertainty = 1.0 - abs(rate - 0.5) * 2.0
        return self.calibration_weight + uncertainty
    def next_batch(self, pool, n: int):
        pool = list(pool)
        jittered = [(self.score(task) + self.rng.random() * 1e-6, task) for task in pool]
        jittered.sort(key=lambda pair: pair[0], reverse=True)
        selected = []
        used_grammars = set()
        for _, task in jittered:
            if len(selected) >= n:
                break
            grammar = getattr(task, "grammar", "unknown")
            if grammar not in used_grammars:
                selected.append(task)
                used_grammars.add(grammar)
        if len(selected) < n:
            selected_ids = {id(x) for x in selected}
            for _, task in jittered:
                if id(task) in selected_ids:
                    continue
                selected.append(task)
                if len(selected) >= n:
                    break
        return selected
