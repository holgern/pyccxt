"""
Example usage of the get_market_volumes_for_pair function.

This example shows how to:
1. Fetch volume data for a specific trading pair across multiple exchanges
2. Display the results in a formatted table
"""

import argparse
import os
import sys

# Add the parent directory to sys.path for imports when running as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pyccxt.exchange import get_market_volumes_for_pair


def display_pair_volumes(base_currency="BTC", quote_currency="EUR", max_exchanges=15):
    """
    Display volume data for a specific trading pair across multiple exchanges.

    Args:
        base_currency: The base currency (default: "BTC")
        quote_currency: The quote currency (default: "EUR")
        max_exchanges: Maximum number of exchanges to check (default: 15)
    """
    print(f"Fetching volumes for {base_currency}/{quote_currency} across exchanges...")
    print("This may take a moment as we query multiple exchanges...\n")

    # Get volume data
    results = get_market_volumes_for_pair(
        base_currency=base_currency,
        quote_currency=quote_currency,
        max_exchanges=max_exchanges,
    )

    # Check if we got any results
    if not results:
        print(f"No data found for {base_currency}/{quote_currency} on any exchange.")
        return
    # Display header
    print(
        f"Volume data for {base_currency}/{quote_currency} across "
        f"{len(results)} exchanges:"
    )
    print("=" * 80)
    print(
        f"{'Exchange':<15} {'Symbol':<12} {'Base Vol':<15} "
        f"{'Quote Vol':<20} {'Price':<15}"
    )
    print("-" * 80)

    # Calculate total volume
    total_base_volume = sum(result.get("baseVolume", 0) for result in results)
    total_quote_volume = sum(result.get("quoteVolume", 0) for result in results)

    # Display results
    for result in results:
        # Get values with defaults for None
        base_volume = result.get("baseVolume", 0)
        quote_volume = result.get("quoteVolume", 0)
        last_price = result.get("last", 0)

        # Format volumes with appropriate precision
        base_vol = f"{base_volume:,.2f}" if base_volume >= 1 else f"{base_volume:.8f}"
        quote_vol = (
            f"{quote_volume:,.2f}" if quote_volume >= 1 else f"{quote_volume:.8f}"
        )
        price = f"{last_price:,.2f}" if last_price >= 1 else f"{last_price:.8f}"

        print(
            f"{result['exchange']:<15} {result['symbol']:<12} "
            f"{base_vol:<15} {quote_vol:<20} {price:<15}"
        )

    # Display totals
    print("-" * 80)
    print(
        f"{'TOTAL':<15} {'(' + str(len(results)) + ' exchanges)':<12} "
        f"{total_base_volume:,.2f} {total_quote_volume:,.2f}"
    )

    # Display market share
    print("\nMarket Share by Exchange (based on quote volume):")
    print("-" * 40)
    for result in results:
        quote_volume = result.get("quoteVolume", 0)
        market_share = (
            (quote_volume / total_quote_volume) * 100 if total_quote_volume > 0 else 0
        )
        print(f"{result['exchange']:<15}: {market_share:,.2f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Display volume data for a trading pair across exchanges"
    )
    parser.add_argument(
        "--base", "-b", type=str, default="BTC", help="Base currency (default: BTC)"
    )
    parser.add_argument(
        "--quote", "-q", type=str, default="EUR", help="Quote currency (default: EUR)"
    )
    parser.add_argument(
        "--exchanges",
        "-e",
        type=int,
        default=15,
        help="Maximum number of exchanges to check (default: 15)",
    )
    args = parser.parse_args()

    display_pair_volumes(args.base, args.quote, args.exchanges)
