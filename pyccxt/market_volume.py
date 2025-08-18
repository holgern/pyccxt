import concurrent.futures
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import ccxt

from .ticker import Ticker

logger = logging.getLogger(__name__)


def get_market_volumes_for_pair(
    base_currency: str, quote_currency: str, max_exchanges: int = 15, timeout: int = 30
) -> List[Dict[str, Any]]:
    """
    Get the volume for a specific trading pair across all supported exchanges.

    Args:
        base_currency: The base currency (e.g., 'BTC')
        quote_currency: The quote currency (e.g., 'EUR')
        max_exchanges: Maximum number of exchanges to check (default: 15)
        timeout: Timeout in seconds for each exchange request (default: 30)

    Returns:
        List of dictionaries containing exchange name, volume, and other details,
        sorted by volume in descending order.
    """
    # Normalize currency codes
    base = base_currency.upper()
    quote = quote_currency.upper()
    symbol = f"{base}/{quote}"

    # Get all available exchanges
    exchanges = [ex for ex in ccxt.exchanges if not ex.startswith("_")]

    # Limit the number of exchanges to avoid excessive API calls
    if max_exchanges and max_exchanges > 0:
        exchanges = exchanges[:max_exchanges]

    results = []

    def fetch_exchange_volume(exchange_id):
        """Fetch volume for a specific exchange"""
        try:
            # Initialize the exchange
            exchange_class = getattr(ccxt, exchange_id)
            exchange = exchange_class(
                {"timeout": timeout * 1000}
            )  # timeout in milliseconds

            # Check if exchange supports fetchTicker
            if not exchange.has.get("fetchTicker", False):
                return None

            # Load markets to check if the symbol exists
            markets = exchange.load_markets()

            # Try different symbol formats if the exact one doesn't exist
            available_symbol = symbol
            if symbol not in markets:
                # Try with different quote currencies (USDT/USD)
                if quote == "USD" and f"{base}/USDT" in markets:
                    available_symbol = f"{base}/USDT"
                elif quote == "USDT" and f"{base}/USD" in markets:
                    available_symbol = f"{base}/USD"
                else:
                    # Check for any other symbol format variations
                    for market_symbol in markets:
                        parts = market_symbol.split("/")
                        if len(parts) == 2 and parts[0] == base and parts[1] == quote:
                            available_symbol = market_symbol
                            break
                    else:
                        # No matching symbol found
                        return None

            # Fetch ticker for the symbol
            ticker = exchange.fetch_ticker(available_symbol)

            # Extract volume information
            base_volume = ticker.get("baseVolume", 0)
            quote_volume = ticker.get("quoteVolume", 0)

            # Sometimes exchanges don't provide quoteVolume, calculate it if possible
            if quote_volume == 0 and base_volume > 0 and ticker.get("last", 0) > 0:
                quote_volume = base_volume * ticker.get("last", 0)

            return {
                "exchange": exchange_id,
                "symbol": available_symbol,
                "baseVolume": base_volume,
                "quoteVolume": quote_volume,
                "last": ticker.get("last", 0),
                "timestamp": ticker.get("timestamp"),
                "datetime": ticker.get("datetime"),
            }
        except Exception as e:
            logger.debug(f"Error fetching volume for {exchange_id}: {str(e)}")
            return None

    # Use thread pool to fetch data from exchanges concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(fetch_exchange_volume, exchange_id): exchange_id
            for exchange_id in exchanges
        }
        for future in concurrent.futures.as_completed(futures):
            exchange_id = futures[future]
            try:
                result = future.result()
                if result and result.get("baseVolume", 0) > 0:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Error processing result for {exchange_id}: {str(e)}")

    # Filter out results with None volumes and sort by quote volume in descending order
    valid_results = [
        r for r in results if r and isinstance(r.get("quoteVolume", 0), (int, float))
    ]
    valid_results.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)

    return valid_results


class MarketVolume:
    """
    A class to fetch and organize market volume data across exchanges.

    This class provides functionality to retrieve volume data for markets
    on a given exchange, with volume normalized to base  currency for comparison.

    By specifying a quote_currency, you can limit the data to only fetch the
    specific trading pairs base_currency/quote_currency and quote_currency/base_currency.
    This drastically improves performance and reduces API calls when you're only
    interested in specific currency pairs.
    """

    def __init__(
        self,
        market: str = "binance",
        min_refresh_time: int = 300,  # 5 minutes default refresh time
        base_currency: str = "BTC",  # Default base currency for normalization
        quote_currency: Optional[str] = None,  # Optional quote currency to filter by
        filter_by_base: bool = True,  # Whether to filter by base currency
    ):
        """
        Initialize the MarketVolume class.

        Args:
            market: The exchange to use (default: "binance")
            min_refresh_time: Minimum time between refreshes in seconds (default: 300)
            base_currency: The base currency to normalize volumes to (default: "BTC")
            quote_currency: Optional quote currency to filter tickers by (e.g., "EUR").
                           If specified, only base_currency/quote_currency and
                           quote_currency/base_currency pairs will be fetched.
            filter_by_base: Whether to filter markets by base currency (default: True)
        """
        self.market = market.lower()
        self.min_refresh_time = min_refresh_time
        self.base_currency = base_currency.upper()
        self.quote_currency = quote_currency.upper() if quote_currency else None
        self.filter_by_base = filter_by_base
        # Initialize storage variables
        self._markets: Dict[str, Dict[str, Any]] = {}
        self._tickers: Dict[str, Ticker] = {}
        self._volumes: List[Dict[str, Any]] = []
        self._prices: Dict[str, float] = {}
        self._last_update: Optional[datetime] = None

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

    def _load_markets(self, reload: bool = False) -> Dict:
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
            return markets
        except Exception as e:
            logger.error(f"Error loading markets: {e}")
            return {}

    def _fetch_prices(self) -> Dict[str, float]:
        """
        Fetch prices in various quote currencies to use for volume normalization.

        Returns:
            Dict of prices indexed by quote currency
        """
        if self.exchange is None:
            return {}

        prices = {}

        try:
            # Get commonly used quote currencies
            quote_currencies = set()
            for symbol in self._markets.keys():
                parts = symbol.split("/")
                if len(parts) == 2:
                    quote_currencies.add(parts[1])

            # Fetch  price in each quote currency
            for quote in quote_currencies:
                symbol = f"{self.base_currency}/{quote}"
                if symbol in self._markets:
                    try:
                        ticker = self.exchange.fetch_ticker(symbol)
                        if ticker and "last" in ticker and ticker["last"]:
                            prices[quote] = ticker["last"]
                    except Exception as e:
                        logger.debug(f"Could not fetch  price for {quote}: {e}")

                # Try reverse pair if direct pair not available
                if quote not in prices and quote != self.base_currency:
                    reverse_symbol = f"{quote}/{self.base_currency}"
                    if reverse_symbol in self._markets:
                        try:
                            ticker = self.exchange.fetch_ticker(reverse_symbol)
                            if (
                                ticker
                                and "last" in ticker
                                and ticker["last"]
                                and ticker["last"] > 0
                            ):
                                prices[quote] = 1 / ticker["last"]
                        except Exception as e:
                            logger.debug(
                                f"Could not fetch reverse  price for {quote}: {e}"
                            )

            self._prices = prices
            return prices
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {}

    def _fetch_all_tickers(self) -> Dict[str, Ticker]:
        """
        Fetch tickers for markets on the exchange.
        If quote_currency is specified, only fetch tickers for base_currency/quote_currency
        and quote_currency/base_currency pairs.

        Returns:
            Dict of Ticker objects indexed by symbol
        """
        if self.exchange is None:
            return {}

        try:
            # Check if exchange supports fetchTickers method
            if self.exchange.has["fetchTickers"]:
                if self.quote_currency:
                    # Only fetch the specific pairs we need when quote_currency is specified
                    direct_pair = f"{self.base_currency}/{self.quote_currency}"
                    inverse_pair = f"{self.quote_currency}/{self.base_currency}"

                    # Collect the pairs to fetch
                    filtered_symbols = []
                    if direct_pair in self._markets:
                        filtered_symbols.append(direct_pair)
                    if inverse_pair in self._markets:
                        filtered_symbols.append(inverse_pair)

                    # If neither direct nor inverse pair exists
                    if not filtered_symbols:
                        logger.warning(
                            f"Neither {direct_pair} nor {inverse_pair} found in available markets"
                        )
                        self._tickers = {}
                        return {}

                    # Fetch tickers individually for the filtered symbols
                    tickers = {}
                    for symbol in filtered_symbols:
                        try:
                            ccxt_ticker = self.exchange.fetch_ticker(symbol)
                            tickers[symbol] = Ticker.from_ccxt(ccxt_ticker)
                        except Exception as e:
                            logger.debug(f"Could not fetch ticker for {symbol}: {e}")
                    self._tickers = tickers
                    return tickers
                else:
                    # Fetch all tickers if no quote_currency specified
                    ccxt_tickers = self.exchange.fetch_tickers()
                    tickers = {}
                    for symbol, ccxt_ticker in ccxt_tickers.items():
                        tickers[symbol] = Ticker.from_ccxt(ccxt_ticker)
                    self._tickers = tickers
                    return tickers
            else:
                # Fallback to fetching tickers individually
                tickers = {}

                if self.quote_currency:
                    # Only fetch the specific pairs we need when quote_currency is specified
                    direct_pair = f"{self.base_currency}/{self.quote_currency}"
                    inverse_pair = f"{self.quote_currency}/{self.base_currency}"

                    # Collect the pairs to fetch
                    symbols_to_fetch = []
                    if direct_pair in self._markets:
                        symbols_to_fetch.append(direct_pair)
                    if inverse_pair in self._markets:
                        symbols_to_fetch.append(inverse_pair)

                    # If neither direct nor inverse pair exists
                    if not symbols_to_fetch:
                        logger.warning(
                            f"Neither {direct_pair} nor {inverse_pair} found in available markets"
                        )
                        self._tickers = {}
                        return {}
                else:
                    # Fetch all symbols if no quote_currency specified
                    symbols_to_fetch = list(self._markets.keys())

                for symbol in symbols_to_fetch:
                    try:
                        ccxt_ticker = self.exchange.fetch_ticker(symbol)
                        tickers[symbol] = Ticker.from_ccxt(ccxt_ticker)
                    except Exception as e:
                        logger.debug(f"Could not fetch ticker for {symbol}: {e}")
                self._tickers = tickers
                return tickers
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            return {}

    def _calculate_volumes(self) -> List[Dict[str, Any]]:
        """
        Calculate volumes in for markets.
        When quote_currency is specified, only calculates volumes for the
        base_currency/quote_currency and quote_currency/base_currency pairs.

        Returns:
            List of market data with volumes in Base Currency, 
        """
        volumes = []

        # Ensure we have the necessary data
        if not self._tickers or not self._prices:
            logger.debug("Missing tickers or  prices")
            return volumes

        for symbol, ticker in self._tickers.items():
            try:
                if not ticker.baseVolume or not ticker.quoteVolume:
                    logger.debug(f"Missing volume data for {symbol}")
                    continue

                # Parse symbol to get base and quote currencies
                parts = symbol.split("/")
                if len(parts) != 2:
                    logger.debug(f"Invalid symbol format: {symbol}")
                    continue

                base, quote = parts

                # Apply base currency filter only if enabled and not using BTC as base currency
                if (
                    self.filter_by_base
                    and base != self.base_currency
                ):
                    logger.debug(
                        f"Skipping {symbol} due to base currency filter: {self.base_currency}"
                    )
                    continue

                # Parse symbol to get base and quote currencies
                parts = symbol.split("/")
                if len(parts) != 2:
                    continue

                base, quote = parts

                # Skip pairs that don't have the base currency as the base in the symbol
                # This is the primary filter - only show pairs where base matches the specified base_currency
                if self.filter_by_base and base != self.base_currency:
                    # Skip this pair because it doesn't match our base currency filter
                    logger.debug(
                        f"Skipping {symbol} due to base currency filter: {self.base_currency}"
                    )
                    continue

                # Skip if the pair doesn't match our filtering requirements for quote currency
                if self.quote_currency:
                    # For quote_currency mode, we only process the direct or inverse pair
                    direct_pair = (
                        base == self.base_currency and quote == self.quote_currency
                    )
                    inverse_pair = (
                        base == self.quote_currency and quote == self.base_currency
                    )
                    if not (direct_pair or inverse_pair):
                        continue

                # Calculate  volume
                volume = None

                # Case 1: Base currency 
                if base == self.base_currency:
                    volume = ticker.baseVolume

                # Case 2: Quote currency
                elif quote == self.base_currency:
                    volume = ticker.quoteVolume

                # Case 3: Convert using known prices
                elif quote in self._prices:
                    volume = ticker.quoteVolume / self._prices[quote]

                # Case 4: Try to find a conversion path
                else:
                    # This would require more complex conversion logic
                    # For simplicity, we'll skip markets we can't convert directly
                    continue

                if volume is not None and volume > 0:
                    volumes.append(
                        {
                            "symbol": symbol,
                            "base": base,
                            "quote": quote,
                            "baseVolume": ticker.baseVolume,
                            "quoteVolume": ticker.quoteVolume,
                            "volume": volume,
                            "price": ticker.last,
                            "timestamp": ticker.timestamp,
                            "datetime": ticker.datetime,
                        }
                    )
            except Exception as e:
                logger.debug(f"Error calculating volume for {symbol}: {e}")

        # Sort by volume in descending order
        volumes.sort(key=lambda x: x["volume"], reverse=True)
        self._volumes = volumes
        return volumes

    def refresh(self) -> bool:
        """
        Refresh market data if necessary.

        Returns:
            bool: True if successful, False otherwise
        """
        # Check if we need to refresh based on time
        if self._last_update is not None:
            # Make sure both datetimes are timezone-aware or timezone-naive for comparison
            current_time = datetime.now(timezone.utc)

            # Convert _last_update to timezone-aware if it's naive
            last_update = self._last_update
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)

            time_diff = (current_time - last_update).total_seconds()
            if time_diff < self.min_refresh_time:
                logger.debug(
                    f"Skipping refresh - last update was {time_diff} seconds ago"
                )
                return True

        # Load markets if not already loaded
        if not self._markets:
            self._load_markets()

        # Fetch prices for normalization
        self._fetch_prices()

        # Fetch all tickers
        self._fetch_all_tickers()

        # Calculate volumes
        self._calculate_volumes()

        # Update timestamp
        self._last_update = datetime.now(timezone.utc)
        return True

    def get_volumes(
        self, limit: Optional[int] = None, min_volume: float = 0
    ) -> List[Dict[str, Any]]:
        """
        Get the list of markets with their volumes in Basecurrency.

        Args:
            limit: Maximum number of markets to return (default: None = all)
            min_volume: Minimum base currency volume for filtering markets (default: 0)

        Returns:
            List of market data with volumes in base currency, sorted by volume
        """
        # Refresh if no data available
        if not self._volumes:
            self.refresh()

        # Filter by minimum volume
        filtered = [v for v in self._volumes if v["volume"] >= min_volume]

        # Apply limit if provided
        if limit is not None and limit > 0:
            return filtered[:limit]

        return filtered

    def get_total_volume(self) -> float:
        """
        Get the total trading volume across all markets in base currency.

        Returns:
            Total volume in base currency
        """
        if not self._volumes:
            self.refresh()

        return sum(v["volume"] for v in self._volumes)

    def get_volume_by_quote_currency(self) -> Dict[str, float]:
        """
        Get the trading volume grouped by quote currency.

        Returns:
            Dict of volumes indexed by quote currency
        """
        if not self._volumes:
            self.refresh()

        result = {}
        for v in self._volumes:
            quote = v["quote"]
            if quote not in result:
                result[quote] = 0
            result[quote] += v["volume"]

        # Sort by volume in descending order
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def get_volume_by_base_currency(self) -> Dict[str, float]:
        """
        Get the trading volume grouped by base currency.

        Returns:
            Dict of volumes indexed by base currency
        """
        if not self._volumes:
            self.refresh()

        result = {}
        for v in self._volumes:
            base = v["base"]
            if base not in result:
                result[base] = 0
            result[base] += v["volume"]

        # Sort by volume in descending order
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def get_top_markets(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the top markets by volume.

        Args:
            limit: Maximum number of markets to return (default: 10)

        Returns:
            List of top markets by volume
        """
        return self.get_volumes(limit=limit)

    def get_exchange(self) -> str:
        """
        Get the exchange name.

        Returns:
            Exchange name
        """
        return self.market

    def get_timestamp(self) -> Optional[datetime]:
        """
        Get the timestamp of the last data update.

        Returns:
            Timestamp of the last update or None if not available
        """
        return self._last_update
