"""Chiller plant model: part-load efficiency and electrical power."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Chiller:
    name: str
    capacity_kw: float      # cooling capacity (kW thermal)
    cop_max: float          # best-case coefficient of performance
    best_plr: float         # part-load ratio where efficiency peaks
    min_plr: float = 0.2    # lowest stable part-load ratio

    def cop(self, load_kw: float) -> float:
        """COP falls off quadratically as the chiller moves away from its sweet spot."""
        plr = load_kw / self.capacity_kw
        return self.cop_max * (1 - 1.5 * (plr - self.best_plr) ** 2)

    def power_kw(self, load_kw: float) -> float:
        """Electrical power needed to deliver `load_kw` of cooling."""
        if load_kw <= 0:
            return 0.0
        return load_kw / self.cop(load_kw)


def default_plant() -> list[Chiller]:
    """A made-up three-chiller plant. Not based on any real facility."""
    return [
        Chiller("CH-1", capacity_kw=1000, cop_max=6.0, best_plr=0.80),
        Chiller("CH-2", capacity_kw=1000, cop_max=5.5, best_plr=0.75),
        Chiller("CH-3", capacity_kw=500, cop_max=5.0, best_plr=0.70),
    ]
