import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from .ohlc import OHLC
from .ohlcv_collection import OHLCVCollection
from .ticker import Ticker

if TYPE_CHECKING:
    from .exchange import Exchange

logger = logging.getLogger(__name__)


class Market:
    """
    Represents a single trading pair on an exchange.

    This class manages data for a specific market (e.g., BTC/EUR) including
    current prices, volumes, OHLC data, and market metadata. The class stores
    the timeframe used for OHLC data and provides methods to fetch incremental
    updates using the stored timeframe.
    """

    def __init__(
        self,
        exchange: "Exchange",
        symbol: str,
        base_currency: str,
        quote_currency: str,
        market_info: dict[str, Any],
        min_refresh_time: int = 300,
    ):
        """
        Initialize a Market instance.

        Args:
            exchange: Parent Exchange instance
            symbol: Trading pair symbol (e.g., 'BTC/EUR')
            base_currency: Base currency (e.g., 'BTC')
            quote_currency: Quote currency (e.g., 'EUR')
            market_info: Market metadata from exchange
            min_refresh_time: Minimum refresh time in seconds
        """
        self.exchange = exchange
        self.symbol = symbol
        self.base_currency = base_currency.upper()
        self.quote_currency = quote_currency.upper()
        self.market_info = market_info
        self.min_refresh_time = min_refresh_time

        # Data storage
        self._ticker: Optional[Ticker] = None
        self._ohlc_data: Optional[OHLCVCollection] = None
        self._ohlc_timeframe: Optional[str] = None
        self._last_update: Optional[datetime] = None

    def __repr__(self) -> str:
        """
        Return a string representation of the Market instance.

        Returns:
            str: String representation showing symbol, exchange, and current price
        """
        price = self.get_price()
        price_str = f"{price:.8f}" if price is not None else "N/A"
        return (
            f"Market(symbol='{self.symbol}', exchange='{self.exchange.name}', "
            f"price={price_str})"
        )

    def refresh(self) -> bool:
        """
        Refresh market data if necessary.

        Returns:
            bool: True if successful, False otherwise
        """
        # Check if we need to refresh based on time
        if self._last_update is not None:
            current_time = datetime.now(timezone.utc)
            last_update = self._last_update
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)

            time_diff = (current_time - last_update).total_seconds()
            if time_diff < self.min_refresh_time:
                logger.debug(
                    f"Skipping refresh for {self.symbol} - last update was "
                    f"{time_diff} seconds ago"
                )
                return True

        try:
            # Fetch ticker data
            if self.exchange.ccxt_exchange is not None:
                ccxt_ticker = self.exchange.ccxt_exchange.fetch_ticker(self.symbol)
                self._ticker = Ticker.from_ccxt(ccxt_ticker)
                self._last_update = datetime.now(timezone.utc)
                return True
            return False
        except Exception as e:
            logger.error(f"Error refreshing ticker for {self.symbol}: {e}")
            return False

    def _validate_timeframe(self, timeframe: str) -> bool:
        """
        Validate if the timeframe is supported by the exchange.

        Args:
            timeframe: Timeframe to validate (e.g., '1h', '1d')

        Returns:
            bool: True if timeframe is supported, False otherwise
        """
        try:
            exchange_info = self.exchange.get_exchange_info()
            supported_timeframes = exchange_info.get("timeframes", {})
            return timeframe in supported_timeframes
        except Exception as e:
            logger.warning(f"Could not validate timeframe {timeframe}: {e}")
            return True  # Allow if validation fails

    def fetch_ohlc(
        self,
        timeframe: str = "1h",
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> bool:
        """
        Fetch OHLC data for this market and store it in an OHLCVCollection.

        Args:
            timeframe: Timeframe (e.g., '1h', '1d')
            since: Timestamp in milliseconds to fetch from
            limit: Maximum number of entries to fetch

        Returns:
            bool: True if successful, False otherwise
        """
        # Validate timeframe
        if not self._validate_timeframe(timeframe):
            logger.warning(
                f"Timeframe '{timeframe}' is not supported by exchange "
                f"{self.exchange.name}"
            )
            return False

        try:
            if (
                self.exchange.ccxt_exchange is not None
                and not self.exchange.ccxt_exchange.has.get("fetchOHLCV", False)
            ):
                logger.warning(
                    f"Exchange {self.exchange.name} does not support OHLCV data"
                )
                return False

            if self.exchange.ccxt_exchange is not None:
                ohlcv = self.exchange.ccxt_exchange.fetch_ohlcv(
                    self.symbol, timeframe, since, limit
                )
            else:
                return False

            if ohlcv is not None:
                ohlcv_collection = OHLCVCollection(self.symbol, timeframe)

                for entry in ohlcv:
                    timestamp = entry[0]
                    open_price, high_price, low_price, close_price, volume = entry[1:6]

                    open_price = self.format_price_to_precision(open_price)
                    high_price = self.format_price_to_precision(high_price)
                    low_price = self.format_price_to_precision(low_price)
                    close_price = self.format_price_to_precision(close_price)

                    ohlc_candle = OHLC(
                        timestamp=timestamp,
                        open_price=open_price,
                        high_price=high_price,
                        low_price=low_price,
                        close_price=close_price,
                        volume=volume,
                        symbol=self.symbol,
                        timeframe=timeframe,
                    )

                    ohlcv_collection.add_ohlc(ohlc_candle)

                self._ohlc_data = ohlcv_collection
                self._ohlc_timeframe = timeframe
                return True

            self._ohlc_data = None
            self._ohlc_timeframe = None
            return False

        except Exception as e:
            logger.error(f"Error fetching OHLC data for {self.symbol}: {e}")
            self._ohlc_data = None
            self._ohlc_timeframe = None
            return False

    def fetch_new_ohlc(self, limit: Optional[int] = None) -> bool:
        """
        Fetch new OHLC data since the latest existing data point.

        This method automatically calculates the 'since' parameter based on the
        newest OHLC value in the current dataset and fetches additional data.
        Uses the same timeframe as the existing data.

        Args:
            limit: Maximum number of entries to fetch

        Returns:
            bool: True if successful, False otherwise
        """
        # Check if we have existing OHLC data and timeframe
        if not self._ohlc_data or not self._ohlc_timeframe:
            logger.warning(
                f"No existing OHLC data found for {self.symbol}. "
                f"Use fetch_ohlc() first."
            )
            return False

        # Get the latest timestamp from existing data
        try:
            latest_ohlc = self._ohlc_data[-1]
            since_timestamp = latest_ohlc.timestamp

            # Add one timeframe interval to avoid duplicate data
            since_timestamp = self._add_timeframe_to_timestamp(
                since_timestamp, self._ohlc_timeframe
            )

            logger.debug(
                f"Fetching new OHLC data for {self.symbol} since {since_timestamp} "
                f"({datetime.fromtimestamp(since_timestamp / 1000, tz=timezone.utc)})"
            )

            # Fetch new data using existing timeframe
            return self._fetch_and_append_ohlc(
                self._ohlc_timeframe, since_timestamp, limit
            )

        except Exception as e:
            logger.error(f"Error fetching new OHLC data for {self.symbol}: {e}")
            return False

    def _add_timeframe_to_timestamp(self, timestamp: int, timeframe: str) -> int:
        """
        Add one timeframe interval to a timestamp.

        Args:
            timestamp: Timestamp in milliseconds
            timeframe: Timeframe string (e.g., '1h', '1d', '5m')

        Returns:
            int: New timestamp in milliseconds
        """
        # Parse timeframe (e.g., '1h' -> 1 hour, '5m' -> 5 minutes)
        timeframe_map = {
            "m": 60 * 1000,  # minutes to milliseconds
            "h": 60 * 60 * 1000,  # hours to milliseconds
            "d": 24 * 60 * 60 * 1000,  # days to milliseconds
            "w": 7 * 24 * 60 * 60 * 1000,  # weeks to milliseconds
            "M": 30 * 24 * 60 * 60 * 1000,  # months to milliseconds (approximate)
        }

        # Extract number and unit from timeframe
        import re

        match = re.match(r"(\d+)([mhdwM])", timeframe)
        if not match:
            logger.warning(f"Unknown timeframe format: {timeframe}")
            return timestamp + (60 * 60 * 1000)  # Default to 1 hour

        number, unit = match.groups()
        number = int(number)

        if unit not in timeframe_map:
            logger.warning(f"Unknown timeframe unit: {unit}")
            return timestamp + (60 * 60 * 1000)  # Default to 1 hour

        interval_ms = number * timeframe_map[unit]
        return timestamp + interval_ms

    def _fetch_and_append_ohlc(
        self, timeframe: str, since: int, limit: Optional[int] = None
    ) -> bool:
        """
        Fetch OHLC data and append to existing collection.

        Args:
            timeframe: Timeframe for the data
            since: Timestamp in milliseconds to fetch from
            limit: Maximum number of entries to fetch

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.exchange.ccxt_exchange is not None:
                ohlcv = self.exchange.ccxt_exchange.fetch_ohlcv(
                    self.symbol, timeframe, since, limit
                )
            else:
                return False

            if ohlcv and len(ohlcv) > 0:
                # Process and append new data to existing collection
                new_entries_count = 0
                for entry in ohlcv:
                    timestamp = entry[0]

                    # Skip if we already have this timestamp (avoid duplicates)
                    if self._ohlc_data and any(
                        ohlc.timestamp == timestamp
                        for ohlc in self._ohlc_data.get_ohlc_data()
                    ):
                        continue

                    open_price, high_price, low_price, close_price, volume = entry[1:6]

                    # Apply precision formatting if available
                    open_price = self.format_price_to_precision(open_price)
                    high_price = self.format_price_to_precision(high_price)
                    low_price = self.format_price_to_precision(low_price)
                    close_price = self.format_price_to_precision(close_price)

                    # Create OHLC instance
                    ohlc_candle = OHLC(
                        timestamp=timestamp,
                        open_price=open_price,
                        high_price=high_price,
                        low_price=low_price,
                        close_price=close_price,
                        volume=volume,
                        symbol=self.symbol,
                        timeframe=timeframe,
                    )

                    if self._ohlc_data is not None:
                        self._ohlc_data.add_ohlc(ohlc_candle)
                        new_entries_count += 1

                logger.debug(
                    f"Added {new_entries_count} new OHLC entries for {self.symbol}"
                )
                return new_entries_count > 0
            else:
                logger.debug(f"No new OHLC data available for {self.symbol}")
                return True  # Not an error, just no new data

        except Exception as e:
            logger.error(
                f"Error fetching and appending OHLC data for {self.symbol}: {e}"
            )
            return False

    def get_current_timeframe(self) -> Optional[str]:
        """
        Get the currently stored timeframe for OHLC data.

        Returns:
            str: The timeframe string or None if no OHLC data has been fetched
        """
        return self._ohlc_timeframe

    def get_ticker(self) -> Optional[Ticker]:
        """Get the current ticker data."""
        if self._ticker is None:
            exchange_ticker = self.exchange._tickers.get(self.symbol)
            if exchange_ticker is not None:
                self._ticker = exchange_ticker

        if self._ticker is None:
            self.refresh()

        return self._ticker

    def get_price(self) -> Optional[float]:
        """Get the current price."""
        ticker = self.get_ticker()
        return ticker.last if ticker else None

    def get_volume(self) -> dict[str, Any]:
        """
        Get volume data for this market.

        Returns:
            Dict with baseVolume and quoteVolume
        """
        ticker = self.get_ticker()
        if ticker:
            return {
                "baseVolume": ticker.baseVolume,
                "quoteVolume": ticker.quoteVolume,
                "symbol": self.symbol,
                "base": self.base_currency,
                "quote": self.quote_currency,
                "price": ticker.last,
                "timestamp": ticker.timestamp,
                "datetime": ticker.datetime,
            }
        return {
            "baseVolume": None,
            "quoteVolume": None,
            "symbol": self.symbol,
            "base": self.base_currency,
            "quote": self.quote_currency,
            "price": None,
            "timestamp": None,
            "datetime": None,
        }

    def get_ohlc_latest(self) -> Optional[dict[str, Any]]:
        """Get the latest OHLC data."""
        if self._ohlc_data is None:
            self.fetch_ohlc()

        if self._ohlc_data and len(self._ohlc_data) > 0:
            latest = self._ohlc_data[-1]
            return {
                "Open": latest.open,
                "High": latest.high,
                "Low": latest.low,
                "Close": latest.close,
                "Volume": latest.volume,
                "Timestamp": latest.datetime or datetime.now(timezone.utc),
            }
        return None

    def get_ohlc_history(self) -> Optional[list[dict[str, Any]]]:
        """Get the complete OHLC history."""
        if self._ohlc_data is None:
            self.fetch_ohlc()

        if self._ohlc_data:
            result = []
            for entry in self._ohlc_data.get_ohlc_data():
                result.append(
                    {
                        "Open": entry.open,
                        "High": entry.high,
                        "Low": entry.low,
                        "Close": entry.close,
                        "Volume": entry.volume,
                        "Timestamp": entry.datetime or datetime.now(timezone.utc),
                    }
                )
            return result
        return None

    def get_ohlc_instances(self) -> Optional[OHLCVCollection]:
        """
        Get the OHLCVCollection instance.

        Returns:
            OHLCVCollection instance or None if no data available
        """
        if self._ohlc_data is None:
            self.fetch_ohlc()
        return self._ohlc_data

    def get_latest_ohlc_instance(self) -> Optional[OHLC]:
        """
        Get the latest OHLC instance.

        Returns:
            Latest OHLC instance or None if no data available
        """
        if self._ohlc_data is None:
            self.fetch_ohlc()

        if self._ohlc_data and len(self._ohlc_data) > 0:
            return self._ohlc_data[-1]
        return None

    def get_ohlcv_collection(self) -> Optional[OHLCVCollection]:
        """
        Get the OHLCVCollection instance if available.

        Returns:
            OHLCVCollection instance or None if not using collection format
        """
        if self._ohlc_data is None:
            self.fetch_ohlc()

        return self._ohlc_data

    def get_price_rows(self, price_type: str = "close") -> list[dict[str, Any]]:
        """Get normalized price rows from fetched OHLCV data."""
        collection = self.get_ohlcv_collection()
        if collection is None:
            return []
        return collection.get_price_list(price_type=price_type)

    def get_ohlcv_rows(self) -> list[dict[str, Any]]:
        """Get normalized OHLCV rows from fetched candle data."""
        collection = self.get_ohlcv_collection()
        if collection is None:
            return []

        rows: list[dict[str, Any]] = []
        for ohlc in collection.get_ohlc_data():
            rows.append(
                {
                    "timestamp": ohlc.timestamp,
                    "datetime": ohlc.datetime,
                    "open": ohlc.open,
                    "high": ohlc.high,
                    "low": ohlc.low,
                    "close": ohlc.close,
                    "volume": ohlc.volume,
                    "symbol": ohlc.symbol or self.symbol,
                    "timeframe": ohlc.timeframe or self._ohlc_timeframe,
                }
            )

        rows.sort(
            key=lambda row: (
                row["timestamp"] if isinstance(row.get("timestamp"), int) else 0
            )
        )
        return rows

    def get_formatted_price_list(
        self, price_type: str = "close"
    ) -> list[dict[str, Any]]:
        """
        Get a formatted price list from OHLC data.

        Args:
            price_type: Type of price to extract ('open', 'high', 'low', 'close',
                'typical', 'median')

        Returns:
            List of dictionaries with timestamp and price data
        """
        return self.get_price_rows(price_type=price_type)

    def get_price_range_analysis(self) -> dict[str, Any]:
        """
        Get price range analysis from OHLC data.

        Returns:
            Dictionary with price range statistics
        """
        collection = self.get_ohlcv_collection()
        if collection:
            return collection.get_price_range()
        return {"min_price": None, "max_price": None, "price_range": None}

    def get_volume_analysis(self) -> dict[str, Any]:
        """
        Get volume analysis from OHLC data.

        Returns:
            Dictionary with volume statistics
        """
        collection = self.get_ohlcv_collection()
        if collection:
            return collection.get_volume_summary()
        return {
            "total_volume": None,
            "avg_volume": None,
            "min_volume": None,
            "max_volume": None,
        }

    def get_timeframe_analysis(self) -> dict[str, Any]:
        """
        Get timeframe analysis from OHLC data.

        Returns:
            Dictionary with timeframe information
        """
        collection = self.get_ohlcv_collection()
        if collection:
            return collection.get_timeframe_info()
        return {"start_time": None, "end_time": None, "duration": None, "count": 0}

    def get_price_history(self) -> list[dict[str, Any]]:
        """Get historical price data generated from OHLC data."""
        if self._ohlc_data is None:
            self.fetch_ohlc()

        if not self._ohlc_data:
            return []

        # Generate historical prices from OHLC data
        historical_prices = []
        for ohlc_entry in self._ohlc_data.get_ohlc_data():
            historical_prices.append(
                {
                    "timestamp": ohlc_entry.datetime
                    or datetime.fromtimestamp(
                        ohlc_entry.timestamp / 1000, tz=timezone.utc
                    ),
                    "price": ohlc_entry.close,
                }
            )

        return historical_prices

    def format_price_to_precision(self, price: float) -> float:
        """
        Format price according to market precision.

        Args:
            price: The price to format

        Returns:
            The formatted price
        """
        return self._format_to_precision(
            value=price,
            method_name="price_to_precision",
            precision_key="price",
        )

    def format_amount_to_precision(self, amount: float) -> float:
        """
        Format amount according to market precision.

        Args:
            amount: The amount to format

        Returns:
            The formatted amount
        """
        return self._format_to_precision(
            value=amount,
            method_name="amount_to_precision",
            precision_key="amount",
        )

    def _format_to_precision(
        self,
        value: float,
        method_name: str,
        precision_key: str,
    ) -> float:
        """Format a numeric value using CCXT-native precision helpers when available."""
        if not isinstance(value, (int, float)):
            return value

        exchange = self.exchange.ccxt_exchange
        if exchange is not None:
            formatter = getattr(exchange, method_name, None)
            if callable(formatter):
                try:
                    formatted_value = formatter(self.symbol, value)
                    if isinstance(formatted_value, str):
                        return float(formatted_value)
                    if isinstance(formatted_value, (int, float)):
                        return float(formatted_value)
                except Exception as exc:
                    logger.debug(
                        "CCXT %s failed for %s on %s: %s",
                        method_name,
                        self.symbol,
                        self.exchange.name,
                        exc,
                    )

        return self._fallback_format_to_precision(value, precision_key)

    def _fallback_format_to_precision(self, value: float, precision_key: str) -> float:
        """Apply a minimal local precision fallback.

        Used when CCXT precision helpers are unavailable.
        """
        if not isinstance(value, (int, float)):
            return value

        precision = self.market_info.get("precision", {}).get(precision_key)
        if not isinstance(precision, (int, float)):
            return value

        if isinstance(precision, float) and precision > 0 and precision < 1:
            return round(value / precision) * precision

        if precision >= 0:
            format_str = f"{{:.{int(precision)}f}}"
            return float(format_str.format(value))

        return value

    def get_market_info(self) -> dict[str, Any]:
        """Get market metadata."""
        return self.market_info

    def get_limits(self) -> dict[str, Any]:
        """Get trading limits for this market."""
        return self.market_info.get("limits", {})

    def get_fees(self) -> dict[str, Any]:
        """Get fee information for this market."""
        return self.market_info.get("fee", {})
