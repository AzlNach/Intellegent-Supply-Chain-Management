from abc import ABC, abstractmethod
from typing import Any, Dict


class Solver(ABC):
    """Abstract base class for inventory solvers."""

    @abstractmethod
    def solve(self, calc_input: Dict[str, Any]) -> Dict[str, int]:
        """Compute solver result from calculation input."""
        pass
