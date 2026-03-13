"""
OHLCV Collection module for pyccxt.

This module provides the OHLCVCollection class for managing collections of OHLC data
with enhanced functionality for price analysis and formatting.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


class OHLCVCollection:
    """
    A collection of OHLCV data with methods for analysis and price list generation.

    This class manages a collection of OHLC instances and provides convenient methods
    for accessing price data, generating formatted price lists, and performing
    basic analysis on the collection.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1h",
        ohlc_data: Optional[list[Any]] = None,
    ):
        """
        Initialize an OHLCVCollection instance.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/EUR')
            timeframe: Timeframe for the data (e.g., '1h', '1d')
            ohlc_data: Optional list of OHLC instances to initialize with
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self._ohlc_data: list[Any] = ohlc_data or []
        self._cached_price_list: Optional[list[dict[str, Any]]] = None
        self._last_cache_update: Optional[datetime] = None

    def __repr__(self) -> str:
        """
        Return a string representation of the OHLCVCollection instance.

        Returns:
            str: String representation showing symbol, timeframe, and data count
        """
        count = len(self._ohlc_data)
        latest_price = self.get_latest_price()
        price_str = f"{latest_price:.8f}" if latest_price is not None else "N/A"
        return (
            f"OHLCVCollection(symbol='{self.symbol}', timeframe='{self.timeframe}', "
            f"count={count}, latest={price_str})"
        )

    def add_ohlc(self, ohlc_instance: Any) -> None:
        """
        Add an OHLC instance to the collection.

        Args:
            ohlc_instance: OHLC instance to add
        """
        self._ohlc_data.append(ohlc_instance)
        self._invalidate_cache()

    def extend_ohlc(self, ohlc_instances: list[Any]) -> None:
        """
        Add multiple OHLC instances to the collection.

        Args:
            ohlc_instances: List of OHLC instances to add
        """
        self._ohlc_data.extend(ohlc_instances)
        self._invalidate_cache()

    def clear(self) -> None:
        """Clear all OHLC data from the collection."""
        self._ohlc_data.clear()
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        """Invalidate the cached price list."""
        self._cached_price_list = None
        self._last_cache_update = None

    def get_ohlc_data(self) -> list[Any]:
        """
        Get all OHLC instances in the collection.

        Returns:
            List of OHLC instances
        """
        return self._ohlc_data.copy()

    def get_price_list(self, price_type: str = "close") -> list[dict[str, Any]]:
        """
        Generate a formatted price list from the OHLC data.

        Args:
            price_type: Type of price to extract ('open', 'high', 'low', 'close',
                'typical', 'median')

        Returns:
            List of dictionaries with timestamp and price data
        """
        if not self._ohlc_data:
            return []

        # Use cache if available and valid
        if (
            self._cached_price_list is not None
            and price_type == "close"  # Only cache close prices for now
            and self._last_cache_update is not None
        ):
            return self._cached_price_list.copy()

        price_list = []

        for ohlc in self._ohlc_data:
            try:
                # Get the requested price type
                if price_type == "open":
                    price = ohlc.open
                elif price_type == "high":
                    price = ohlc.high
                elif price_type == "low":
                    price = ohlc.low
                elif price_type == "close":
                    price = ohlc.close
                elif price_type == "typical":
                    price = (
                        ohlc.get_typical_price()
                        if hasattr(ohlc, "get_typical_price")
                        else (ohlc.high + ohlc.low + ohlc.close) / 3
                    )
                elif price_type == "median":
                    price = (ohlc.high + ohlc.low) / 2
                else:
                    logger.warning(
                        f"Unknown price type '{price_type}', using close price"
                    )
                    price = ohlc.close

                # Get timestamp/datetime
                timestamp = None
                if hasattr(ohlc, "datetime") and ohlc.datetime:
                    timestamp = ohlc.datetime
                elif hasattr(ohlc, "timestamp") and ohlc.timestamp:
                    timestamp = datetime.fromtimestamp(
                        ohlc.timestamp / 1000, tz=timezone.utc
                    )
                else:
                    timestamp = datetime.now(timezone.utc)

                raw_timestamp = getattr(ohlc, "timestamp", None)

                price_entry = {
                    "timestamp": timestamp,
                    "timestamp_ms": raw_timestamp,
                    "price": price,
                    "symbol": self.symbol,
                    "timeframe": self.timeframe,
                    "price_type": price_type,
                }

                # Add volume if available
                if hasattr(ohlc, "volume") and ohlc.volume is not None:
                    price_entry["volume"] = ohlc.volume

                price_list.append(price_entry)

            except Exception as e:
                logger.error(f"Error processing OHLC data for price list: {e}")
                continue

        price_list.sort(
            key=lambda row: (
                row["timestamp_ms"] if isinstance(row.get("timestamp_ms"), int) else 0
            )
        )

        # Cache close prices
        if price_type == "close":
            self._cached_price_list = price_list.copy()
            self._last_cache_update = datetime.now(timezone.utc)

        return price_list

    def get_latest_price(self, price_type: str = "close") -> Optional[float]:
        """
        Get the latest price from the collection.

        Args:
            price_type: Type of price to get ('open', 'high', 'low', 'close',
                'typical', 'median')

        Returns:
            Latest price or None if no data available
        """
        if not self._ohlc_data:
            return None

        latest_ohlc = self._ohlc_data[-1]

        try:
            if price_type == "open":
                return latest_ohlc.open
            elif price_type == "high":
                return latest_ohlc.high
            elif price_type == "low":
                return latest_ohlc.low
            elif price_type == "close":
                return latest_ohlc.close
            elif price_type == "typical":
                return (
                    latest_ohlc.get_typical_price()
                    if hasattr(latest_ohlc, "get_typical_price")
                    else (latest_ohlc.high + latest_ohlc.low + latest_ohlc.close) / 3
                )
            elif price_type == "median":
                return (latest_ohlc.high + latest_ohlc.low) / 2
            else:
                logger.warning(f"Unknown price type '{price_type}', using close price")
                return latest_ohlc.close
        except Exception as e:
            logger.error(f"Error getting latest price: {e}")
            return None

    def get_price_range(self) -> dict[str, Optional[float]]:
        """
        Get the price range (min/max) across all data.

        Returns:
            Dictionary with min_price, max_price, and price_range
        """
        if not self._ohlc_data:
            return {"min_price": None, "max_price": None, "price_range": None}

        try:
            all_highs = [ohlc.high for ohlc in self._ohlc_data if ohlc.high is not None]
            all_lows = [ohlc.low for ohlc in self._ohlc_data if ohlc.low is not None]

            if not all_highs or not all_lows:
                return {"min_price": None, "max_price": None, "price_range": None}

            min_price = min(all_lows)
            max_price = max(all_highs)
            price_range = max_price - min_price

            return {
                "min_price": min_price,
                "max_price": max_price,
                "price_range": price_range,
            }
        except Exception as e:
            logger.error(f"Error calculating price range: {e}")
            return {"min_price": None, "max_price": None, "price_range": None}

    def get_volume_summary(self) -> dict[str, Optional[float]]:
        """
        Get volume summary statistics.

        Returns:
            Dictionary with total_volume, avg_volume, min_volume, max_volume
        """
        if not self._ohlc_data:
            return {
                "total_volume": None,
                "avg_volume": None,
                "min_volume": None,
                "max_volume": None,
            }

        try:
            volumes = [
                ohlc.volume for ohlc in self._ohlc_data if ohlc.volume is not None
            ]

            if not volumes:
                return {
                    "total_volume": None,
                    "avg_volume": None,
                    "min_volume": None,
                    "max_volume": None,
                }

            return {
                "total_volume": sum(volumes),
                "avg_volume": sum(volumes) / len(volumes),
                "min_volume": min(volumes),
                "max_volume": max(volumes),
            }
        except Exception as e:
            logger.error(f"Error calculating volume summary: {e}")
            return {
                "total_volume": None,
                "avg_volume": None,
                "min_volume": None,
                "max_volume": None,
            }

    def get_timeframe_info(self) -> dict[str, Any]:
        """
        Get information about the timeframe coverage.

        Returns:
            Dictionary with start_time, end_time, duration, and count
        """
        if not self._ohlc_data:
            return {
                "start_time": None,
                "end_time": None,
                "duration": None,
                "count": 0,
            }

        try:
            first_ohlc = self._ohlc_data[0]
            last_ohlc = self._ohlc_data[-1]

            # Get start time
            start_time = None
            if hasattr(first_ohlc, "datetime") and first_ohlc.datetime:
                start_time = first_ohlc.datetime
            elif hasattr(first_ohlc, "timestamp") and first_ohlc.timestamp:
                start_time = datetime.fromtimestamp(
                    first_ohlc.timestamp / 1000, tz=timezone.utc
                )

            # Get end time
            end_time = None
            if hasattr(last_ohlc, "datetime") and last_ohlc.datetime:
                end_time = last_ohlc.datetime
            elif hasattr(last_ohlc, "timestamp") and last_ohlc.timestamp:
                end_time = datetime.fromtimestamp(
                    last_ohlc.timestamp / 1000, tz=timezone.utc
                )

            # Calculate duration
            duration = None
            if start_time and end_time:
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(
                        start_time.replace("Z", "+00:00")
                    )
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                duration = end_time - start_time

            return {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "count": len(self._ohlc_data),
            }
        except Exception as e:
            logger.error(f"Error getting timeframe info: {e}")
            return {
                "start_time": None,
                "end_time": None,
                "duration": None,
                "count": len(self._ohlc_data),
            }

    def filter_by_time_range(
        self,
        start_time: Optional[Union[datetime, str]] = None,
        end_time: Optional[Union[datetime, str]] = None,
    ) -> "OHLCVCollection":
        """
        Create a new collection filtered by time range.

        Args:
            start_time: Start time for filtering (inclusive)
            end_time: End time for filtering (inclusive)

        Returns:
            New OHLCVCollection with filtered data
        """
        if not self._ohlc_data:
            return OHLCVCollection(self.symbol, self.timeframe)

        try:
            # Convert string times to datetime objects
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            filtered_data = []
            for ohlc in self._ohlc_data:
                # Get ohlc time
                ohlc_time = None
                if hasattr(ohlc, "datetime") and ohlc.datetime:
                    if isinstance(ohlc.datetime, str):
                        ohlc_time = datetime.fromisoformat(
                            ohlc.datetime.replace("Z", "+00:00")
                        )
                    else:
                        ohlc_time = ohlc.datetime
                elif hasattr(ohlc, "timestamp") and ohlc.timestamp:
                    ohlc_time = datetime.fromtimestamp(
                        ohlc.timestamp / 1000, tz=timezone.utc
                    )

                if ohlc_time:
                    # Check time range
                    if start_time and ohlc_time < start_time:
                        continue
                    if end_time and ohlc_time > end_time:
                        continue
                    filtered_data.append(ohlc)

            return OHLCVCollection(self.symbol, self.timeframe, filtered_data)

        except Exception as e:
            logger.error(f"Error filtering by time range: {e}")
            return OHLCVCollection(self.symbol, self.timeframe)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the collection to a dictionary format.

        Returns:
            Dictionary representation of the collection
        """
        ohlc_list = []
        for ohlc in self._ohlc_data:
            if hasattr(ohlc, "to_dict"):
                ohlc_list.append(ohlc.to_dict())
            else:
                # Fallback for non-OHLC objects
                ohlc_list.append(str(ohlc))

        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "count": len(self._ohlc_data),
            "ohlc_data": ohlc_list,
            "timeframe_info": self.get_timeframe_info(),
            "price_range": self.get_price_range(),
            "volume_summary": self.get_volume_summary(),
        }

    def __len__(self) -> int:
        """Return the number of OHLC entries in the collection."""
        return len(self._ohlc_data)

    def __getitem__(self, index: int) -> Any:
        """Get an OHLC entry by index."""
        return self._ohlc_data[index]

    def __iter__(self):
        """Iterate over OHLC entries."""
        return iter(self._ohlc_data)
