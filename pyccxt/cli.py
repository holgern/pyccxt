from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

import typer
from rich.console import Console
from rich.table import Table

from .asciichart import AsciiChart
from .exceptions import PyCCXTError
from .exchange import Exchange
from .exchanges import Exchanges

log = logging.getLogger(__name__)
app = typer.Typer()
console = Console()


class CLIState(TypedDict):
    verbose: int
    market: str


state: CLIState = {"verbose": 3, "market": "kraken"}


def _render_library_error(prefix: str, error: PyCCXTError) -> None:
    """Render a user-friendly library error without a traceback."""
    console.print(f"[bold red]{prefix}: {error}[/bold red]")
    log.error("%s: %s", prefix, error)


def _format_optional_number(value: Optional[float], precision: int = 4) -> str:  # noqa: UP045
    """Format optional numeric values for terminal output."""
    if value is None:
        return "N/A"
    return f"{value:.{precision}f}"


def _cli_volume_sort_key(row: dict[str, object]) -> tuple[int, float]:
    """Sort normalized rows first, unnormalized rows last."""
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


def _format_timestamp(value: object) -> str:
    """Format timestamps for terminal output."""
    if value is None:
        return "N/A"

    if isinstance(value, datetime):
        timestamp = value
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if isinstance(value, (int, float)):
        try:
            timestamp = datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return str(value)
        return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

    return str(value)


def _format_numeric_value(value: object, precision: int = 4) -> str:
    """Format numeric values consistently for CLI tables."""
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{float(value):,.{precision}f}".rstrip("0").rstrip(".")
    return str(value)


def _resolve_exchange_name(market: Optional[str]) -> str:  # noqa: UP045
    """Resolve the exchange name from explicit option or CLI state."""
    return market if market else state["market"]


def _render_missing_pair(exchange_name: str, symbol: str) -> None:
    """Render a helpful missing-market message."""
    base, quote = symbol.split("/", maxsplit=1)
    console.print(
        f"[bold red]Error: Trading pair {symbol} not found on "
        f"{exchange_name}[/bold red]"
    )
    console.print("Try using the 'markets' command to see available pairs:")
    console.print(
        "  pyccxt markets "
        f"{exchange_name} --base {base.upper()} --quote {quote.upper()}"
    )


def _get_market_or_render_error(exchange_obj: Exchange, symbol: str):
    """Get a market or render a user-facing error."""
    market_obj = exchange_obj.get_market(symbol)
    if market_obj is None:
        _render_missing_pair(exchange_obj.name, symbol)
    return market_obj


def _exchange_supports_ohlcv(  # noqa: UP045
    exchange_obj: Exchange,
) -> Optional[bool]:  # noqa: UP045
    """Return OHLCV support if the exchange exposes capability metadata."""
    ccxt_exchange = getattr(exchange_obj, "ccxt_exchange", None)
    has = getattr(ccxt_exchange, "has", None)
    if isinstance(has, dict):
        fetch_ohlcv = has.get("fetchOHLCV")
        if isinstance(fetch_ohlcv, bool):
            return fetch_ohlcv
    return None


def _render_ohlcv_fetch_error(exchange_name: str, symbol: str, timeframe: str) -> None:
    """Render a user-facing OHLCV fetch error."""
    console.print(
        f"[bold red]Error: Could not fetch OHLCV data for {symbol} on "
        f"{exchange_name} ({timeframe})[/bold red]"
    )
    console.print(
        f"Requested exchange: [cyan]{exchange_name}[/cyan] | "
        f"Symbol: [cyan]{symbol}[/cyan] | Timeframe: [cyan]{timeframe}[/cyan]"
    )


def _build_price_rows_table(
    exchange_name: str,
    symbol: str,
    timeframe: str,
    price_type: str,
    rows: list[dict[str, Any]],
) -> Table:
    """Build the price-series table used by the chart command."""
    table = Table(title=f"Price Data for {symbol} on {exchange_name} ({timeframe})")
    table.add_column("#", justify="right")
    table.add_column("Timestamp")
    table.add_column("Price Type")
    table.add_column("Price", justify="right")
    table.add_column("Volume", justify="right")

    for index, row in enumerate(rows, start=1):
        table.add_row(
            str(index),
            _format_timestamp(row.get("timestamp")),
            str(row.get("price_type") or price_type),
            _format_numeric_value(row.get("price"), precision=6),
            _format_numeric_value(row.get("volume"), precision=4),
        )

    return table


def _build_ohlcv_table(
    exchange_name: str,
    symbol: str,
    timeframe: str,
    rows: list[dict[str, Any]],
) -> Table:
    """Build the OHLCV table used by the ohlcv command."""
    table = Table(title=f"OHLCV Data for {symbol} on {exchange_name} ({timeframe})")
    table.add_column("#", justify="right")
    table.add_column("Timestamp")
    table.add_column("Open", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Low", justify="right")
    table.add_column("Close", justify="right")
    table.add_column("Volume", justify="right")

    for index, row in enumerate(rows, start=1):
        timestamp = row.get("datetime") or row.get("timestamp")
        table.add_row(
            str(index),
            _format_timestamp(timestamp),
            _format_numeric_value(row.get("open"), precision=6),
            _format_numeric_value(row.get("high"), precision=6),
            _format_numeric_value(row.get("low"), precision=6),
            _format_numeric_value(row.get("close"), precision=6),
            _format_numeric_value(row.get("volume"), precision=4),
        )

    return table


def _extract_prices(rows: list[dict[str, Any]]) -> list[float]:
    """Extract numeric price values from normalized rows."""
    prices: list[float] = []
    for row in rows:
        price = row.get("price")
        if not isinstance(price, (int, float)):
            raise ValueError("Price rows must contain numeric 'price' values.")
        prices.append(float(price))
    return prices


def display_price_chart(
    exchange_name: str,
    symbol: str,
    timeframe: str,
    price_type: str,
    rows: list[dict[str, Any]],
    height: int,
    inter_points_margin: int,
    show_table: bool,
) -> None:
    """Render a single-series ASCII price chart and optional data table."""
    if not rows:
        console.print(
            f"[bold yellow]No OHLCV price data available for {symbol} on "
            f"{exchange_name} ({timeframe}).[/bold yellow]"
        )
        return

    chart_title = f"{exchange_name.upper()} {symbol} {timeframe} {price_type}"
    chart_text = AsciiChart(
        _extract_prices(rows),
        title=chart_title,
        x_axis_description="Candles",
        y_axis_description=price_type.capitalize(),
    ).render(height=height, inter_points_margin=inter_points_margin)

    console.print(f"[bold]{chart_title}[/bold]")
    console.print(chart_text)

    if show_table:
        console.print(
            _build_price_rows_table(exchange_name, symbol, timeframe, price_type, rows)
        )


def display_ohlcv_chart(
    exchange_name: str,
    symbol: str,
    timeframe: str,
    plot_price: str,
    ohlc_rows: list[dict[str, Any]],
    price_rows: list[dict[str, Any]],
    height: int,
    inter_points_margin: int,
    show_table: bool,
) -> None:
    """Render an ASCII OHLCV-derived chart and optional candle table."""
    if not price_rows:
        console.print(
            f"[bold yellow]No OHLCV data available for {symbol} on "
            f"{exchange_name} ({timeframe}).[/bold yellow]"
        )
        if show_table and ohlc_rows:
            console.print(
                _build_ohlcv_table(exchange_name, symbol, timeframe, ohlc_rows)
            )
        return

    chart_title = f"{exchange_name.upper()} {symbol} {timeframe} {plot_price}"
    chart_text = AsciiChart(
        _extract_prices(price_rows),
        title=chart_title,
        x_axis_description="Candles",
        y_axis_description=plot_price.capitalize(),
    ).render(height=height, inter_points_margin=inter_points_margin)

    console.print(f"[bold]{chart_title}[/bold]")
    console.print(chart_text)

    if show_table:
        console.print(_build_ohlcv_table(exchange_name, symbol, timeframe, ohlc_rows))


@app.command()
def price(
    base: str = typer.Argument(..., help="Base Currency symbol (e.g., BTC)"),
    quote: str = typer.Argument(..., help="Quote Currency symbol (e.g., USD, EUR)"),
    market: str = typer.Option(None, "--market", "-m", help="Exchange to use"),
):
    """Get the current price for a trading pair on an exchange."""
    try:
        # Use the Exchange class to get market data
        exchange_name = _resolve_exchange_name(market)
        exchange_obj = Exchange(exchange_name=exchange_name)

        # Get the market for the specific trading pair
        trading_pair = f"{base.upper()}/{quote.upper()}"
        market_obj = _get_market_or_render_error(exchange_obj, trading_pair)

        if market_obj is None:
            return

        # Refresh to get latest ticker data
        success = market_obj.refresh()
        if not success:
            console.print(
                f"[bold red]Error: Could not refresh market data for {trading_pair} "
                f"on {exchange_name}[/bold red]"
            )
            return

        ticker = market_obj.get_ticker()

        if ticker is None:
            console.print(
                f"[bold red]Error: Could not fetch price for {trading_pair} "
                f"on {exchange_name}[/bold red]"
            )
            return

        # Convert timestamp to datetime for display
        timestamp_str = "N/A"
        if ticker.timestamp:
            from datetime import datetime, timezone

            dt = datetime.fromtimestamp(ticker.timestamp / 1000, tz=timezone.utc)
            timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        elif ticker.datetime:
            timestamp_str = ticker.datetime

        # Format price with appropriate precision
        price_str = f"{ticker.last:,.8f}".rstrip("0").rstrip(".")

        # Display more informative output
        console.print("\n[bold]Price Information[/bold]")
        console.print(f"Exchange: [green]{exchange_name.upper()}[/green]")
        console.print(f"Symbol: [cyan]{trading_pair}[/cyan]")
        console.print(f"Last Price: [yellow]{price_str} {quote.upper()}[/yellow]")

        # Show additional ticker information if available
        if ticker.bid and ticker.ask:
            bid_str = f"{ticker.bid:,.8f}".rstrip("0").rstrip(".")
            ask_str = f"{ticker.ask:,.8f}".rstrip("0").rstrip(".")
            spread = ticker.ask - ticker.bid
            spread_pct = (spread / ticker.ask * 100) if ticker.ask > 0 else 0
            console.print(
                f"Bid: [blue]{bid_str}[/blue] | Ask: [blue]{ask_str}[/blue] | "
                f"Spread: {spread_pct:.2f}%"
            )

        if ticker.change and ticker.percentage:
            change_color = "green" if ticker.change >= 0 else "red"
            change_symbol = "+" if ticker.change >= 0 else ""
            console.print(
                f"24h Change: [{change_color}]{change_symbol}{ticker.change:,.8f} "
                f"({ticker.percentage:+.2f}%)[/{change_color}]"
            )

        if ticker.high and ticker.low:
            high_str = f"{ticker.high:,.8f}".rstrip("0").rstrip(".")
            low_str = f"{ticker.low:,.8f}".rstrip("0").rstrip(".")
            console.print(
                f"24h High: [green]{high_str}[/green] | 24h Low: [red]{low_str}[/red]"
            )

        if ticker.baseVolume:
            volume_str = f"{ticker.baseVolume:,.4f}".rstrip("0").rstrip(".")
            console.print(f"24h Volume: [magenta]{volume_str} {base.upper()}[/magenta]")

        console.print(f"Time: [dim]{timestamp_str}[/dim]\n")

    except PyCCXTError as error:
        _render_library_error("Error fetching price", error)
    except Exception as e:
        console.print(f"[bold red]Error fetching price: {str(e)}[/bold red]")
        log.error(f"Error in price command: {e}", exc_info=True)


@app.command()
def chart(
    base: str = typer.Argument(..., help="Base currency symbol"),
    quote: str = typer.Argument(..., help="Quote currency symbol"),
    market: str = typer.Option(None, "--market", "-m", help="Exchange to use"),
    timeframe: str = typer.Option("1h", "--timeframe", "-t", help="OHLCV timeframe"),
    limit: int = typer.Option(60, "--limit", "-l", help="Number of candles to fetch"),
    since: Optional[int] = typer.Option(  # noqa: UP045
        None, "--since", help="UTC timestamp in ms"
    ),
    price_type: str = typer.Option(
        "close",
        "--price-type",
        help="Series to plot: open, high, low, close, typical, median",
    ),
    height: int = typer.Option(20, "--height", help="ASCII chart height"),
    inter_points_margin: int = typer.Option(
        2,
        "--inter-points-margin",
        help="Horizontal spacing between points",
    ),
    table: bool = typer.Option(False, "--table", help="Show price data table"),
):
    """Render an ASCII chart from OHLCV-derived price data."""
    try:
        exchange_name = _resolve_exchange_name(market)
        exchange_obj = Exchange(exchange_name=exchange_name)
        symbol = f"{base.upper()}/{quote.upper()}"
        market_obj = _get_market_or_render_error(exchange_obj, symbol)
        if market_obj is None:
            return

        supports_ohlcv = _exchange_supports_ohlcv(exchange_obj)
        if supports_ohlcv is False:
            console.print(
                f"[bold red]Error: Exchange {exchange_name} does not support OHLCV "
                f"for {symbol} ({timeframe})[/bold red]"
            )
            return

        success = market_obj.fetch_ohlc(timeframe=timeframe, since=since, limit=limit)
        if not success:
            _render_ohlcv_fetch_error(exchange_name, symbol, timeframe)
            return

        price_rows = market_obj.get_price_rows(price_type=price_type)
        display_price_chart(
            exchange_name=exchange_name,
            symbol=symbol,
            timeframe=timeframe,
            price_type=price_type,
            rows=price_rows,
            height=height,
            inter_points_margin=inter_points_margin,
            show_table=table,
        )
    except RuntimeError as error:
        console.print(f"[bold red]Error rendering chart: {error}[/bold red]")
        log.error("Error rendering chart: %s", error)
    except PyCCXTError as error:
        _render_library_error("Error fetching chart data", error)
    except Exception as e:
        console.print(f"[bold red]Error fetching chart data: {str(e)}[/bold red]")
        log.error("Error in chart command: %s", e, exc_info=True)


@app.command()
def ohlcv(
    base: str = typer.Argument(..., help="Base currency symbol"),
    quote: str = typer.Argument(..., help="Quote currency symbol"),
    market: str = typer.Option(None, "--market", "-m", help="Exchange to use"),
    timeframe: str = typer.Option("1h", "--timeframe", "-t", help="OHLCV timeframe"),
    limit: int = typer.Option(60, "--limit", "-l", help="Number of candles to fetch"),
    since: Optional[int] = typer.Option(  # noqa: UP045
        None, "--since", help="UTC timestamp in ms"
    ),
    plot_price: str = typer.Option(
        "close",
        "--plot-price",
        help="OHLC field to plot: open, high, low, close, typical, median",
    ),
    height: int = typer.Option(20, "--height", help="ASCII chart height"),
    inter_points_margin: int = typer.Option(
        2,
        "--inter-points-margin",
        help="Horizontal spacing between points",
    ),
    table: bool = typer.Option(False, "--table", help="Show OHLCV table"),
):
    """Fetch OHLCV candles, render an ASCII chart, and optionally print a table."""
    try:
        exchange_name = _resolve_exchange_name(market)
        exchange_obj = Exchange(exchange_name=exchange_name)
        symbol = f"{base.upper()}/{quote.upper()}"
        market_obj = _get_market_or_render_error(exchange_obj, symbol)
        if market_obj is None:
            return

        supports_ohlcv = _exchange_supports_ohlcv(exchange_obj)
        if supports_ohlcv is False:
            console.print(
                f"[bold red]Error: Exchange {exchange_name} does not support OHLCV "
                f"for {symbol} ({timeframe})[/bold red]"
            )
            return

        success = market_obj.fetch_ohlc(timeframe=timeframe, since=since, limit=limit)
        if not success:
            _render_ohlcv_fetch_error(exchange_name, symbol, timeframe)
            return

        ohlc_rows = market_obj.get_ohlcv_rows()
        price_rows = market_obj.get_price_rows(price_type=plot_price)
        display_ohlcv_chart(
            exchange_name=exchange_name,
            symbol=symbol,
            timeframe=timeframe,
            plot_price=plot_price,
            ohlc_rows=ohlc_rows,
            price_rows=price_rows,
            height=height,
            inter_points_margin=inter_points_margin,
            show_table=table,
        )
    except RuntimeError as error:
        console.print(f"[bold red]Error rendering OHLCV chart: {error}[/bold red]")
        log.error("Error rendering OHLCV chart: %s", error)
    except PyCCXTError as error:
        _render_library_error("Error fetching OHLCV data", error)
    except Exception as e:
        console.print(f"[bold red]Error fetching OHLCV data: {str(e)}[/bold red]")
        log.error("Error in ohlcv command: %s", e, exc_info=True)


@app.command()
def volume(
    markets: str = typer.Option(
        "kraken", "--market", "-m", help="Exchange(s) to use (comma-separated list)"
    ),
    base_currency: Optional[str] = typer.Option(  # noqa: UP045
        None, "--base", "-b", help="Filter by market base currency"
    ),
    quote_currency: Optional[str] = typer.Option(  # noqa: UP045
        None, "--quote", "-q", help="Filter by market quote currency"
    ),
    normalize_to: str = typer.Option(
        "USD",
        "--normalize-to",
        "-n",
        help="Target currency for normalized volume display",
    ),
    limit: int = typer.Option(
        10, "--limit", "-l", help="Maximum number of markets to display per exchange"
    ),
    min_volume: float = typer.Option(
        0.0, "--min-volume", help="Minimum base-volume threshold"
    ),
    compare: bool = typer.Option(
        False, "--compare", "-c", help="Compare volumes across exchanges"
    ),
):
    """
    Display trading volume metrics across one or more exchanges.
    """
    try:
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
                console.print(
                    f"[bold red]Error: Exchange '{market}' not found.[/bold red]"
                )
                console.print(
                    f"Available exchanges: {', '.join(all_exchanges[:10])}..."
                )
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

                # Initialize Exchange object for volume operations
                exchange_obj = Exchange(
                    exchange_name=market,
                    min_refresh_time=60,  # 1 minute refresh time
                )

                # Refresh the data
                exchange_obj.refresh_all()

                # Get volumes with filtering - use the new API
                volumes = exchange_obj.get_market_volumes(
                    filter_base=base_currency,
                    filter_quote=quote_currency,
                    normalize_to=normalize_to,
                    min_volume=min_volume,
                    limit=limit,
                    include_unconverted=True,
                )

                if not volumes:
                    console.print(
                        f"[bold yellow]No volume data found on {market} "
                        f"with the specified parameters.[/bold yellow]"
                    )
                    continue

                # Store data for this exchange
                exchange_data[market] = {
                    "volumes": volumes,
                    "exchange_obj": exchange_obj,
                    "total_volume": exchange_obj.get_total_volume(
                        filter_base=base_currency,
                        filter_quote=quote_currency,
                        normalize_to=normalize_to,
                        min_volume=min_volume,
                        include_unconverted=False,
                    ),
                    "quote_volumes": exchange_obj.get_volume_by_quote_currency(
                        filter_base=base_currency,
                        filter_quote=quote_currency,
                        min_volume=min_volume,
                    ),
                    "base_volumes": exchange_obj.get_volume_by_base_currency(
                        filter_base=base_currency,
                        filter_quote=quote_currency,
                        min_volume=min_volume,
                    ),
                    "normalize_to": normalize_to.upper(),
                    "timestamp": None,  # Exchange class doesn't track timestamp
                }

                # Add exchange name to volume data for comparison
                for v in volumes:
                    all_volumes.append({**v, "exchange": market})

                # Display individual exchange table if not comparing
                if not compare:
                    display_exchange_volumes(market, exchange_data[market])

            except PyCCXTError as error:
                _render_library_error(f"Error fetching data from {market}", error)
            except Exception as e:
                console.print(
                    f"[bold red]Error fetching data from {market}: {str(e)}[/bold red]"
                )
                log.error(
                    f"Error fetching volume data from {market}: {e}", exc_info=True
                )

        # If comparing exchanges, display combined table
        if compare and exchange_data:
            display_compared_volumes(exchange_data, all_volumes, normalize_to, limit)
    except PyCCXTError as error:
        _render_library_error("Error fetching volume data", error)


def display_exchange_volumes(exchange_name, data):
    """Display volume information for a single exchange."""
    volumes = data["volumes"]
    total_volume = data["total_volume"]
    quote_volumes = data["quote_volumes"]
    base_volumes = data["base_volumes"]
    normalize_to = data["normalize_to"]
    timestamp = data["timestamp"]

    # Create a table for top markets by volume
    table = Table(title=f"Top Markets by Volume on {exchange_name.capitalize()}")

    # Add columns
    table.add_column("Rank", style="cyan", justify="right")
    table.add_column("Symbol", style="green")
    table.add_column(
        f"Normalized Volume ({normalize_to})", style="yellow", justify="right"
    )
    table.add_column("Base Volume", justify="right")
    table.add_column("Quote Volume", justify="right")
    table.add_column("Price", justify="right")

    # Add rows
    for i, v in enumerate(volumes, 1):
        table.add_row(
            str(i),
            v["symbol"],
            _format_optional_number(v.get("normalizedVolume")),
            _format_optional_number(v.get("baseVolume")),
            _format_optional_number(v.get("quoteVolume")),
            _format_optional_number(v.get("price"), precision=6),
        )

    # Display the table
    console.print(table)

    # Display summary information
    console.print("\n[bold]Volume Summary[/bold]")
    console.print(f"Total Volume: [yellow]{total_volume:.2f} {normalize_to}[/yellow]")

    # Get top quote currencies by volume
    console.print("\n[bold]Top Quote Currencies by Volume[/bold]")
    for i, (quote, volume) in enumerate(list(quote_volumes.items())[:5], 1):
        console.print(f"{i}. {quote}: [yellow]{volume:.2f} {quote}[/yellow]")

    # Get top base currencies by volume
    console.print("\n[bold]Top Base Currencies by Volume[/bold]")
    for i, (base, volume) in enumerate(list(base_volumes.items())[:5], 1):
        console.print(f"{i}. {base}: [yellow]{volume:.2f} {base}[/yellow]")

    # Show last update time
    if timestamp:
        console.print(
            f"\\nLast updated: [cyan]{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            f"[/cyan]"
        )
    console.print("\n" + "-" * 80 + "\n")


def display_compared_volumes(exchange_data, all_volumes, normalize_to, limit):
    """Display comparison of volumes across exchanges."""
    normalized_currency = normalize_to.upper()
    sorted_volumes = sorted(all_volumes, key=_cli_volume_sort_key, reverse=True)

    # Limit the total number of entries if needed
    if limit > 0:
        sorted_volumes = sorted_volumes[:limit]

    # Create comparison table
    table = Table(
        title=(
            f"Top Markets by Normalized Volume ({normalized_currency}) Across Exchanges"
        )
    )

    # Add columns
    table.add_column("Rank", style="cyan", justify="right")
    table.add_column("Exchange", style="blue")
    table.add_column("Symbol", style="green")
    table.add_column(
        f"Normalized Volume ({normalized_currency})",
        style="yellow",
        justify="right",
    )
    table.add_column("Base Volume", justify="right")
    table.add_column("Quote Volume", justify="right")
    table.add_column("Price", justify="right")

    # Add rows
    for i, v in enumerate(sorted_volumes, 1):
        table.add_row(
            str(i),
            v["exchange"],
            v["symbol"],
            _format_optional_number(v.get("normalizedVolume")),
            _format_optional_number(v.get("baseVolume")),
            _format_optional_number(v.get("quoteVolume")),
            _format_optional_number(v.get("price"), precision=6),
        )

    # Display the table
    console.print(table)

    # Create exchange volume summary
    console.print("\n[bold]Exchange Volume Summary[/bold]")
    total_all_exchanges = sum(data["total_volume"] for data in exchange_data.values())

    # Create exchange comparison table
    summary_table = Table(
        title=f"Normalized Volume by Exchange in {normalized_currency}"
    )
    summary_table.add_column("Rank", style="cyan", justify="right")
    summary_table.add_column("Exchange", style="blue")
    summary_table.add_column(
        f"Total {normalized_currency} Volume", style="yellow", justify="right"
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
def exchanges(  # noqa: C901
    show_features: bool = typer.Option(
        False, "--features", "-f", help="Show exchange features (e.g., has OHLC)"
    ),
    filter_by: list[str] = typer.Option(  # noqa: B008
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
    try:
        # Get all available exchanges
        all_exchanges = Exchanges.get_all_exchanges()

        # Filter by features if specified
        exchanges_list = all_exchanges
        if filter_by:
            exchanges_list = Exchanges.filter_exchanges_by_features(
                exchanges_list, filter_by
            )

        # Filter by market if base or quote currency is specified
        exchange_market_pairs: dict[str, list[str]] = {}
        if base_currency or quote_currency:
            console.print("[bold]Filtering exchanges with market pairs...[/bold]")
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
                    f"{exchange_id}: {len(exchange_market_pairs[exchange_id])} "
                    f"matching pairs"
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
    except PyCCXTError as error:
        _render_library_error("Error listing exchanges", error)


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
    exchange_id = exchange if exchange else state["market"]

    try:
        console.print(f"[bold]Loading markets from {exchange_id}...[/bold]")

        try:
            # Get markets using the Exchanges class
            filtered_markets = Exchanges.get_exchange_markets(
                exchange_id=str(exchange_id),
                base_currency=base_currency,
                quote_currency=quote_currency,
                active_only=active_only,
                sort_by=sort_by,
            )

            exchange_instance = Exchanges.get_exchange_instance(str(exchange_id))

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

    except PyCCXTError as error:
        _render_library_error("Error loading markets", error)
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
