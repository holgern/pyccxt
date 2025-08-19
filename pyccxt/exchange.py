from __future__ import annotations

import concurrent.futures
import logging
from datetime import datetime, timezone
from typing import Any

import ccxt

from .market import Market
from .ticker import Ticker

logger = logging.getLogger(__name__)


class Exchange:
    """
    Manages a single cryptocurrency exchange and its markets.

    This class provides functionality to interact with all markets on a given
    exchange, fetch tickers, calculate volumes, and manage market data.
    """

    def __init__(
        self,
        exchange_name: str = "binance",
        min_refresh_time: int = 300,
        timeout: int = 30000,
    ):
        """
        Initialize the Exchange.

        Args:
            exchange_name: Name of the exchange (default: "binance")
            min_refresh_time: Minimum time between refreshes in seconds (default: 300)
            timeout: Request timeout in milliseconds (default: 30000)
        """
        self.name = exchange_name.lower()
        self.min_refresh_time = min_refresh_time
        self.timeout = timeout

        # Data storage
        self._markets: dict[str, dict[str, Any]] = {}
        self._market_instances: dict[str, Market] = {}
        self._tickers: dict[str, Ticker] = {}
        self._currencies: dict[str, dict[str, Any]] = {}
        self._last_update: datetime | None = None

        # Initialize exchange
        try:
            exchange_class = getattr(ccxt, self.name)
            self.ccxt_exchange = exchange_class(
                {
                    "timeout": self.timeout,
                    "enableRateLimit": True,
                }
            )
            self._load_markets()
        except Exception as e:
            logger.error(f"Error initializing exchange {exchange_name}: {e}")
            self.ccxt_exchange = None

    def __repr__(self) -> str:
        """
        Return a string representation of the Exchange instance.

        Returns:
            str: String representation showing exchange name, status, and market count
        """
        status = "connected" if self.ccxt_exchange else "disconnected"
        market_count = len(self._markets)
        return (
            f"Exchange(name='{self.name}', status='{status}', markets={market_count})"
        )

    def _load_markets(self, reload: bool = False) -> dict[str, dict[str, Any]]:
        """
        Load markets from the exchange.

        Args:
            reload: Whether to force reload markets

        Returns:
            Dict of markets indexed by symbol
        """
        if self.ccxt_exchange is None:
            return {}

        try:
            markets = self.ccxt_exchange.load_markets(reload=reload)
            self._markets = markets

            # Store currencies
            self._currencies = getattr(self.ccxt_exchange, "currencies", {})

            # Clear market instances on reload
            if reload:
                self._market_instances.clear()

            return markets
        except Exception as e:
            logger.error(f"Error loading markets: {e}")
            return {}

    def get_market(self, symbol: str) -> Market | None:
        """
        Get a Market instance for the specified symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/EUR')

        Returns:
            Market instance or None if not found
        """
        # Import here to avoid circular import
        from .market import Market

        if symbol not in self._markets:
            return None

        if symbol not in self._market_instances:
            market_info = self._markets[symbol]
            parts = symbol.split("/")
            if len(parts) == 2:
                base, quote = parts
                self._market_instances[symbol] = Market(
                    exchange=self,
                    symbol=symbol,
                    base_currency=base,
                    quote_currency=quote,
                    market_info=market_info,
                    min_refresh_time=self.min_refresh_time,
                )

        return self._market_instances.get(symbol)

    def get_markets_by_base(self, base_currency: str) -> list[Market]:
        """
        Get all markets with the specified base currency.

        Args:
            base_currency: Base currency to filter by

        Returns:
            List of Market instances
        """
        base = base_currency.upper()
        markets = []

        for symbol in self._markets:
            parts = symbol.split("/")
            if len(parts) == 2 and parts[0] == base:
                market = self.get_market(symbol)
                if market:
                    markets.append(market)

        return markets

    def get_markets_by_quote(self, quote_currency: str) -> list[Market]:
        """
        Get all markets with the specified quote currency.

        Args:
            quote_currency: Quote currency to filter by

        Returns:
            List of Market instances
        """
        quote = quote_currency.upper()
        markets = []

        for symbol in self._markets:
            parts = symbol.split("/")
            if len(parts) == 2 and parts[1] == quote:
                market = self.get_market(symbol)
                if market:
                    markets.append(market)

        return markets

    def get_all_markets(self) -> list[Market]:
        """
        Get all available markets.

        Returns:
            List of all Market instances
        """
        markets = []
        for symbol in self._markets:
            market = self.get_market(symbol)
            if market:
                markets.append(market)
        return markets

    def fetch_all_tickers(self) -> dict[str, Ticker]:
        """
        Fetch tickers for all markets on the exchange.

        Returns:
            Dict of Ticker objects indexed by symbol
        """
        if self.ccxt_exchange is None:
            return {}

        try:
            if self.ccxt_exchange.has.get("fetchTickers", False):
                ccxt_tickers = self.ccxt_exchange.fetch_tickers()
                tickers = {}
                for symbol, ccxt_ticker in ccxt_tickers.items():
                    tickers[symbol] = Ticker.from_ccxt(ccxt_ticker)
                self._tickers = tickers
                return tickers
            else:
                # Fallback to individual ticker fetching
                tickers = {}
                for symbol in self._markets:
                    try:
                        ccxt_ticker = self.ccxt_exchange.fetch_ticker(symbol)
                        tickers[symbol] = Ticker.from_ccxt(ccxt_ticker)
                    except Exception as e:
                        logger.debug(f"Could not fetch ticker for {symbol}: {e}")
                self._tickers = tickers
                return tickers
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            return {}

    def get_market_volumes(
        self,
        base_currency: str | None = None,
        min_volume: float = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get volume data for markets, optionally filtered by base currency.

        Args:
            base_currency: Filter by base currency (default: None = all)
            min_volume: Minimum volume threshold
            limit: Maximum number of results

        Returns:
            List of market volume data sorted by volume
        """
        if base_currency:
            markets = self.get_markets_by_base(base_currency)
        else:
            markets = self.get_all_markets()

        volumes = []
        for market in markets:
            volume_data = market.get_volume()
            if (volume_data.get("baseVolume", 0) or 0) >= min_volume:
                # Normalize volume to base currency if needed
                normalized_volume = self._normalize_volume(
                    volume_data, base_currency or "USD"
                )
                if normalized_volume is not None:
                    volume_data["normalizedVolume"] = normalized_volume
                    volumes.append(volume_data)

        # Sort by normalized volume or base volume
        volumes.sort(
            key=lambda x: x.get("normalizedVolume", x.get("baseVolume", 0) or 0),
            reverse=True,
        )

        if limit is not None and limit > 0:
            return volumes[:limit]

        return volumes

    def _normalize_volume(
        self, volume_data: dict[str, Any], target_currency: str
    ) -> float | None:
        """
        Normalize volume to target currency.

        Args:
            volume_data: Volume data dict
            target_currency: Currency to normalize to

        Returns:
            Normalized volume or None if conversion not possible
        """
        base = volume_data.get("base")
        quote = volume_data.get("quote")
        base_volume = volume_data.get("baseVolume")
        quote_volume = volume_data.get("quoteVolume")
        price = volume_data.get("price")

        if not base_volume or not quote_volume or not price:
            return None

        # If base currency is already target currency
        if base == target_currency:
            return base_volume

        # If quote currency is target currency
        if quote == target_currency:
            return quote_volume

        # Try to find conversion rate to target currency
        if base and isinstance(base, str):
            conversion_rate = self._get_conversion_rate(base, target_currency)
            if conversion_rate is not None:
                return base_volume * conversion_rate

        if quote and isinstance(quote, str):
            conversion_rate = self._get_conversion_rate(quote, target_currency)
            if conversion_rate is not None:
                return quote_volume * conversion_rate

        return None

    def _get_conversion_rate(
        self, from_currency: str, to_currency: str
    ) -> float | None:
        """
        Get conversion rate between two currencies.

        Args:
            from_currency: Source currency
            to_currency: Target currency

        Returns:
            Conversion rate or None if not available
        """
        if from_currency == to_currency:
            return 1.0

        # Try direct pair
        direct_symbol = f"{from_currency}/{to_currency}"
        if direct_symbol in self._tickers:
            return self._tickers[direct_symbol].last

        # Try reverse pair
        reverse_symbol = f"{to_currency}/{from_currency}"
        if reverse_symbol in self._tickers:
            reverse_rate = self._tickers[reverse_symbol].last
            return 1 / reverse_rate if reverse_rate and reverse_rate > 0 else None

        return None

    def get_total_volume(self, base_currency: str | None = None) -> float:
        """
        Get total trading volume across markets.

        Args:
            base_currency: Filter by base currency

        Returns:
            Total volume in base currency
        """
        volumes = self.get_market_volumes(base_currency=base_currency)
        return sum(
            v.get("normalizedVolume", v.get("baseVolume", 0) or 0) for v in volumes
        )

    def get_volume_by_quote_currency(self) -> dict[str, float]:
        """
        Get trading volume grouped by quote currency.

        Returns:
            Dict of volumes indexed by quote currency
        """
        volumes = self.get_market_volumes()
        result = {}

        for v in volumes:
            quote = v.get("quote")
            if quote:
                if quote not in result:
                    result[quote] = 0
                result[quote] += v.get("normalizedVolume", v.get("baseVolume", 0) or 0)

        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def refresh_all(self) -> bool:
        """
        Refresh all market data.

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
                    f"Skipping refresh - last update was {time_diff} seconds ago"
                )
                return True

        try:
            # Fetch all tickers
            self.fetch_all_tickers()
            self._last_update = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.error(f"Error refreshing exchange data: {e}")
            return False

    def get_available_symbols(self) -> list[str]:
        """Get list of available trading symbols."""
        return list(self._markets.keys())

    def get_currencies(self) -> dict[str, dict[str, Any]]:
        """Get available currencies information."""
        return self._currencies

    def get_exchange_info(self) -> dict[str, Any]:
        """Get exchange information."""
        if self.ccxt_exchange is None:
            return {}

        return {
            "name": self.name,
            "has": getattr(self.ccxt_exchange, "has", {}),
            "timeframes": getattr(self.ccxt_exchange, "timeframes", {}),
            "markets_count": len(self._markets),
            "last_update": self._last_update,
        }


def get_market_volumes_for_pair(
    base_currency: str, quote_currency: str, max_exchanges: int = 15, timeout: int = 30
) -> list[dict[str, Any]]:
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
            exchange = Exchange(exchange_id, timeout=timeout * 1000)
            if exchange.ccxt_exchange is None:
                return None

            market = exchange.get_market(symbol)
            if market is None:
                # Try alternative symbol formats
                if quote == "USD" and exchange.get_market(f"{base}/USDT"):
                    market = exchange.get_market(f"{base}/USDT")
                elif quote == "USDT" and exchange.get_market(f"{base}/USD"):
                    market = exchange.get_market(f"{base}/USD")
                else:
                    return None

            if market:
                volume_data = market.get_volume()
                if volume_data and volume_data.get("baseVolume", 0) > 0:
                    return {
                        "exchange": exchange_id,
                        "symbol": volume_data["symbol"],
                        "baseVolume": volume_data["baseVolume"],
                        "quoteVolume": volume_data["quoteVolume"],
                        "last": volume_data["price"],
                        "timestamp": volume_data["timestamp"],
                        "datetime": volume_data["datetime"],
                    }
            return None
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
