#!/usr/bin/env python3
"""
Example showing how to use the MarketVolume class with a specific quote_currency.
This demonstrates the new functionality of filtering to only base_currency/quote_currency
and quote_currency/base_currency pairs.
"""

import logging

from pyccxt.market_volume import MarketVolume

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    # Example using quote_currency (e.g., only get BTC/EUR and EUR/BTC pairs)
    logger.info("Creating MarketVolume instance with EUR as quote_currency")
    market_volume_eur = MarketVolume(
        market="binance", min_refresh_time=60, base_currency="BTC", quote_currency="EUR"
    )

    # Refresh data
    logger.info("Fetching volume data for BTC/EUR and EUR/BTC pairs...")
    market_volume_eur.refresh()

    # Get the data for the pairs
    logger.info(f"Tickers fetched: {list(market_volume_eur._tickers.keys())}")

    # Get volumes
    volumes = market_volume_eur.get_volumes()
    logger.info("Volume data:")
    for v in volumes:
        logger.info(f"{v['symbol']}: BTC Volume = {v['volume']:.8f}")

    # For comparison, get markets without quote_currency filter
    logger.info("\nCreating MarketVolume instance without quote_currency filter")
    market_volume_all = MarketVolume(
        market="binance", min_refresh_time=60, base_currency="BTC"
    )

    # Refresh data
    logger.info("Fetching volume data for all markets...")
    market_volume_all.refresh()

    # Get top markets
    top_markets_all = market_volume_all.get_top_markets(limit=5)
    logger.info("Top 5 markets (all quote currencies) by volume:")
    for market in top_markets_all:
        logger.info(f"{market['symbol']}: BTC Volume = {market['volume']:.8f}")

    # Show how many markets were fetched in each case
    logger.info("\nStatistics:")
    logger.info(
        f"Number of markets with EUR quote currency filter: {len(market_volume_eur._tickers)}"
    )
    logger.info(f"Number of all markets: {len(market_volume_all._tickers)}")

    # Performance difference
    logger.info("\nThis demonstrates how the targeted filtering to just the pairs")
    logger.info("that are needed significantly reduces API calls and data processing.")


if __name__ == "__main__":
    main()
