from __future__ import annotations

import importlib
import logging
from typing import Any

log = logging.getLogger(__name__)


def _import_ccxt() -> Any:
    return importlib.import_module("ccxt")


def _sort_markets(markets: list[dict[str, Any]], sort_by: str) -> list[dict[str, Any]]:
    if sort_by == "symbol":
        markets.sort(key=lambda x: x.get("symbol", ""))
    elif sort_by == "base":
        markets.sort(key=lambda x: x.get("base", ""))
    elif sort_by == "quote":
        markets.sort(key=lambda x: x.get("quote", ""))
    elif sort_by == "volume":
        markets.sort(
            key=lambda x: float(x.get("info", {}).get("baseVolume", 0) or 0),
            reverse=True,
        )
    elif sort_by == "active":
        markets.sort(key=lambda x: x.get("active", False), reverse=True)
    return markets


class Exchanges:
    """
    Class for retrieving and processing exchange information from ccxt.
    """

    def __repr__(self) -> str:
        """
        Return a string representation of the Exchanges class.

        Returns:
            str: String representation showing available exchange count
        """
        exchange_count = len(self.get_all_exchanges())
        return f"Exchanges(available_exchanges={exchange_count})"

    @staticmethod
    def get_all_exchanges() -> list[str]:
        """
        Get a list of all available exchange IDs.

        Returns:
            list[str]: List of exchange IDs
        """
        return _import_ccxt().exchanges

    @staticmethod
    def get_exchange_instance(exchange_id: str) -> Any:
        """
        Create an instance of the specified exchange.

        Args:
            exchange_id: ID of the exchange to instantiate

        Returns:
            Exchange instance

        Raises:
            AttributeError: If exchange_id is not found
        """
        try:
            ccxt = _import_ccxt()
            return getattr(ccxt, exchange_id)()
        except AttributeError as err:
            raise AttributeError(f"Exchange '{exchange_id}' not found") from err

    @staticmethod
    def get_exchange_features(exchange: Any) -> dict[str, Any]:
        """
        Get features supported by an exchange.

        Args:
            exchange: Exchange instance

        Returns:
            dict[str, Any]: Dictionary of features
        """
        return exchange.has

    @staticmethod
    def filter_exchanges_by_features(
        exchanges: list[str], features: list[str]
    ) -> list[str]:
        """
        Filter exchanges based on supported features.

        Args:
            exchanges: List of exchange IDs to filter
            features: List of features that exchanges must support

        Returns:
            list[str]: Filtered list of exchange IDs
        """
        filtered_exchanges = []

        for exchange_id in exchanges:
            try:
                # Create an instance of the exchange
                exchange = Exchanges.get_exchange_instance(exchange_id)

                # Check if the exchange has all specified features
                has_all_features = True
                for feature in features:
                    if not exchange.has.get(feature):
                        has_all_features = False
                        break

                if has_all_features:
                    filtered_exchanges.append(exchange_id)
            except Exception as e:
                log.debug(f"Error initializing {exchange_id}: {e}")
                continue

        return filtered_exchanges

    @staticmethod
    def filter_exchanges_by_market(
        exchanges: list[str],
        base_currency: str | None = None,
        quote_currency: str | None = None,
    ) -> tuple[list[str], dict[str, list[str]]]:
        """
        Filter exchanges based on supported markets.

        Args:
            exchanges: List of exchange IDs to filter
            base_currency: Base currency to filter by
            quote_currency: Quote currency to filter by

        Returns:
            tuple[list[str], dict[str, list[str]]]:
                - Filtered list of exchange IDs
                - Dictionary mapping exchange IDs to lists of matching market symbols
        """
        filtered_exchanges = []
        exchange_market_pairs = {}

        for exchange_id in exchanges:
            try:
                # Create an instance of the exchange
                exchange = Exchanges.get_exchange_instance(exchange_id)

                # Load markets for this exchange
                markets = exchange.load_markets()

                # Check if markets match the criteria
                matching_pairs = []
                for _symbol, market in markets.items():
                    # Filter by base currency if specified
                    if base_currency and market.get("base") != base_currency.upper():
                        continue

                    # Filter by quote currency if specified
                    if quote_currency and market.get("quote") != quote_currency.upper():
                        continue

                    # If we got here, the market matches the criteria
                    matching_pairs.append(_symbol)

                # If we found matching pairs, include this exchange
                if matching_pairs:
                    filtered_exchanges.append(exchange_id)
                    exchange_market_pairs[exchange_id] = matching_pairs

            except Exception as e:
                log.debug(f"Error loading markets for {exchange_id}: {e}")
                continue

        return filtered_exchanges, exchange_market_pairs

    @staticmethod
    def get_exchange_markets(
        exchange_id: str,
        base_currency: str | None = None,
        quote_currency: str | None = None,
        active_only: bool = False,
        sort_by: str = "symbol",
    ) -> list[dict[str, Any]]:
        """
        Get markets for a specific exchange with optional filtering.

        Args:
            exchange_id: ID of the exchange
            base_currency: Optional base currency filter
            quote_currency: Optional quote currency filter
            active_only: If True, return only active markets
            sort_by: Field to sort by (symbol, base, quote, volume, active)

        Returns:
            list[dict[str, Any]]: List of market dictionaries
        """
        try:
            # Create an instance of the exchange
            exchange = Exchanges.get_exchange_instance(exchange_id)

            # Load markets
            markets = exchange.load_markets()

            # Filter markets
            filtered_markets = []
            for _symbol, market in markets.items():
                # Skip inactive markets if active_only is True
                if active_only and not market.get("active", True):
                    continue

                # Filter by base currency if specified
                if base_currency and market.get("base") != base_currency.upper():
                    continue

                # Filter by quote currency if specified
                if quote_currency and market.get("quote") != quote_currency.upper():
                    continue

                filtered_markets.append(market)

            return _sort_markets(filtered_markets, sort_by)

        except Exception as e:
            log.error(f"Error getting markets for {exchange_id}: {e}")
            raise
