from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .exchange import Exchange
    from .market import Market
    from .ohlc import OHLC
    from .ohlcv_collection import OHLCVCollection
    from .price_by_market import MarketVolume, PriceByMarket
    from .ticker import Ticker


_EXPORTS = {
    "PriceByMarket": (".price_by_market", "PriceByMarket"),
    "Ticker": (".ticker", "Ticker"),
    "MarketVolume": (".price_by_market", "MarketVolume"),
    "Exchange": (".exchange", "Exchange"),
    "Market": (".market", "Market"),
    "OHLC": (".ohlc", "OHLC"),
    "OHLCVCollection": (".ohlcv_collection", "OHLCVCollection"),
}

__all__ = [
    "PriceByMarket",
    "Ticker",
    "MarketVolume",
    "Exchange",
    "Market",
    "OHLC",
    "OHLCVCollection",
]


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
