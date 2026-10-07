from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    mode: str
    database_path: str
    max_daily_loss: float

    @classmethod
    def from_env(cls) -> Settings:
        mode = getenv("DANTEX_MODE", "shadow").lower()
        if mode != "shadow":
            raise ValueError("DANTEX_MODE must be shadow; live order mode is disabled")
        return cls(
            mode=mode,
            database_path=getenv("DANTEX_DB", "dantex.db"),
            max_daily_loss=float(getenv("DANTEX_MAX_DAILY_LOSS", "1000")),
        )
