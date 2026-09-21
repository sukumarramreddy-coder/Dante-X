from __future__ import annotations

from dataclasses import dataclass

from .upstox_stream import FeedMode, Subscription


@dataclass(frozen=True)
class FeedLimits:
    ltpc: int = 5000
    option_greeks: int = 3000
    full: int = 2000
    combined: int = 2000


def plan_subscriptions(
    *,
    radar_keys: list[str],
    focus_keys: list[str],
    option_keys: list[str],
    limits: FeedLimits = FeedLimits(),
) -> tuple[Subscription, ...]:
    focus = tuple(dict.fromkeys(focus_keys))[:limits.full]
    focus_set = set(focus)
    options = tuple(k for k in dict.fromkeys(option_keys) if k not in focus_set)
    radar = tuple(
        k for k in dict.fromkeys(radar_keys)
        if k not in focus_set and k not in set(options)
    )
    if focus and options:
        options = options[:max(0, limits.combined - len(focus))]
    else:
        options = options[:limits.option_greeks]
    used = len(focus) + len(options)
    radar_limit = max(0, limits.combined - used) if used else limits.ltpc
    radar = radar[:radar_limit]
    result = []
    if focus:
        result.append(Subscription(focus, FeedMode.FULL))
    if options:
        result.append(Subscription(options, FeedMode.OPTION_GREEKS))
    if radar:
        result.append(Subscription(radar, FeedMode.LTPC))
    return tuple(result)
