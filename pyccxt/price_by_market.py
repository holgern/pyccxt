"""Backward-compatible exports for the older price-by-market API name."""

from .exchange import Exchange, get_market_volumes_for_pair

PriceByMarket = Exchange

__all__ = [
    "Exchange",
    "PriceByMarket",
    "get_market_volumes_for_pair",
]
