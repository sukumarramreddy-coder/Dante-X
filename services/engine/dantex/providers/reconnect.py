from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconnectPolicy:
    initial_seconds: float = 1
    maximum_seconds: float = 30
    multiplier: float = 2

    def delay(self, attempt: int) -> float:
        if attempt < 0:
            raise ValueError("attempt must be non-negative")
        return min(self.maximum_seconds, self.initial_seconds * self.multiplier**attempt)
