import logging
from typing import Dict, List, Optional, Tuple, Any

import ccxt

log = logging.getLogger(__name__)


class Exchanges:
    """
    Class for retrieving and processing exchange information from ccxt.
    """

    @staticmethod
    def get_all_exchanges() -> List[str]:
        """
        Get a list of all available exchange IDs.

        Returns:
            List[str]: List of exchange IDs
        """
        return ccxt.exchanges

    @staticmethod
    def get_exchange_instance(exchange_id: str) -> ccxt.Exchange:
        """
        Create an instance of the specified exchange.

        Args:
            exchange_id: ID of the exchange to instantiate

        Returns:
            ccxt.Exchange: Exchange instance

        Raises:
            AttributeError: If exchange_id is not found
        """
        try:
            return getattr(ccxt, exchange_id)()
        except AttributeError:
            raise AttributeError(f"Exchange '{exchange_id}' not found")

    @staticmethod
    def get_exchange_features(exchange: ccxt.Exchange) -> Dict[str, Any]:
        """
        Get features supported by an exchange.

        Args:
            exchange: Exchange instance

        Returns:
            Dict[str, Any]: Dictionary of features
        """
        return exchange.has

    @staticmethod
    def filter_exchanges_by_features(
        exchanges: List[str], features: List[str]
    ) -> List[str]:
        """
        Filter exchanges based on supported features.

        Args:
            exchanges: List of exchange IDs to filter
            features: List of features that exchanges must support

        Returns:
            List[str]: Filtered list of exchange IDs
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
        exchanges: List[str],
        base_currency: Optional[str] = None,
        quote_currency: Optional[str] = None,
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        Filter exchanges based on supported markets.

        Args:
            exchanges: List of exchange IDs to filter
            base_currency: Base currency to filter by
            quote_currency: Quote currency to filter by

        Returns:
            Tuple[List[str], Dict[str, List[str]]]:
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
                for symbol, market in markets.items():
                    # Filter by base currency if specified
                    if base_currency and market.get("base") != base_currency.upper():
                        continue

                    # Filter by quote currency if specified
                    if quote_currency and market.get("quote") != quote_currency.upper():
                        continue

                    # If we got here, the market matches the criteria
                    matching_pairs.append(symbol)

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
        base_currency: Optional[str] = None,
        quote_currency: Optional[str] = None,
        active_only: bool = False,
        sort_by: str = "symbol",
    ) -> List[Dict[str, Any]]:
        """
        Get markets for a specific exchange with optional filtering.

        Args:
            exchange_id: ID of the exchange
            base_currency: Optional base currency filter
            quote_currency: Optional quote currency filter
            active_only: If True, return only active markets
            sort_by: Field to sort by (symbol, base, quote, volume, active)

        Returns:
            List[Dict[str, Any]]: List of market dictionaries
        """
        try:
            # Create an instance of the exchange
            exchange = Exchanges.get_exchange_instance(exchange_id)

            # Load markets
            markets = exchange.load_markets()

            # Filter markets
            filtered_markets = []
            for symbol, market in markets.items():
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

            # Sort markets
            if sort_by == "symbol":
                filtered_markets.sort(key=lambda x: x.get("symbol", ""))
            elif sort_by == "base":
                filtered_markets.sort(key=lambda x: x.get("base", ""))
            elif sort_by == "quote":
                filtered_markets.sort(key=lambda x: x.get("quote", ""))
            elif sort_by == "volume":
                # Sort by baseVolume or quoteVolume if available
                filtered_markets.sort(
                    key=lambda x: float(x.get("info", {}).get("baseVolume", 0) or 0),
                    reverse=True,
                )
            elif sort_by == "active":
                filtered_markets.sort(
                    key=lambda x: x.get("active", False), reverse=True
                )

            return filtered_markets

        except Exception as e:
            log.error(f"Error getting markets for {exchange_id}: {e}")
            raise
