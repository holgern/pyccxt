"""
Example usage of the Exchange class to fetch and display market volumes.

This example shows how to:
1. Initialize the Exchange class
2. Fetch market volumes from multiple exchanges
3. Display the top markets by volume
4. Show the total volume and breakdown by currency
"""

import argparse
import os
import sys

import ccxt

# Add the parent directory to sys.path for imports when running as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pyccxt.exchange import Exchange


def display_volumes_for_exchange(market_name="binance", limit=10, min_volume=0):
    """
    Display market volumes for a specified exchange.

    Args:
        market_name: The exchange to use (default: "binance")
        limit: Maximum number of markets to display (default: 10)
        min_volume: Minimum base volume for filtering markets (default: 0)
    """
    # Initialize Exchange
    print(f"Fetching market volumes from {market_name}...")
    exchange = Exchange(market_name)

    # Get volumes
    volumes = exchange.get_market_volumes(min_volume=min_volume, limit=limit)

    if not volumes:
        print(f"No volume data available for {market_name}")
        return None

    # Display header
    print(f"\nTop {len(volumes)} markets by volume on {market_name.capitalize()}:")
    print("=" * 80)
    print(
        f"{'Symbol':<12} {'Base Vol':<15} {'Quote Vol':<20} "
        f"{'Norm Vol':<15} {'Price':<15}"
    )
    print("-" * 80)

    # Display markets
    for v in volumes:
        # Format volumes with appropriate precision
        base_vol = (
            f"{v['baseVolume']:,.2f}"
            if v["baseVolume"] and v["baseVolume"] >= 1
            else f"{v['baseVolume']:.8f}"
            if v["baseVolume"]
            else "0"
        )
        quote_vol = (
            f"{v['quoteVolume']:,.2f}"
            if v["quoteVolume"] and v["quoteVolume"] >= 1
            else f"{v['quoteVolume']:.8f}"
            if v["quoteVolume"]
            else "0"
        )
        norm_vol = (
            f"{v.get('normalizedVolume', 0):,.2f}"
            if v.get("normalizedVolume", 0) >= 1
            else f"{v.get('normalizedVolume', 0):.8f}"
        )
        price = (
            f"{v['price']:,.2f}"
            if v["price"] and v["price"] >= 1
            else f"{v['price']:.8f}"
            if v["price"]
            else "N/A"
        )

        print(
            f"{v['symbol']:<12} {base_vol:<15} {quote_vol:<20} "
            f"{norm_vol:<15} {price:<15}"
        )

    # Display total volume
    total_volume = exchange.get_total_volume()
    print("\nTotal Volume Statistics:")
    print(f"Total Normalized Volume: {total_volume:,.2f}")

    # Display volume by quote currency
    quote_volumes = exchange.get_volume_by_quote_currency()
    print("\nVolume by Quote Currency:")
    for quote, volume in list(quote_volumes.items())[:5]:  # Show top 5
        print(
            f"{quote:<8}: {volume:,.2f} ({volume / total_volume * 100:.2f}%)"
            if total_volume > 0
            else f"{quote:<8}: {volume:,.2f}"
        )

    # Display exchange info
    exchange_info = exchange.get_exchange_info()
    print(f"\nLast updated: {exchange_info.get('last_update', 'N/A')}")

    return {"exchange": market_name, "total_volume": total_volume, "volumes": volumes}


def display_volumes_multi_exchange(
    exchanges=None, limit=11, min_volume=0, top_exchanges=11
):
    """
    Display market volumes across multiple exchanges.

    Args:
        exchanges: List of exchanges to use (default: None, which uses top 5 exchanges)
        limit: Maximum number of markets to display per exchange (default: 10)
        min_volume: Minimum BTC volume for filtering markets (default: 0)
        top_exchanges: Number of top exchanges to use if no exchanges are
                       specified (default: 5)
    """
    if exchanges is None:
        # Get all available exchanges
        all_exchanges = [ex for ex in ccxt.exchanges if not ex.startswith("_")]
        print(f"No exchanges specified. Using top {top_exchanges} popular exchanges.")
        # Use some popular exchanges as default
        popular_exchanges = [
            "binance",
            "coinbase",
            "bitmart",
            "kraken",
            "kucoin",
            "huobi",
            "bybit",
            "okx",
            "bitfinex",
            "bitstamp",
            "gemini",
        ]
        exchanges = [ex for ex in popular_exchanges if ex in all_exchanges][
            :top_exchanges
        ]

    print(f"Fetching market volumes from exchanges: {', '.join(exchanges)}")
    print("This may take some time depending on the number of exchanges...")

    exchange_results = []

    # Process each exchange
    for exchange_name in exchanges:
        result = display_volumes_for_exchange(exchange_name, limit, min_volume)
        if result:
            exchange_results.append(result)
        print("\n" + "-" * 40 + "\n")

    # Display summary comparison across exchanges
    if exchange_results:
        print("\n" + "=" * 40)
        print("SUMMARY COMPARISON ACROSS EXCHANGES")
        print("=" * 40)

        # Sort exchanges by total volume
        exchange_results.sort(key=lambda x: x["total_volume"], reverse=True)

        print(f"{'Exchange':<15} {'Total BTC Volume':>20}")
        print("-" * 40)
        for result in exchange_results:
            print(
                f"{result['exchange'].capitalize():<15} "
                f"{result['total_volume']:>20,.2f}"
            )

    print("\nCompleted fetching data from all specified exchanges.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Display market volumes by exchange")
    parser.add_argument(
        "--market",
        "-m",
        type=str,
        default=None,
        help="Exchange to fetch data from (default: None, which uses "
        "multiple exchanges)",
    )
    parser.add_argument(
        "--exchanges",
        "-e",
        type=str,
        nargs="+",
        help="List of exchanges to fetch data from (e.g., -e binance kraken coinbase)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Number of markets to display per exchange (default: 10)",
    )
    parser.add_argument(
        "--min-volume",
        "-v",
        type=float,
        default=0,
        help="Minimum volume to include (default: 0)",
    )
    parser.add_argument(
        "--top-exchanges",
        "-t",
        type=int,
        default=5,
        help="Number of top exchanges to use if no exchanges are "
        "specified (default: 5)",
    )
    parser.add_argument(
        "--list-exchanges",
        action="store_true",
        help="List all available exchanges and exit",
    )
    args = parser.parse_args()

    if args.list_exchanges:
        print("Available exchanges in CCXT:")
        exchanges = [ex for ex in ccxt.exchanges if not ex.startswith("_")]
        for i, exchange in enumerate(sorted(exchanges)):
            print(f"{exchange:<15}", end="\t")
            if (i + 1) % 5 == 0:
                print()
        print("\nTotal exchanges:", len(exchanges))
        sys.exit(0)

    if args.market:
        # Single exchange mode
        display_volumes_for_exchange(args.market, args.limit, args.min_volume)
    else:
        # Multi-exchange mode
        display_volumes_multi_exchange(
            args.exchanges, args.limit, args.min_volume, args.top_exchanges
        )
