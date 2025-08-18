import logging
from typing import Optional, List

import ccxt
import typer
from rich.console import Console
from rich.table import Table

from .market_volume import MarketVolume
from .price_by_market import PriceByMarket
from pyccxt.exchanges import Exchanges

log = logging.getLogger(__name__)
app = typer.Typer()
console = Console()

state = {"verbose": 3}


@app.command()
def price(
    base: str = typer.Argument(..., help="Base Currency symbol (e.g., BTC)"),
    quote: str = typer.Argument(..., help="Quote Currency symbol (e.g., USD, EUR)"),
    market: str = typer.Option(None, "--market", "-m", help="Exchange to use"),
):
    p = PriceByMarket(
        market=market if market else state["market"],
        base_currency=base,
        quote_currency=quote,
        enable_ohlc=False,
    )
    p.refresh()
    price_data = p.price

    # Display more informative output
    console.print("[bold]Price[/bold]")
    console.print(f"Market: [green]{price_data['market']}[/green]")
    console.print(
        f"Time: [cyan]{price_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}[/cyan]"
    )
    console.print(
        f"Price ({base.upper()}/{quote.upper()}): [yellow]{price_data['price']:,.2f}[/yellow]"
    )


@app.command()
def volume(
    markets: str = typer.Option(
        "kraken", "--market", "-m", help="Exchange(s) to use (comma-separated list)"
    ),
    base_currency: str = typer.Option(
        "BTC", "--base", "-b", help="Base currency for normalization"
    ),
    quote_currency: Optional[str] = typer.Option(
        None, "--quote", "-q", help="Optional quote currency to filter by"
    ),
    limit: int = typer.Option(
        10, "--limit", "-l", help="Maximum number of markets to display per exchange"
    ),
    min_volume: float = typer.Option(
        0.0, "--min-volume", "-v", help="Minimum volume threshold in BTC"
    ),
    compare: bool = typer.Option(
        False, "--compare", "-c", help="Compare volumes across exchanges"
    ),
):
    """
    Display trading volume metrics across one or more exchanges.
    """
    # Handle string input (comma-separated list)
    if "," in markets:
        market_list = [m.strip() for m in markets.split(",")]
    else:
        market_list = [markets]

    # If no markets provided, use default
    if not market_list:
        market_list = [state["market"]]
    # Check if exchanges exist
    all_exchanges = Exchanges.get_all_exchanges()
    for market in market_list:
        if market not in all_exchanges:
            console.print(f"[bold red]Error: Exchange '{market}' not found.[/bold red]")
            console.print(f"Available exchanges: {', '.join(all_exchanges[:10])}...")
            return

    # Dictionary to store volume data for each exchange
    exchange_data = {}
    all_volumes = []

    # Process each exchange
    for market in market_list:
        try:
            console.print(
                f"[bold]Fetching volume data from [green]{market}[/green]...[/bold]"
            )

            # Initialize MarketVolume object
            mv = MarketVolume(
                market=market,
                base_currency=base_currency,
                quote_currency=quote_currency,
                min_refresh_time=60,  # 1 minute refresh time
            )

            # Initialize MarketVolume object
            mv = MarketVolume(
                market=market,
                base_currency=base_currency,
                quote_currency=quote_currency,
                min_refresh_time=60,  # 1 minute refresh time
            )

            # Refresh the data
            mv.refresh()

            # Get volumes with filtering
            volumes = mv.get_volumes(limit=limit, min_volume=min_volume)

            if not volumes:
                console.print(
                    f"[bold yellow]No volume data found on {market} with the specified parameters.[/bold yellow]"
                )
                continue

            # Store data for this exchange
            exchange_data[market] = {
                "volumes": volumes,
                "market_volume": mv,
                "total_volume": mv.get_total_volume(),
                "quote_volumes": mv.get_volume_by_quote_currency(),
                "base_volumes": mv.get_volume_by_base_currency(),
                "timestamp": mv.get_timestamp(),
            }

            # Add exchange name to volume data for comparison
            for v in volumes:
                v["exchange"] = market
                all_volumes.append(v)

            # Display individual exchange table if not comparing
            if not compare:
                display_exchange_volumes(market, exchange_data[market])

        except Exception as e:
            console.print(
                f"[bold red]Error fetching data from {market}: {str(e)}[/bold red]"
            )
            log.error(f"Error fetching volume data from {market}: {e}", exc_info=True)

    # If comparing exchanges, display combined table
    if compare and exchange_data:
        display_compared_volumes(exchange_data, all_volumes, base_currency, limit)


def display_exchange_volumes(exchange_name, data):
    """Display volume information for a single exchange."""
    volumes = data["volumes"]
    mv = data["market_volume"]
    total_volume = data["total_volume"]
    quote_volumes = data["quote_volumes"]
    base_volumes = data["base_volumes"]
    timestamp = data["timestamp"]

    # Create a table for top markets by volume
    table = Table(title=f"Top Markets by Volume on {exchange_name.capitalize()}")

    # Add columns
    table.add_column("Rank", style="cyan", justify="right")
    table.add_column("Symbol", style="green")
    table.add_column("BTC Volume", style="yellow", justify="right")
    table.add_column("Base Volume", justify="right")
    table.add_column("Quote Volume", justify="right")
    table.add_column("Price", justify="right")

    # Add rows
    for i, v in enumerate(volumes, 1):
        table.add_row(
            str(i),
            v["symbol"],
            f"{v['volume']:.4f}",
            f"{v['baseVolume']:.4f}",
            f"{v['quoteVolume']:.4f}",
            f"{v['price']:.6f}",
        )

    # Display the table
    console.print(table)

    # Display summary information
    console.print("\n[bold]Volume Summary[/bold]")
    console.print(f"Total Volume: [yellow]{total_volume:.2f} BTC[/yellow]")

    # Get top quote currencies by volume
    console.print("\n[bold]Top Quote Currencies by Volume[/bold]")
    for i, (quote, volume) in enumerate(list(quote_volumes.items())[:5], 1):
        pct = (volume / total_volume) * 100 if total_volume > 0 else 0
        console.print(f"{i}. {quote}: [yellow]{volume:.2f} BTC[/yellow] ({pct:.1f}%)")

    # Get top base currencies by volume
    console.print("\n[bold]Top Base Currencies by Volume[/bold]")
    for i, (base, volume) in enumerate(list(base_volumes.items())[:5], 1):
        pct = (volume / total_volume) * 100 if total_volume > 0 else 0
        console.print(f"{i}. {base}: [yellow]{volume:.2f} BTC[/yellow] ({pct:.1f}%)")

    # Show last update time
    if timestamp:
        console.print(
            f"\nLast updated: [cyan]{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}[/cyan]"
        )
    console.print("\n" + "-" * 80 + "\n")


def display_compared_volumes(exchange_data, all_volumes, base_currency, limit):
    """Display comparison of volumes across exchanges."""
    # Sort all volumes by BTC volume
    sorted_volumes = sorted(all_volumes, key=lambda x: x["volume"], reverse=True)

    # Limit the total number of entries if needed
    if limit > 0:
        sorted_volumes = sorted_volumes[:limit]

    # Create comparison table
    table = Table(title=f"Top Markets by {base_currency} Volume Across Exchanges")

    # Add columns
    table.add_column("Rank", style="cyan", justify="right")
    table.add_column("Exchange", style="blue")
    table.add_column("Symbol", style="green")
    table.add_column(f"{base_currency} Volume", style="yellow", justify="right")
    table.add_column("Base Volume", justify="right")
    table.add_column("Quote Volume", justify="right")
    table.add_column("Price", justify="right")

    # Add rows
    for i, v in enumerate(sorted_volumes, 1):
        table.add_row(
            str(i),
            v["exchange"],
            v["symbol"],
            f"{v['volume']:.4f}",
            f"{v['baseVolume']:.4f}",
            f"{v['quoteVolume']:.4f}",
            f"{v['price']:.6f}",
        )

    # Display the table
    console.print(table)

    # Create exchange volume summary
    console.print("\n[bold]Exchange Volume Summary[/bold]")
    total_all_exchanges = sum(data["total_volume"] for data in exchange_data.values())

    # Create exchange comparison table
    summary_table = Table(title=f"Volume by Exchange in {base_currency}")
    summary_table.add_column("Rank", style="cyan", justify="right")
    summary_table.add_column("Exchange", style="blue")
    summary_table.add_column(
        f"Total {base_currency} Volume", style="yellow", justify="right"
    )
    summary_table.add_column("% of All Exchanges", style="magenta", justify="right")

    # Sort exchanges by volume
    sorted_exchanges = sorted(
        [(name, data["total_volume"]) for name, data in exchange_data.items()],
        key=lambda x: x[1],
        reverse=True,
    )

    # Add rows to summary table
    for i, (exchange, volume) in enumerate(sorted_exchanges, 1):
        percentage = (
            (volume / total_all_exchanges) * 100 if total_all_exchanges > 0 else 0
        )
        summary_table.add_row(str(i), exchange, f"{volume:.2f}", f"{percentage:.1f}%")

    # Add total row
    summary_table.add_row(
        "", "TOTAL", f"{total_all_exchanges:.2f}", "100.0%", style="bold"
    )

    # Display the summary table
    console.print(summary_table)


@app.command()
def exchanges(
    show_features: bool = typer.Option(
        False, "--features", "-f", help="Show exchange features (e.g., has OHLC)"
    ),
    filter_by: List[str] = typer.Option(
        None, "--filter", "-F", help="Filter exchanges by feature (e.g., fetchOHLCV)"
    ),
    base_currency: str = typer.Option(
        None, "--base", "-b", help="Filter exchanges by base currency (e.g., BTC)"
    ),
    quote_currency: str = typer.Option(
        None,
        "--quote",
        "-q",
        help="Filter exchanges by quote currency (e.g., EUR, USD)",
    ),
    limit: int = typer.Option(
        0, "--limit", "-l", help="Limit number of exchanges shown (0 for all)"
    ),
):
    """
    List all available exchanges and their properties.
    """
    # Get all available exchanges
    all_exchanges = Exchanges.get_all_exchanges()

    # Filter by features if specified
    exchanges_list = all_exchanges
    if filter_by:
        exchanges_list = Exchanges.filter_exchanges_by_features(
            exchanges_list, filter_by
        )

    # Filter by market if base or quote currency is specified
    exchange_market_pairs = {}
    if base_currency or quote_currency:
        console.print(f"[bold]Filtering exchanges with market pairs...[/bold]")
        with console.status(
            "[bold green]Loading markets for exchanges...[/bold green]"
        ):
            exchanges_list, exchange_market_pairs = (
                Exchanges.filter_exchanges_by_market(
                    exchanges_list, base_currency, quote_currency
                )
            )

        # Show how many pairs were found for each exchange
        for exchange_id in exchanges_list:
            log.debug(
                f"{exchange_id}: {len(exchange_market_pairs[exchange_id])} matching pairs"
            )

    # Apply limit if specified
    if limit > 0:
        exchanges_list = exchanges_list[:limit]

    # Create table
    table = Table(title="Available CCXT Exchanges")
    table.add_column("Exchange ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Countries", style="yellow")

    # Add a column for matching pairs count if filtering by market
    if base_currency or quote_currency:
        table.add_column("Matching Pairs", style="magenta", justify="right")

    feature_columns = []
    if show_features:
        important_features = [
            "fetchOHLCV",
            "fetchTicker",
            "fetchOrderBook",
            "fetchBalance",
            "createOrder",
            "fetchTrades",
        ]
        for feature in important_features:
            table.add_column(feature, justify="center")
            feature_columns.append(feature)

    # Populate table
    for exchange_id in sorted(exchanges_list):
        try:
            # Create an instance of the exchange
            exchange = Exchanges.get_exchange_instance(exchange_id)

            # Get exchange properties
            name = exchange.name
            countries = (
                ", ".join(exchange.countries)
                if hasattr(exchange, "countries") and exchange.countries
                else "-"
            )

            # Create row with basic info
            row = [exchange_id, name, countries]

            # Add matching pairs count if filtering by market
            if base_currency or quote_currency:
                row.append(str(len(exchange_market_pairs[exchange_id])))

            # Add feature columns if requested
            if show_features:
                for feature in feature_columns:
                    value = exchange.has.get(feature, False)
                    if value is True:
                        row.append("✓")
                    elif value == "emulated":
                        row.append("E")
                    else:
                        row.append("✗")

            table.add_row(*row)

        except Exception as e:
            log.debug(f"Error processing {exchange_id}: {e}")
            continue

    console.print(table)
    console.print(f"\nTotal exchanges: {len(exchanges_list)}")

    # Print filter information
    filters = []
    if filter_by:
        filters.append(f"Features: {', '.join(filter_by)}")
    if base_currency:
        filters.append(f"Base currency: {base_currency.upper()}")
    if quote_currency:
        filters.append(f"Quote currency: {quote_currency.upper()}")

    if filters:
        console.print(f"Filters applied: {'; '.join(filters)}")

    # Show feature legend if features are shown
    if show_features:
        console.print("\n[bold]Legend:[/bold]")
        console.print("✓ - Feature is natively supported")
        console.print("E - Feature is emulated")
        console.print("✗ - Feature is not supported")


@app.command()
def markets(
    exchange: str = typer.Argument(None, help="Exchange ID (e.g., kraken, binance)"),
    base_currency: str = typer.Option(
        None, "--base", "-b", help="Filter by base currency (e.g., BTC, ETH)"
    ),
    quote_currency: str = typer.Option(
        None, "--quote", "-q", help="Filter by quote currency (e.g., USD, USDT)"
    ),
    active_only: bool = typer.Option(
        False, "--active-only", "-a", help="Show only active markets"
    ),
    show_details: bool = typer.Option(
        False, "--details", "-d", help="Show detailed market information"
    ),
    limit: int = typer.Option(
        0, "--limit", "-l", help="Limit number of markets shown (0 for all)"
    ),
    sort_by: str = typer.Option(
        "symbol",
        "--sort",
        "-s",
        help="Sort by field (symbol, base, quote, volume, active)",
    ),
):
    """
    List all available markets for a specific exchange.
    """
    # Use the exchange from argument or from state
    exchange_id = exchange or state["market"]

    try:
        console.print(f"[bold]Loading markets from {exchange_id}...[/bold]")

        try:
            # Get markets using the Exchanges class
            filtered_markets = Exchanges.get_exchange_markets(
                exchange_id=exchange_id,
                base_currency=base_currency,
                quote_currency=quote_currency,
                active_only=active_only,
                sort_by=sort_by,
            )

            # Get exchange instance for name and other properties
            exchange_instance = Exchanges.get_exchange_instance(exchange_id)

            # Apply limit if specified
            if limit > 0:
                filtered_markets = filtered_markets[:limit]

            # Create table
            table = Table(title=f"Markets on {exchange_instance.name}")
            table.add_column("Symbol", style="cyan")
            table.add_column("Base", style="green")
            table.add_column("Quote", style="yellow")
            table.add_column("Active", justify="center")

            if show_details:
                table.add_column("Spot", justify="center")
                table.add_column("Margin", justify="center")
                table.add_column("Future", justify="center")
                table.add_column("Precision", justify="right")

            # Populate table
            for market in filtered_markets:
                symbol = market.get("symbol", "")
                base = market.get("base", "")
                quote = market.get("quote", "")
                active = "✓" if market.get("active", False) else "✗"

                row = [symbol, base, quote, active]

                if show_details:
                    spot = "✓" if market.get("spot", False) else "✗"
                    margin = "✓" if market.get("margin", False) else "✗"
                    future = "✓" if market.get("future", False) else "✗"

                    # Get precision information
                    price_precision = market.get("precision", {}).get("price", "N/A")
                    amount_precision = market.get("precision", {}).get("amount", "N/A")
                    precision = f"P:{price_precision} A:{amount_precision}"

                    row.extend([spot, margin, future, precision])

                table.add_row(*row)

            # Print table
            console.print(table)
            console.print(f"\nTotal markets: {len(filtered_markets)}")

            # Print filter info
            filters_applied = []
            if base_currency:
                filters_applied.append(f"Base: {base_currency.upper()}")
            if quote_currency:
                filters_applied.append(f"Quote: {quote_currency.upper()}")
            if active_only:
                filters_applied.append("Active only")

            if filters_applied:
                console.print(f"Filters applied: {', '.join(filters_applied)}")

        except Exception as e:
            log.error(f"Error getting markets: {str(e)}", exc_info=True)
            raise

    except AttributeError:
        console.print(
            f"[bold red]Error: Exchange '{exchange_id}' not found.[/bold red]"
        )
        console.print(
            f"Available exchanges: {', '.join(Exchanges.get_all_exchanges()[:10])}..."
        )
    except Exception as e:
        console.print(f"[bold red]Error loading markets: {str(e)}[/bold red]")
        log.error(f"Error in markets command: {e}", exc_info=True)


@app.callback()
def main(
    verbose: int = typer.Option(3, "--verbose", "-v", help="Verbosity level (0-4)"),
    market: str = typer.Option(
        "kraken", "--market", "-m", help="Default exchange to use"
    ),
):
    """Python CLI for ccxt, enjoy."""
    # Logging
    state["verbose"] = verbose
    state["market"] = market
    log = logging.getLogger(__name__)
    verbosity = ["critical", "error", "warn", "info", "debug"][int(min(verbose, 4))]
    log.setLevel(getattr(logging, verbosity.upper()))
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, verbosity.upper()))
    ch.setFormatter(formatter)
    log.addHandler(ch)


if __name__ == "__main__":
    app()
