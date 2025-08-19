from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class OHLC:
    """
    Represents a single OHLC (Open, High, Low, Close) candlestick with volume data.

    This class encapsulates OHLCV data from cryptocurrency exchanges, providing
    easy access to price and volume information for a specific time period.
    """

    def __init__(
        self,
        timestamp: int,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: float,
        symbol: str | None = None,
        timeframe: str | None = None,
    ):
        """
        Initialize an OHLC instance.

        Args:
            timestamp: UTC timestamp in milliseconds
            open_price: Opening price for the period
            high_price: Highest price during the period
            low_price: Lowest price during the period
            close_price: Closing price for the period
            volume: Trading volume during the period (usually in base currency)
            symbol: Trading pair symbol (e.g., 'BTC/EUR')
            timeframe: Timeframe of the candle (e.g., '1h', '1d')
        """
        self.timestamp = timestamp
        self.open = open_price
        self.high = high_price
        self.low = low_price
        self.close = close_price
        self.volume = volume
        self.symbol = symbol
        self.timeframe = timeframe

    def __repr__(self) -> str:
        """
        Return a string representation of the OHLC instance.

        Returns:
            str: String representation showing timestamp, OHLC prices, and volume
        """
        dt = self.datetime.strftime("%Y-%m-%d %H:%M:%S") if self.datetime else "N/A"
        symbol_str = f" {self.symbol}" if self.symbol else ""
        return (
            f"OHLC({dt}{symbol_str}, O:{self.open:.4f}, H:{self.high:.4f}, "
            f"L:{self.low:.4f}, C:{self.close:.4f}, V:{self.volume:.2f})"
        )

    @property
    def datetime(self) -> datetime | None:
        """
        Get the datetime representation of the timestamp.

        Returns:
            datetime: UTC datetime object or None if timestamp is invalid
        """
        if self.timestamp is None:
            return None
        try:
            return datetime.fromtimestamp(self.timestamp / 1000, tz=timezone.utc)
        except (ValueError, OSError):
            return None

    @property
    def iso_datetime(self) -> str | None:
        """
        Get the ISO8601 datetime string representation.

        Returns:
            str: ISO8601 formatted datetime string or None if timestamp is invalid
        """
        dt = self.datetime
        return dt.isoformat() if dt else None

    @classmethod
    def from_ccxt_array(
        cls,
        ohlcv_array: list[Any],
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> OHLC:
        """
        Create an OHLC instance from a CCXT OHLCV array.

        Args:
            ohlcv_array: CCXT OHLCV array [timestamp, open, high, low, close, volume]
            symbol: Trading pair symbol
            timeframe: Timeframe of the candle

        Returns:
            OHLC: New OHLC instance

        Raises:
            ValueError: If the array doesn't have the expected format
        """
        if not isinstance(ohlcv_array, (list, tuple)) or len(ohlcv_array) < 6:
            raise ValueError(
                "OHLCV array must have at least 6 elements: "
                "[timestamp, open, high, low, close, volume]"
            )

        timestamp, open_price, high_price, low_price, close_price, volume = ohlcv_array[
            :6
        ]

        # Validate numeric values
        try:
            timestamp = int(timestamp) if timestamp is not None else 0
            open_price = float(open_price) if open_price is not None else 0.0
            high_price = float(high_price) if high_price is not None else 0.0
            low_price = float(low_price) if low_price is not None else 0.0
            close_price = float(close_price) if close_price is not None else 0.0
            volume = float(volume) if volume is not None else 0.0
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid numeric value in OHLCV array: {e}") from e

        return cls(
            timestamp=timestamp,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=volume,
            symbol=symbol,
            timeframe=timeframe,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> OHLC:
        """
        Create an OHLC instance from a dictionary.

        Args:
            data: Dictionary with OHLC data
            symbol: Trading pair symbol
            timeframe: Timeframe of the candle

        Returns:
            OHLC: New OHLC instance
        """
        return cls(
            timestamp=data.get("timestamp", 0),
            open_price=data.get("open", 0.0),
            high_price=data.get("high", 0.0),
            low_price=data.get("low", 0.0),
            close_price=data.get("close", 0.0),
            volume=data.get("volume", 0.0),
            symbol=symbol,
            timeframe=timeframe,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the OHLC instance to a dictionary.

        Returns:
            dict: Dictionary representation of the OHLC data
        """
        return {
            "timestamp": self.timestamp,
            "datetime": self.iso_datetime,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
        }

    def to_ccxt_array(self) -> list[Any]:
        """
        Convert the OHLC instance to a CCXT-compatible array format.

        Returns:
            list: CCXT OHLCV array [timestamp, open, high, low, close, volume]
        """
        return [self.timestamp, self.open, self.high, self.low, self.close, self.volume]

    def get_change(self) -> float:
        """
        Calculate the absolute price change (close - open).

        Returns:
            float: Absolute price change
        """
        return self.close - self.open

    def get_change_percentage(self) -> float:
        """
        Calculate the percentage price change.

        Returns:
            float: Percentage change (0-100 scale)
        """
        if self.open == 0:
            return 0.0
        return ((self.close - self.open) / self.open) * 100

    def get_typical_price(self) -> float:
        """
        Calculate the typical price (high + low + close) / 3.

        Returns:
            float: Typical price
        """
        return (self.high + self.low + self.close) / 3

    def get_range(self) -> float:
        """
        Calculate the price range (high - low).

        Returns:
            float: Price range
        """
        return self.high - self.low

    def is_bullish(self) -> bool:
        """
        Check if the candle is bullish (close > open).

        Returns:
            bool: True if bullish, False otherwise
        """
        return self.close > self.open

    def is_bearish(self) -> bool:
        """
        Check if the candle is bearish (close < open).

        Returns:
            bool: True if bearish, False otherwise
        """
        return self.close < self.open

    def is_doji(self, threshold: float = 0.001) -> bool:
        """
        Check if the candle is a doji (open ≈ close).

        Args:
            threshold: Percentage threshold for considering prices equal

        Returns:
            bool: True if doji, False otherwise
        """
        if self.open == 0:
            return False
        return abs((self.close - self.open) / self.open) <= threshold

    def get_body_size(self) -> float:
        """
        Get the size of the candle body (absolute difference between open and close).

        Returns:
            float: Body size
        """
        return abs(self.close - self.open)

    def get_upper_shadow(self) -> float:
        """
        Get the upper shadow (wick) size.

        Returns:
            float: Upper shadow size
        """
        return self.high - max(self.open, self.close)

    def get_lower_shadow(self) -> float:
        """
        Get the lower shadow (wick) size.

        Returns:
            float: Lower shadow size
        """
        return min(self.open, self.close) - self.low

    def validate(self) -> bool:
        """
        Validate the OHLC data integrity.

        Returns:
            bool: True if data is valid, False otherwise
        """
        try:
            # Check that high is the highest price
            if self.high < max(self.open, self.close, self.low):
                return False

            # Check that low is the lowest price
            if self.low > min(self.open, self.close, self.high):
                return False

            # Check for negative values (assuming all prices should be positive)
            if any(
                value < 0
                for value in [self.open, self.high, self.low, self.close, self.volume]
            ):
                return False

            # Check timestamp is reasonable (after 2000-01-01)
            if self.timestamp < 946684800000:  # Year 2000 in milliseconds
                return False

            return True
        except (TypeError, ValueError):
            return False
