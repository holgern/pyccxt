#!/usr/bin/env python3
"""
Example showing how to use the Exchange and Market classes with specific
quote currencies. This demonstrates how to filter markets by base/quote
currencies using the new API.
"""

import logging

from pyccxt.exchange import Exchange

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    # Example using specific quote currency (e.g., only get BTC/EUR pair)
    logger.info("Creating Exchange instance and getting BTC/EUR market")
    exchange = Exchange("binance", min_refresh_time=60)

    # Get specific market
    btc_eur_market = exchange.get_market("BTC/EUR")
    if btc_eur_market:
        logger.info(f"Found market: {btc_eur_market.symbol}")

        # Get volume data for this specific market
        volume_data = btc_eur_market.get_volume()
        logger.info(f"BTC/EUR Volume data: {volume_data}")
    else:
        logger.info("BTC/EUR market not found on Binance")

    # Get all markets with EUR as quote currency
    logger.info("\nGetting all EUR markets...")
    eur_markets = exchange.get_markets_by_quote("EUR")
    logger.info(f"Found {len(eur_markets)} markets with EUR as quote currency")

    # Display top EUR markets by volume
    if eur_markets:
        eur_volumes = []
        for market in eur_markets:
            volume_data = market.get_volume()
            if volume_data.get("baseVolume"):
                eur_volumes.append(volume_data)

        # Sort by base volume
        eur_volumes.sort(key=lambda x: x.get("baseVolume", 0), reverse=True)

        logger.info("Top 5 EUR markets by base volume:")
        for v in eur_volumes[:5]:
            logger.info(
                f"{v['symbol']}: Base Volume = {v['baseVolume']:.2f}, "
                f"Quote Volume = {v['quoteVolume']:.2f}"
            )

    # Get all markets with BTC as base currency
    logger.info("\nGetting all BTC markets...")
    btc_markets = exchange.get_markets_by_base("BTC")
    logger.info(f"Found {len(btc_markets)} markets with BTC as base currency")

    # Get volume data using exchange method
    logger.info("\nGetting market volumes filtered by BTC base currency...")
    btc_volumes = exchange.get_market_volumes(base_currency="BTC", limit=5)
    logger.info("Top 5 BTC markets by volume:")
    for v in btc_volumes:
        logger.info(
            f"{v['symbol']}: Base Volume = {v.get('baseVolume', 0):.2f}, "
            f"Normalized Volume = {v.get('normalizedVolume', 0):.2f}"
        )

    # For comparison, get all markets
    logger.info("\nGetting all markets for comparison...")
    all_markets = exchange.get_all_markets()
    logger.info(f"Total markets on exchange: {len(all_markets)}")

    # Show total volumes
    total_btc_volume = exchange.get_total_volume(base_currency="BTC")
    total_all_volume = exchange.get_total_volume()
    logger.info(f"\nTotal BTC volume: {total_btc_volume:.2f}")
    logger.info(f"Total volume (all markets): {total_all_volume:.2f}")

    # Performance difference
    logger.info("\nThis demonstrates how the targeted filtering to specific")
    logger.info("base/quote currencies reduces data processing and provides")
    logger.info("more focused analysis of trading volumes.")


if __name__ == "__main__":
    main()
