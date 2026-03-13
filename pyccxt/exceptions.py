from __future__ import annotations


class PyCCXTError(Exception):
    """Base exception for pyccxt errors."""


class ExchangeInitializationError(PyCCXTError):
    """Raised when an exchange cannot be initialized."""


class ExchangeNotFoundError(PyCCXTError):
    """Raised when an exchange id is unknown to CCXT."""


class MarketLoadError(PyCCXTError):
    """Raised when exchange markets cannot be loaded."""


class TickerFetchError(PyCCXTError):
    """Raised when ticker data cannot be fetched."""


class VolumeNormalizationError(PyCCXTError):
    """Raised when volume normalization cannot be completed."""


__all__ = [
    "PyCCXTError",
    "ExchangeInitializationError",
    "ExchangeNotFoundError",
    "MarketLoadError",
    "TickerFetchError",
    "VolumeNormalizationError",
]
