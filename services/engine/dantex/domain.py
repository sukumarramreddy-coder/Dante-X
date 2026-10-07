from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class AssetClass(StrEnum):
    INDEX = "index"
    INDEX_OPTION = "index_option"
    EQUITY = "equity"
    EQUITY_OPTION = "equity_option"
    CURRENCY = "currency"
    CURRENCY_OPTION = "currency_option"


class Side(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class Lifecycle(StrEnum):
    NO_EDGE = "NO_EDGE"
    DETECTED = "DETECTED"
    WATCH = "WATCH"
    ARMED = "ARMED"
    GO = "GO"
    HOLD = "HOLD"
    RUN = "RUN"
    WARNING = "WARNING"
    EXIT = "EXIT"
    CANCEL = "CANCEL"


class Horizon(StrEnum):
    SCALP = "scalp"
    INTRADAY = "intraday"
    POSITIONAL = "positional"
    EXPIRY = "expiry"


class Confidence(BaseModel):
    live_confirmation: float = Field(ge=0, le=100)
    path_match: float = Field(ge=0, le=100)
    potential_left: float = Field(ge=0, le=100)
    calibrated_probability: float | None = Field(default=None, ge=0, le=100)
    calibration_label: Literal["uncalibrated", "validated"] = "uncalibrated"

    @model_validator(mode="after")
    def probability_requires_validation(self):
        if self.calibration_label != "validated" and self.calibrated_probability is not None:
            raise ValueError("Probability cannot be published before validation.")
        return self


class PricePlan(BaseModel):
    underlying_trigger: float
    premium_trigger: float | None = None
    entry_low: float
    entry_high: float
    stop: float
    targets: list[float] = Field(min_length=1)
    cancel_underlying: float | None = None


class RiskPlan(BaseModel):
    risk_budget_inr: float = Field(gt=0)
    risk_per_unit_inr: float = Field(gt=0)
    quantity: int = Field(gt=0)
    estimated_costs_inr: float = Field(ge=0)
    expected_reward_inr: float = Field(gt=0)
    net_r_multiple: float


class Signal(BaseModel):
    signal_id: str
    created_at: datetime
    symbol: str
    asset_class: AssetClass
    side: Side
    horizon: Horizon
    lifecycle: Lifecycle
    contract: str | None = None
    plan: PricePlan
    risk: RiskPlan
    confidence: Confidence
    evidence: list[str]
    invalidation_reason: str
    expires_at: datetime | None = None
