from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .instruments import Instrument


@dataclass(frozen=True)
class Universe:
    cash: tuple[Instrument, ...]
    futures: tuple[Instrument, ...]
    options: tuple[Instrument, ...]
    indices: tuple[Instrument, ...]
    global_context: tuple[Instrument, ...]


def classify(instruments: tuple[Instrument, ...], *, today: date) -> Universe:
    live = tuple(x for x in instruments if x.expiry is None or x.expiry >= today)
    return Universe(
        cash=tuple(x for x in live if x.instrument_type in {"EQ", "EQUITY"}),
        futures=tuple(x for x in live if "FUT" in x.instrument_type),
        options=tuple(x for x in live if x.instrument_type in {"CE", "PE"}),
        indices=tuple(x for x in live if "INDEX" in x.segment and x.instrument_type not in {"CE", "PE"}),
        global_context=tuple(x for x in live if x.segment in {"GLOBAL_INDEX", "GLOBAL_INDICATOR"}),
    )
