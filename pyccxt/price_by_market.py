"""
price_by_market module providing backward compatibility.

This module imports and re-exports classes from the new modular structure:
- Exchange from exchange.py
- Market from market.py
- Cross-exchange volume comparison functions
"""

from .exchange import Exchange, get_market_volumes_for_pair
from .market import Market

# Backward compatibility aliases
PriceByMarket = Exchange
MarketVolume = Exchange

__all__ = [
    "Exchange",
    "Market",
    "PriceByMarket",
    "MarketVolume",
    "get_market_volumes_for_pair",
]
