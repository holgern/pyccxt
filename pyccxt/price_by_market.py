import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import ccxt

from .ticker import Ticker

logger = logging.getLogger(__name__)


class PriceByMarket:
    def __init__(
        self,
        base_currency="btc",
        quote_currency="eur",
        market="kraken",
        days_ago=1,
        min_refresh_time=120,
        interval="1h",
        enable_ohlc=True,
    ):
        """
        Initialize the PriceByMarket class.

        Args:
            market: The exchange to use (default: "kraken")
            days_ago: How many days of historical data to fetch (default: 1)
            min_refresh_time: Minimum time between refreshes in seconds (default: 120)
            interval: The interval for historical data (default: "1h")
            enable_ohlc: Whether to fetch OHLC data (default: True)
        """
        self.days_ago = days_ago
        self.interval = interval
        self.min_refresh_time = min_refresh_time  # seconds
        self.base_currency = base_currency.lower()
        self.quote_currency = quote_currency.lower()
        self.market = market.lower()
        self.enable_ohlc = enable_ohlc
        self._ticker: Ticker = None  # Store Ticker objects
        self._markets: dict[str, dict[str, Any]] = {}  # Store markets by symbol
        self._markets_by_id: dict[str, list[dict[str, Any]]] = {}  # Store markets by id
        self._currencies: dict[str, dict[str, Any]] = {}  # Store currencies
        self._current_price: float = 0.0 # Store current prices
        self._historical_prices = []  # Store historical prices
        self._ohlc_data = None  # Store OHLC data
        self._price_list = []  # Store accumulated price list
        self._last_update = None  # Last update timestamp

        # Get available exchange classes from ccxt
        self.available_markets = dir(ccxt)
        self.available_markets = [
            m
            for m in self.available_markets
            if m[0].islower() and not m.startswith("_")
        ]

        # Initialize exchange
        try:
            exchange_class = getattr(ccxt, self.market)
            self.exchange = exchange_class()
            self._load_markets()
        except Exception as e:
            logger.error(f"Error initializing exchange {market}: {e}")
            self.exchange = None

    def _load_markets(self, reload=False):
        """
        Load markets from the exchange.

        Args:
            reload: Whether to force reload the markets (default: False)

        Returns:
            Dict of markets indexed by symbol
        """
        if self.exchange is None:
            return {}

        try:
            markets = self.exchange.load_markets(reload=reload)
            self._markets = markets
            self._markets_by_id = {}

            # Create markets_by_id for easy lookup
            for _symbol, market in markets.items():
                market_id = market.get("id")
                if market_id is not None:
                    if market_id not in self._markets_by_id:
                        self._markets_by_id[market_id] = []
                    self._markets_by_id[market_id].append(market)

            # Store currencies
            self._currencies = (
                self.exchange.currencies if hasattr(self.exchange, "currencies") else {}
            )

            return markets
        except Exception as e:
            logger.error(f"Error loading markets: {e}")
            return {}

    def _fetch_prices(self):
        """Fetch prices and OHLC data from the exchange."""
        try:
            if self.exchange is None:
                return False

            self._current_price = 0.0  # Reset current price 

            # Define trading pairs
            trading_pair = f"{self.base_currency.upper()}/{self.quote_currency.upper()}"

            # Ensure we have the markets loaded
            if not self._markets:
                self._load_markets()

            # Fetch ticker data for the pairs
            try:
                # Check if the pair exists in the available markets
                if trading_pair in self._markets:
                    ccxt_ticker = self.exchange.fetch_ticker(trading_pair)
                    ticker = Ticker.from_ccxt(ccxt_ticker)
                    self._current_price = (
                        ticker.last if ticker.last is not None else 0
                    )
                    self._ticker = ticker
                else:
                    logger.warning(
                        f"Market {btc_usd_pair} not found in available markets"
                    )
                    self._current_prices["usd"] = 0
            except Exception as e:
                logger.error(f"Error fetching USD price: {e}")
                self._current_prices["usd"] = 0

            # Fetch OHLC data if enabled
            if self.enable_ohlc:
                self._fetch_ohlc_data(trading_pair)
            else:
                self._ohlc_data = None

            # Update timestamp
            self._last_update = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return False

    def _fetch_ohlc_data(self, symbol):
        """
        Fetch OHLC data for the given symbol.

        Args:
            symbol: The trading pair symbol to fetch data for

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if the symbol exists in the available markets
            if symbol not in self._markets:
                logger.warning(f"Symbol {symbol} not found in available markets")
                self._ohlc_data = None
                return False

            # Get market information for precision handling
            market = self._markets[symbol]

            # Convert interval to timeframe format used by ccxt
            timeframe = self._convert_interval_to_timeframe(self.interval)

            # Calculate start time (days ago from now)
            since = int(
                (datetime.now(timezone.utc) - timedelta(days=self.days_ago)).timestamp()
                * 1000
            )

            # Fetch OHLCV data for the specified number of days
            if self.exchange is not None:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since)

                if ohlcv and len(ohlcv) > 0:
                    # Store the full OHLCV data array
                    formatted_ohlcv = []
                    formatted_prices = []

                    for entry in ohlcv:
                        timestamp = datetime.fromtimestamp(
                            entry[0] / 1000, tz=timezone.utc
                        )
                        open_price, high_price, low_price, close_price, volume = entry[
                            1:6
                        ]

                        # Apply precision formatting if available
                        if "precision" in market and "price" in market["precision"]:
                            precision = market["precision"]["price"]
                            if isinstance(precision, (int, float)):
                                # Apply precision formatting based on exchange's mode
                                if hasattr(self.exchange, "precisionMode"):
                                    if self.exchange.precisionMode == ccxt.TICK_SIZE:
                                        # Round to the nearest tick size
                                        open_price = (
                                            round(open_price / precision) * precision
                                        )
                                        high_price = (
                                            round(high_price / precision) * precision
                                        )
                                        low_price = (
                                            round(low_price / precision) * precision
                                        )
                                        close_price = (
                                            round(close_price / precision) * precision
                                        )
                                    elif (
                                        self.exchange.precisionMode
                                        == ccxt.SIGNIFICANT_DIGITS
                                    ):
                                        # Format to significant digits
                                        format_str = f"{{:.{int(precision)}g}}"
                                        open_price = float(
                                            format_str.format(open_price)
                                        )
                                        high_price = float(
                                            format_str.format(high_price)
                                        )
                                        low_price = float(format_str.format(low_price))
                                        close_price = float(
                                            format_str.format(close_price)
                                        )
                                    else:
                                        # Format to decimal places
                                        format_str = f"{{:.{int(precision)}f}}"
                                        open_price = float(
                                            format_str.format(open_price)
                                        )
                                        high_price = float(
                                            format_str.format(high_price)
                                        )
                                        low_price = float(format_str.format(low_price))
                                        close_price = float(
                                            format_str.format(close_price)
                                        )

                        formatted_ohlcv.append(
                            {
                                "timestamp": timestamp,
                                "open": open_price,
                                "high": high_price,
                                "low": low_price,
                                "close": close_price,
                                "volume": volume,
                            }
                        )
                        formatted_prices.append(
                            {
                                "timestamp": timestamp,
                                "price": close_price,
                                "price_usd": None,  # No USD price in this request
                            }
                        )

                    self._historical_prices = formatted_prices
                    self._ohlc_data = formatted_ohlcv
                    return True
                else:
                    self._ohlc_data = None
                    self._historical_prices = []
                    return False
            return False
        except Exception as e:
            logger.error(f"Error fetching OHLC data: {e}")
            self._ohlc_data = None
            return False

    def _convert_interval_to_timeframe(self, interval):
        """
        Convert interval string to ccxt timeframe format.

        Args:
            interval: The interval string (e.g. "1h", "1d")

        Returns:
            The ccxt timeframe string
        """
        # Handle common formats
        interval = interval.lower()

        # Map of our interval format to ccxt timeframe format
        interval_map = {
            "1m": "1m",  # 1 minute
            "5m": "5m",  # 5 minutes
            "15m": "15m",  # 15 minutes
            "30m": "30m",  # 30 minutes
            "1h": "1h",  # 1 hour
            "2h": "2h",  # 2 hours
            "4h": "4h",  # 4 hours
            "1d": "1d",  # 1 day
            "1w": "1w",  # 1 week
        }

        return interval_map.get(interval, "1h")  # Default to 1h if not found

    def refresh(self):
        """
        Refresh the price data if necessary.

        Returns:
            bool: True if successful, False otherwise
        """
        # Check if we need to refresh based on time
        if hasattr(self, "_last_update") and self._last_update is not None:
            time_diff = (datetime.now(timezone.utc) - self._last_update).total_seconds()
            if time_diff < self.min_refresh_time:
                logger.debug(
                    f"Skipping refresh - last update was {time_diff} seconds ago"
                )
                return True

        # Fetch new data
        refresh_success = self._fetch_prices()

        # Initialize data structures if this is first successful fetch
        if refresh_success and not hasattr(self, "_price_list"):
            self._price_list = []

        # Add new price to the list if successful
        if refresh_success:
            current_price = {
                "timestamp": datetime.now(timezone.utc),
                "price": self._current_price,
            }
            self._price_list.append(current_price)

        return refresh_success

    def get_price_list(self):
        """Get the list of historical prices."""
        if not hasattr(self, "_price_list"):
            self._price_list = []
            self.refresh()

        # If we have historical data from the API, use that
        if self.enable_ohlc and hasattr(self, "_historical_prices"):
            result = []
            for entry in self._historical_prices:
                # Assuming the API returns timestamp and price in the format we need
                timestamp = entry.get("timestamp")
                price = entry.get("price")

                if timestamp and price:
                    result.append(
                        {"timestamp": timestamp, "price": price}
                    )
            return result

        # Otherwise return our accumulated price list
        return self._price_list

    def get_timeseries_list(self):
        """Alias for get_price_list for backward compatibility."""
        return self.get_price_list()

    @property
    def timeseries_stack(self):
        """Property accessor for price list for backward compatibility."""
        return self.get_price_list()

    def get_ticker(self, symbol="usd"):
        """
        Get the Ticker object for the specified symbol.

        Args:
            symbol: The symbol to get the ticker for (default: 'usd')

        Returns:
            The Ticker object or None if not available
        """
        if not hasattr(self, "_tickers"):
            self._tickers = {}
            self.refresh()

        return self._tickers.get(symbol.lower())

    def get_tickers(self):
        """
        Get all available Ticker objects.

        Returns:
            A dictionary of Ticker objects indexed by their symbol
        """
        if not hasattr(self, "_tickers"):
            self._tickers = {}
            self.refresh()

        return self._tickers

    def get_market(self, symbol):
        """
        Get the market structure for the specified symbol.

        Args:
            symbol: The symbol to get the market for

        Returns:
            The market structure or None if not available
        """
        return self._markets.get(symbol)

    def get_markets(self):
        """
        Get all available markets.

        Returns:
            A dictionary of market structures indexed by their symbol
        """
        return self._markets

    def get_markets_by_id(self):
        """
        Get all available markets indexed by their id.

        Returns:
            A dictionary of market structures indexed by their id
        """
        return self._markets_by_id
    
    def get_currency(self, code):
        """
        Get the currency structure for the specified code.

        Args:
            code: The currency code

        Returns:
            The currency structure or None if not available
        """
        return self._currencies.get(code)

    def get_currencies(self):
        """
        Get all available currencies.

        Returns:
            A dictionary of currency structures indexed by their code
        """
        return self._currencies

    @property
    def price(self):
        """Get the current price data as a dictionary."""
        # Ensure we have data
        if self._current_price == 0.0: 
            self.refresh()

        return {
            "price": self._current_price,
            "base_currency": self.base_currency.upper(),
            "quote_currency": self.quote_currency.upper(),
            "timestamp": self._last_update
            if hasattr(self, "_last_update") and self._last_update is not None
            else datetime.now(timezone.utc),
            "market": self.market,
        }

    @property
    def ohlc(self):
        """Get the OHLC (Open, High, Low, Close) data."""
        if not self.enable_ohlc:
            return None

        if not hasattr(self, "_ohlc_data") or self._ohlc_data is None:
            self.refresh()

        # Return None if we still don't have data after refresh
        if not hasattr(self, "_ohlc_data") or self._ohlc_data is None:
            return None

        # If we have days_ago of data, return the most recent entry by default
        if isinstance(self._ohlc_data, list) and len(self._ohlc_data) > 0:
            latest = self._ohlc_data[-1]  # Get the most recent entry
            return {
                "Open": latest.get("open", 0),
                "High": latest.get("high", 0),
                "Low": latest.get("low", 0),
                "Close": latest.get("close", 0),
                "Volume": latest.get("volume", 0),
                "Timestamp": latest.get("timestamp", datetime.now(timezone.utc)),
            }

        return None

    def get_ohlc_for_day(self, days_from_now=0):
        """
        Get OHLC data for a specific day in the past.

        Args:
            days_from_now: Days from now (0 = today, 1 = yesterday, etc.)

        Returns:
            dict: OHLC data for the specified day or None if not available
        """
        if not self.enable_ohlc:
            return None

        if not hasattr(self, "_ohlc_data") or self._ohlc_data is None:
            self.refresh()

        # Return None if we still don't have data after refresh
        if not isinstance(self._ohlc_data, list) or len(self._ohlc_data) == 0:
            return None

        # Calculate the target date (at midnight UTC)
        target_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=days_from_now)

        # Find the entry closest to the target date
        closest_entry = None
        min_diff = float("inf")

        for entry in self._ohlc_data:
            timestamp = entry.get("timestamp")
            if timestamp:
                # Calculate time difference in seconds
                diff = abs((timestamp - target_date).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest_entry = entry

        if closest_entry:
            return {
                "Open": closest_entry.get("open", 0),
                "High": closest_entry.get("high", 0),
                "Low": closest_entry.get("low", 0),
                "Close": closest_entry.get("close", 0),
                "Volume": closest_entry.get("volume", 0),
                "Timestamp": closest_entry.get("timestamp", datetime.now(timezone.utc)),
            }

        return None

    def get_ohlc_history(self):
        """
        Get the complete OHLC history data.

        Returns:
            list: List of OHLC data entries or None if not available
        """
        if not self.enable_ohlc:
            return None

        if not hasattr(self, "_ohlc_data") or self._ohlc_data is None:
            self.refresh()

        # Return None if we still don't have data after refresh
        if not isinstance(self._ohlc_data, list) or len(self._ohlc_data) == 0:
            return None

        # Convert the internal format to the public format
        formatted_history = []
        for entry in self._ohlc_data:
            formatted_history.append(
                {
                    "Open": entry.get("open", 0),
                    "High": entry.get("high", 0),
                    "Low": entry.get("low", 0),
                    "Close": entry.get("close", 0),
                    "Volume": entry.get("volume", 0),
                    "Timestamp": entry.get("timestamp", datetime.now(timezone.utc)),
                }
            )

        return formatted_history

    def set_days_ago(self, days_ago):
        """Set the number of days to fetch historical data for."""
        self.days_ago = days_ago

    def get_price_change(self):
        """Calculate price change percentage over the timeframe."""
        if not self.enable_ohlc:
            return None

        price_list = self.get_price_list()
        if not price_list or len(price_list) < 2:
            return None

        # Get first and last price in our timeframe
        first_price = price_list[0]["price"]
        last_price = price_list[-1]["price"]

        if first_price == 0:
            return None

        # Calculate percentage change
        change_pct = ((last_price - first_price) / first_price) * 100

        return {
            "change_pct": change_pct,
            "start_price": first_price,
            "end_price": last_price,
            "timeframe_days": self.days_ago,
        }


    def get_price(self):
        """Get the current price in USD."""
        current_price = self.price
        return current_price["price"]

    def get_timestamp(self):
        """Get the timestamp of the last price update."""
        if hasattr(self, "_last_update") and self._last_update is not None:
            return self._last_update
        return datetime.now(timezone.utc)

    def get_price_now(self):
        """Get the current price formatted as a string."""
        self.refresh()
        price_now = self.get_price()
        return f"{price_now:,.0f}" if price_now > 1000 else f"{price_now:.5g}"

    def format_price_to_precision(self, symbol, price):
        """
        Format price according to market precision.

        Args:
            symbol: The market symbol
            price: The price to format

        Returns:
            The formatted price
        """
        market = self.get_market(symbol)
        if market is None or not isinstance(price, (int, float)):
            return price

        if "precision" in market and "price" in market["precision"]:
            precision = market["precision"]["price"]
            if isinstance(precision, (int, float)):
                # Apply precision formatting based on exchange's mode
                if hasattr(self.exchange, "precisionMode"):
                    if self.exchange.precisionMode == ccxt.TICK_SIZE:
                        # Round to the nearest tick size
                        return round(price / precision) * precision
                    elif self.exchange.precisionMode == ccxt.SIGNIFICANT_DIGITS:
                        # Format to significant digits
                        format_str = f"{{:.{int(precision)}g}}"
                        return float(format_str.format(price))
                    else:
                        # Format to decimal places
                        format_str = f"{{:.{int(precision)}f}}"
                        return float(format_str.format(price))

        return price

    def format_amount_to_precision(self, symbol, amount):
        """
        Format amount according to market precision.

        Args:
            symbol: The market symbol
            amount: The amount to format

        Returns:
            The formatted amount
        """
        market = self.get_market(symbol)
        if market is None or not isinstance(amount, (int, float)):
            return amount

        if "precision" in market and "amount" in market["precision"]:
            precision = market["precision"]["amount"]
            if isinstance(precision, (int, float)):
                # Apply precision formatting based on exchange's mode
                if hasattr(self.exchange, "precisionMode"):
                    if self.exchange.precisionMode == ccxt.TICK_SIZE:
                        # Round to the nearest tick size
                        return round(amount / precision) * precision
                    elif self.exchange.precisionMode == ccxt.SIGNIFICANT_DIGITS:
                        # Format to significant digits
                        format_str = f"{{:.{int(precision)}g}}"
                        return float(format_str.format(amount))
                    else:
                        # Format to decimal places
                        format_str = f"{{:.{int(precision)}f}}"
                        return float(format_str.format(amount))

        return amount
