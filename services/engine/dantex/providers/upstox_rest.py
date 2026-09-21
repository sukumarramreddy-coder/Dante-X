from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote
from urllib.request import Request, urlopen

from .upstox import UpstoxConfig


@dataclass
class UpstoxRestClient:
    config: UpstoxConfig

    def _get(self, path: str) -> dict:
        request = Request(
            self.config.rest_base + path,
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer " + self.config.access_token,
            },
        )
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    def historical_candles(
        self, instrument_key: str, *, unit: str, interval: int, to_date: str, from_date: str
    ) -> dict:
        key = quote(instrument_key, safe="")
        return self._get(
            f"/v3/historical-candle/{key}/{unit}/{interval}/{to_date}/{from_date}"
        )

    def intraday_candles(self, instrument_key: str, *, unit: str, interval: int) -> dict:
        key = quote(instrument_key, safe="")
        return self._get(f"/v3/historical-candle/intraday/{key}/{unit}/{interval}")

    def option_chain(self, instrument_key: str, *, expiry_date: str) -> dict:
        key = quote(instrument_key, safe="")
        return self._get(f"/v2/option/chain?instrument_key={key}&expiry_date={expiry_date}")

    def full_market_quote(self, instrument_key: str) -> dict:
        key = quote(instrument_key, safe="")
        return self._get(f"/v3/market-quote/quotes?instrument_key={key}")

    def market_feed_authorize(self) -> dict:
        return self._get("/feed/market-data-feed/authorize")
