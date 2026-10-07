from __future__ import annotations

from pydantic import BaseModel

from .radar import RadarInputs


class RadarCandidateRequest(BaseModel):
    symbol: str
    asset_class: str
    side: str
    live_confirmation: float
    path_match: float
    potential_left: float
    net_r_multiple: float
    liquidity_score: float
    spread_score: float
    executable: bool = True
    block_reason: str | None = None

    def radar_inputs(self) -> RadarInputs:
        return RadarInputs(
            self.live_confirmation,
            self.path_match,
            self.potential_left,
            self.net_r_multiple,
            self.liquidity_score,
            self.spread_score,
        )


class RadarRequest(BaseModel):
    candidates: list[RadarCandidateRequest]
