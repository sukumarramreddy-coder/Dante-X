from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class UpstoxCredentials:
    analytics_token: str

    @classmethod
    def from_env(cls) -> UpstoxCredentials:
        token = os.getenv("UPSTOX_ANALYTICS_TOKEN", "").strip()
        if not token:
            raise RuntimeError("UPSTOX_ANALYTICS_TOKEN is not configured")
        return cls(token)

    def bearer_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.analytics_token}"}
