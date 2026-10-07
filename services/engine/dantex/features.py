from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    key: str
    bullish: float
    bearish: float
    family: str
    note: str = ""


@dataclass(frozen=True)
class HypothesisScore:
    bullish: float
    bearish: float
    conflict: float
    independent_families: int


def score_hypotheses(evidence: list[Evidence]) -> HypothesisScore:
    """Collapse each evidence family first so correlated indicators do not get extra votes."""
    if not evidence:
        return HypothesisScore(0, 0, 100, 0)

    by_family: dict[str, list[Evidence]] = {}
    for item in evidence:
        by_family.setdefault(item.family, []).append(item)

    bull, bear = [], []
    for family_items in by_family.values():
        bull.append(sum(x.bullish for x in family_items) / len(family_items))
        bear.append(sum(x.bearish for x in family_items) / len(family_items))

    b1 = sum(bull) / len(bull)
    b2 = sum(bear) / len(bear)
    conflict = min(b1, b2)
    return HypothesisScore(round(b1, 1), round(b2, 1), round(conflict, 1), len(by_family))
