"""Limites deterministas.

Regla transversal 3: el mismo comando debe dar el mismo resultado en tu
maquina y en la del arbitro. El reloj de pared no sirve para eso; el
rlimit de z3 es una medida de trabajo determinista, si.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Limits:
    timeout_ms: int = 10_000
    rlimit: int = 20_000_000          # medida de trabajo de z3
    max_memory_mb: int = 2048
    seed: int = 0
    max_iterations: int = 10_000      # para bucles (synth)
    conflict_budget: int = 1_000_000  # medida de trabajo de SAT (cases)

    def apply_to(self, solver) -> None:
        """Aplica los limites a un z3.Solver / z3.Optimize."""
        solver.set("timeout", self.timeout_ms)
        solver.set("rlimit", self.rlimit)
        try:
            solver.set("max_memory", self.max_memory_mb)
        except Exception:
            pass  # no todos los tacticos aceptan max_memory

    def to_dict(self) -> dict:
        return asdict(self)
