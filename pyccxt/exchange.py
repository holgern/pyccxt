from __future__ import annotations

import concurrent.futures
import importlib
import logging
from datetime import datetime, timezone
from typing import Any

from .exceptions import (
    ExchangeInitializationError,
    ExchangeNotFoundError,
    MarketLoadError,
    PyCCXTError,
    TickerFetchError,
    VolumeNormalizationError,
)
from .market import Market
from .ticker import Ticker

logger = logging.getLogger(__name__)


def _import_ccxt() -> Any:
    return importlib.import_module("ccxt")


def _volume_sort_key(row: dict[str, Any]) -> tuple[int, float]:
    normalized = row.get("normalizedVolume")
    if isinstance(normalized, (int, float)):
        return (3, float(normalized))

    quote_volume = row.get("quoteVolume")
    if isinstance(quote_volume, (int, float)):
        return (2, float(quote_volume))

    base_volume = row.get("baseVolume")
    if isinstance(base_volume, (int, float)):
        return (1, float(base_volume))

    return (0, 0.0)


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
        self.ccxt_exchange: Any = None

        # Initialize exchange
        try:
            ccxt = _import_ccxt()
        except Exception as exc:
            raise ExchangeInitializationError(
                "Failed to import ccxt while initializing "
                f"exchange '{self.name}': {exc}"
            ) from exc

        try:
            exchange_class = getattr(ccxt, self.name)
        except AttributeError as exc:
            raise ExchangeNotFoundError(
                f"Exchange '{self.name}' is not supported by ccxt."
            ) from exc

        try:
            self.ccxt_exchange = exchange_class(
                {
                    "timeout": self.timeout,
                    "enableRateLimit": True,
                }
            )
            self._load_markets()
        except PyCCXTError:
            raise
        except Exception as exc:
            raise ExchangeInitializationError(
                f"Failed to initialize exchange '{self.name}': {exc}"
            ) from exc

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

        Raises:
            MarketLoadError: If markets cannot be loaded from the exchange.
        """
        if self.ccxt_exchange is None:
            raise MarketLoadError(
                "Cannot load markets for exchange "
                f"'{self.name}': exchange is not initialized."
            )

        try:
            markets = self.ccxt_exchange.load_markets(reload=reload)
            self._markets = markets

            # Store currencies
            self._currencies = getattr(self.ccxt_exchange, "currencies", {})

            # Clear market instances on reload
            if reload:
                self._market_instances.clear()

            return markets
        except Exception as exc:
            raise MarketLoadError(
                f"Failed to load markets for exchange '{self.name}': {exc}"
            ) from exc

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

        Raises:
            TickerFetchError: If ticker data cannot be fetched for the exchange.
        """
        if self.ccxt_exchange is None:
            raise TickerFetchError(
                "Cannot fetch tickers for exchange "
                f"'{self.name}': exchange is not initialized."
            )

        try:
            if self.ccxt_exchange.has.get("fetchTickers", False):
                ccxt_tickers = self.ccxt_exchange.fetch_tickers()
                tickers = {}
                for symbol, ccxt_ticker in ccxt_tickers.items():
                    tickers[symbol] = Ticker.from_ccxt(ccxt_ticker)
                self._tickers = tickers
                return tickers
        except Exception as exc:
            raise TickerFetchError(
                f"Failed to fetch bulk tickers for exchange '{self.name}': {exc}"
            ) from exc

        tickers = {}
        for symbol in self._markets:
            try:
                ccxt_ticker = self.ccxt_exchange.fetch_ticker(symbol)
                tickers[symbol] = Ticker.from_ccxt(ccxt_ticker)
            except Exception as exc:
                logger.debug(
                    "Could not fetch ticker for %s on %s: %s", symbol, self.name, exc
                )

        if not tickers and self._markets:
            raise TickerFetchError(
                f"Failed to fetch tickers for all markets on exchange '{self.name}'."
            )

        self._tickers = tickers
        return tickers

    def get_market_volumes(
        self,
        filter_base: str | None = None,
        filter_quote: str | None = None,
        normalize_to: str | None = "USD",
        min_volume: float = 0,
        limit: int | None = None,
        include_unconverted: bool = True,
        base_currency: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get volume data for markets with explicit filtering and normalization.

        Args:
            filter_base: Filter markets by base currency.
            filter_quote: Filter markets by quote currency.
            normalize_to: Currency used for normalized volume values.
            min_volume: Minimum native base volume threshold.
            limit: Maximum number of results after sorting.
            include_unconverted: Keep rows with no normalized volume when True.
            base_currency: Deprecated alias for ``filter_base``.

        Returns:
            List of market volume rows sorted by normalized volume.
        """
        if filter_base is None and base_currency is not None:
            filter_base = base_currency

        normalized_target = normalize_to.upper() if normalize_to else None
        filtered_base = filter_base.upper() if filter_base else None
        filtered_quote = filter_quote.upper() if filter_quote else None

        markets = self.get_all_markets()
        if self._markets and not self._tickers:
            self.fetch_all_tickers()

        volumes = []
        for market in markets:
            if filtered_base and market.base_currency != filtered_base:
                continue
            if filtered_quote and market.quote_currency != filtered_quote:
                continue

            volume_data = market.get_volume()
            if (volume_data.get("baseVolume", 0) or 0) >= min_volume:
                volume_row = self._build_volume_row(
                    volume_data=volume_data,
                    normalize_to=normalized_target,
                )
                if include_unconverted or volume_row["normalizedVolume"] is not None:
                    volumes.append(volume_row)

        volumes.sort(key=_volume_sort_key, reverse=True)

        if limit is not None and limit > 0:
            return volumes[:limit]

        return volumes

    def _build_volume_row(
        self,
        volume_data: dict[str, Any],
        normalize_to: str | None,
    ) -> dict[str, Any]:
        """Create a standardized market-volume row."""
        normalized_volume = None
        is_normalized = False

        if normalize_to is not None:
            normalized_volume = self._normalize_volume(volume_data, normalize_to)
            is_normalized = normalized_volume is not None

        return {
            "symbol": volume_data.get("symbol"),
            "base": volume_data.get("base"),
            "quote": volume_data.get("quote"),
            "price": volume_data.get("price"),
            "baseVolume": volume_data.get("baseVolume"),
            "quoteVolume": volume_data.get("quoteVolume"),
            "normalizedVolume": normalized_volume,
            "normalizedCurrency": normalize_to,
            "isNormalized": is_normalized,
            "timestamp": volume_data.get("timestamp"),
            "datetime": volume_data.get("datetime"),
        }

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
        if not target_currency:
            raise VolumeNormalizationError(
                f"Invalid normalization target for exchange '{self.name}'."
            )

        base = volume_data.get("base")
        quote = volume_data.get("quote")
        base_volume = volume_data.get("baseVolume")
        quote_volume = volume_data.get("quoteVolume")
        target = target_currency.upper()

        # If base currency is already target currency
        if base == target and isinstance(base_volume, (int, float)):
            return base_volume

        # If quote currency is target currency
        if quote == target and isinstance(quote_volume, (int, float)):
            return quote_volume

        # Try to find conversion rate to target currency
        if base and isinstance(base, str) and isinstance(base_volume, (int, float)):
            conversion_rate = self._get_conversion_rate(base, target)
            if conversion_rate is not None and conversion_rate > 0:
                return base_volume * conversion_rate

        if quote and isinstance(quote, str) and isinstance(quote_volume, (int, float)):
            conversion_rate = self._get_conversion_rate(quote, target)
            if conversion_rate is not None and conversion_rate > 0:
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

    def get_total_volume(
        self,
        filter_base: str | None = None,
        filter_quote: str | None = None,
        normalize_to: str | None = "USD",
        min_volume: float = 0,
        include_unconverted: bool = False,
        base_currency: str | None = None,
    ) -> float:
        """
        Get total normalized trading volume across markets.

        Args:
            filter_base: Filter markets by base currency.
            filter_quote: Filter markets by quote currency.
            normalize_to: Currency used for normalized volume values.
            min_volume: Minimum native base volume threshold.
            include_unconverted: Include rows without normalized values.
            base_currency: Deprecated alias for ``filter_base``.

        Returns:
            Total normalized volume.
        """
        volumes = self.get_market_volumes(
            filter_base=filter_base,
            filter_quote=filter_quote,
            normalize_to=normalize_to,
            min_volume=min_volume,
            include_unconverted=include_unconverted,
            base_currency=base_currency,
        )
        return sum(
            float(v["normalizedVolume"])
            for v in volumes
            if isinstance(v.get("normalizedVolume"), (int, float))
        )

    def get_volume_by_quote_currency(
        self,
        filter_base: str | None = None,
        filter_quote: str | None = None,
        min_volume: float = 0,
        base_currency: str | None = None,
    ) -> dict[str, float]:
        """
        Get trading volume grouped by quote currency in native quote units.

        Args:
            filter_base: Filter markets by base currency.
            filter_quote: Filter markets by quote currency.
            min_volume: Minimum native base volume threshold.
            base_currency: Deprecated alias for ``filter_base``.

        Returns:
            Dict of quote-volume totals indexed by quote currency.
        """
        if filter_base is None and base_currency is not None:
            filter_base = base_currency

        volumes = self.get_market_volumes(
            filter_base=filter_base,
            filter_quote=filter_quote,
            normalize_to=None,
            min_volume=min_volume,
        )
        result: dict[str, float] = {}

        for v in volumes:
            quote = v.get("quote")
            quote_volume = v.get("quoteVolume")
            if quote and isinstance(quote_volume, (int, float)):
                if quote not in result:
                    result[quote] = 0.0
                result[quote] += float(quote_volume)

        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def get_volume_by_base_currency(
        self,
        filter_base: str | None = None,
        filter_quote: str | None = None,
        min_volume: float = 0,
        base_currency: str | None = None,
    ) -> dict[str, float]:
        """Get trading volume grouped by base currency in native base units."""
        if filter_base is None and base_currency is not None:
            filter_base = base_currency

        volumes = self.get_market_volumes(
            filter_base=filter_base,
            filter_quote=filter_quote,
            normalize_to=None,
            min_volume=min_volume,
        )
        result: dict[str, float] = {}

        for v in volumes:
            base = v.get("base")
            base_volume = v.get("baseVolume")
            if base and isinstance(base_volume, (int, float)):
                if base not in result:
                    result[base] = 0.0
                result[base] += float(base_volume)

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
        except PyCCXTError:
            raise
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
    base_currency: str,
    quote_currency: str,
    max_exchanges: int = 15,
    timeout: int = 30,
    exchange_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Get the volume for a specific trading pair across all supported exchanges.

    Args:
        base_currency: The base currency (e.g., 'BTC')
        quote_currency: The quote currency (e.g., 'EUR')
        max_exchanges: Maximum number of exchanges to check (default: 15)
        timeout: Timeout in seconds for each exchange request (default: 30)
        exchange_ids: Specific exchange ids to query instead of all exchanges.

    Returns:
        List of standardized market volume rows sorted by normalized volume.
    """
    # Normalize currency codes
    base = base_currency.upper()
    quote = quote_currency.upper()
    symbol = f"{base}/{quote}"

    # Get all available exchanges
    if exchange_ids is not None:
        exchanges = [
            exchange_id
            for exchange_id in exchange_ids
            if not exchange_id.startswith("_")
        ]
    else:
        ccxt = _import_ccxt()
        exchanges = [ex for ex in ccxt.exchanges if not ex.startswith("_")]

    # Limit the number of exchanges to avoid excessive API calls
    if max_exchanges and max_exchanges > 0:
        exchanges = exchanges[:max_exchanges]

    results = []

    def build_result(
        exchange_id: str,
        market_symbol: str,
        volume_data: dict[str, Any],
    ) -> dict[str, Any]:
        actual_quote = str(volume_data.get("quote") or "").upper() or None
        normalized_volume = volume_data.get("quoteVolume")
        normalized_currency = actual_quote
        is_normalized = actual_quote == quote

        return {
            "exchange": exchange_id,
            "symbol": market_symbol,
            "base": str(volume_data.get("base") or base),
            "quote": actual_quote or quote,
            "price": volume_data.get("price"),
            "baseVolume": volume_data.get("baseVolume"),
            "quoteVolume": volume_data.get("quoteVolume"),
            "normalizedVolume": normalized_volume,
            "normalizedCurrency": normalized_currency,
            "isNormalized": is_normalized,
            "timestamp": volume_data.get("timestamp"),
            "datetime": volume_data.get("datetime"),
        }

    def fetch_exchange_volume(exchange_id: str) -> dict[str, Any] | None:
        """Fetch volume for a specific exchange."""
        try:
            exchange = Exchange(exchange_id, timeout=timeout * 1000)

            market = exchange.get_market(symbol)
            matched_symbol = symbol
            if market is None:
                # Try alternative symbol formats
                if quote == "USD" and exchange.get_market(f"{base}/USDT"):
                    market = exchange.get_market(f"{base}/USDT")
                    matched_symbol = f"{base}/USDT"
                elif quote == "USDT" and exchange.get_market(f"{base}/USD"):
                    market = exchange.get_market(f"{base}/USD")
                    matched_symbol = f"{base}/USD"
                else:
                    return None

            if market:
                volume_data = market.get_volume()
                if volume_data and isinstance(
                    volume_data.get("baseVolume"), (int, float)
                ):
                    if float(volume_data["baseVolume"]) <= 0:
                        return None
                    return build_result(exchange_id, matched_symbol, volume_data)
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

    valid_results = [r for r in results if r is not None]
    valid_results.sort(key=_volume_sort_key, reverse=True)

    return valid_results
