import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from pyccxt.cli import _build_ohlcv_table, _build_price_rows_table, app
from pyccxt.exceptions import MarketLoadError


def _sample_price_rows(price_type="close"):
    return [
        {
            "timestamp": datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            "timestamp_ms": 1704067200000,
            "price": 42000.0,
            "price_type": price_type,
            "volume": 10.5,
        },
        {
            "timestamp": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
            "timestamp_ms": 1704070800000,
            "price": 42150.0,
            "price_type": price_type,
            "volume": 12.25,
        },
    ]


def _sample_ohlcv_rows():
    return [
        {
            "timestamp": 1704067200000,
            "datetime": datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            "open": 41900.0,
            "high": 42100.0,
            "low": 41850.0,
            "close": 42000.0,
            "volume": 10.5,
            "symbol": "BTC/USDT",
            "timeframe": "1h",
        },
        {
            "timestamp": 1704070800000,
            "datetime": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
            "open": 42000.0,
            "high": 42200.0,
            "low": 41980.0,
            "close": 42150.0,
            "volume": 12.25,
            "symbol": "BTC/USDT",
            "timeframe": "1h",
        },
    ]


class FakeMarket:
    def __init__(
        self,
        fetch_result=True,
        price_rows=None,
        ohlcv_rows=None,
    ):
        self.fetch_result = fetch_result
        self.price_rows = price_rows if price_rows is not None else _sample_price_rows()
        self.ohlcv_rows = ohlcv_rows if ohlcv_rows is not None else _sample_ohlcv_rows()
        self.fetch_calls = []
        self.requested_price_types = []

    def fetch_ohlc(self, timeframe="1h", since=None, limit=None):
        self.fetch_calls.append(
            {"timeframe": timeframe, "since": since, "limit": limit}
        )
        return self.fetch_result

    def get_price_rows(self, price_type="close"):
        self.requested_price_types.append(price_type)
        if self.price_rows and price_type != "close":
            return [{**row, "price_type": price_type} for row in self.price_rows]
        return list(self.price_rows)

    def get_ohlcv_rows(self):
        return list(self.ohlcv_rows)


class FakeExchange:
    def __init__(self, market_obj=None, supports_ohlcv=True, name="kraken"):
        self.name = name
        self.market_obj = market_obj
        self.ccxt_exchange = SimpleNamespace(has={"fetchOHLCV": supports_ohlcv})

    def get_market(self, symbol):
        self.symbol = symbol
        return self.market_obj


class FakeNoSupportExchange:
    def __init__(self, market_obj=None, name="kraken"):
        self.name = name
        self.market_obj = market_obj

    def get_market(self, symbol):
        self.symbol = symbol
        return self.market_obj


class TestCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("pyccxt.cli.Exchanges.get_exchange_instance")
    @patch("pyccxt.cli.Exchanges.get_exchange_markets")
    def test_markets_command_displays_filtered_markets(
        self, mock_get_exchange_markets, mock_get_exchange_instance
    ):
        mock_get_exchange_markets.return_value = [
            {
                "symbol": "BTC/EUR",
                "base": "BTC",
                "quote": "EUR",
                "active": True,
            }
        ]
        mock_get_exchange_instance.return_value = SimpleNamespace(name="Kraken")

        result = self.runner.invoke(
            app,
            ["markets", "kraken", "--base", "BTC", "--quote", "EUR"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Markets on Kraken", result.output)
        self.assertIn("BTC/EUR", result.output)
        self.assertIn("Filters applied: Base: BTC, Quote: EUR", result.output)
        mock_get_exchange_markets.assert_called_once_with(
            exchange_id="kraken",
            base_currency="BTC",
            quote_currency="EUR",
            active_only=False,
            sort_by="symbol",
        )
        mock_get_exchange_instance.assert_called_once_with("kraken")

    @patch("pyccxt.cli.Exchanges.get_exchange_markets")
    def test_markets_command_handles_library_errors(self, mock_get_exchange_markets):
        mock_get_exchange_markets.side_effect = MarketLoadError(
            "Failed to load markets for exchange 'kraken': boom"
        )

        result = self.runner.invoke(app, ["markets", "kraken"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Error loading markets", result.output)
        self.assertIn(
            "Failed to load markets for exchange 'kraken': boom", result.output
        )

    @patch("pyccxt.cli.Exchanges.get_all_exchanges")
    @patch("pyccxt.cli.Exchange")
    def test_volume_command_passes_explicit_filter_and_normalization_args(
        self, mock_exchange_class, mock_get_all_exchanges
    ):
        mock_get_all_exchanges.return_value = ["kraken"]
        mock_exchange = mock_exchange_class.return_value
        mock_exchange.get_market_volumes.return_value = [
            {
                "symbol": "BTC/USD",
                "baseVolume": 10.0,
                "quoteVolume": 300000.0,
                "price": 30000.0,
                "normalizedVolume": 300000.0,
                "normalizedCurrency": "USD",
                "isNormalized": True,
            }
        ]
        mock_exchange.get_total_volume.return_value = 300000.0
        mock_exchange.get_volume_by_quote_currency.return_value = {"USD": 300000.0}
        mock_exchange.get_volume_by_base_currency.return_value = {"BTC": 10.0}

        result = self.runner.invoke(
            app,
            [
                "volume",
                "--market",
                "kraken",
                "--base",
                "BTC",
                "--quote",
                "USD",
                "--normalize-to",
                "EUR",
                "--limit",
                "5",
                "--min-volume",
                "2",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        mock_exchange.get_market_volumes.assert_called_once_with(
            filter_base="BTC",
            filter_quote="USD",
            normalize_to="EUR",
            min_volume=2.0,
            limit=5,
            include_unconverted=True,
        )
        mock_exchange.get_total_volume.assert_called_once_with(
            filter_base="BTC",
            filter_quote="USD",
            normalize_to="EUR",
            min_volume=2.0,
            include_unconverted=False,
        )
        self.assertIn("Volume (EUR)", result.output)
        self.assertIn("Total Volume: 300000.00 EUR", result.output)

    @patch("pyccxt.cli.Exchanges.get_all_exchanges")
    @patch("pyccxt.cli.Exchange")
    def test_volume_command_renders_na_for_missing_normalized_values(
        self, mock_exchange_class, mock_get_all_exchanges
    ):
        mock_get_all_exchanges.return_value = ["kraken"]
        mock_exchange = mock_exchange_class.return_value
        mock_exchange.get_market_volumes.return_value = [
            {
                "symbol": "ADA/GBP",
                "baseVolume": 1000.0,
                "quoteVolume": 500.0,
                "price": 0.5,
                "normalizedVolume": None,
                "normalizedCurrency": "USD",
                "isNormalized": False,
            }
        ]
        mock_exchange.get_total_volume.return_value = 0.0
        mock_exchange.get_volume_by_quote_currency.return_value = {"GBP": 500.0}
        mock_exchange.get_volume_by_base_currency.return_value = {"ADA": 1000.0}

        result = self.runner.invoke(app, ["volume", "--market", "kraken"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("ADA/GBP", result.output)
        self.assertIn("N/A", result.output)
        self.assertIn("Volume", result.output)
        self.assertIn("(USD)", result.output)

    @patch("pyccxt.cli.Exchanges.get_all_exchanges")
    @patch("pyccxt.cli.Exchange")
    def test_volume_compare_uses_dynamic_normalization_labels(
        self, mock_exchange_class, mock_get_all_exchanges
    ):
        mock_get_all_exchanges.return_value = ["kraken", "binance"]

        mock_exchange_class.side_effect = [
            SimpleNamespace(
                refresh_all=lambda: True,
                get_market_volumes=lambda **kwargs: [
                    {
                        "symbol": "BTC/USD",
                        "baseVolume": 5.0,
                        "quoteVolume": 150000.0,
                        "price": 30000.0,
                        "normalizedVolume": 150000.0,
                        "normalizedCurrency": "USD",
                        "isNormalized": True,
                    }
                ],
                get_total_volume=lambda **kwargs: 150000.0,
                get_volume_by_quote_currency=lambda **kwargs: {"USD": 150000.0},
                get_volume_by_base_currency=lambda **kwargs: {"BTC": 5.0},
            ),
            SimpleNamespace(
                refresh_all=lambda: True,
                get_market_volumes=lambda **kwargs: [
                    {
                        "symbol": "ETH/USD",
                        "baseVolume": 100.0,
                        "quoteVolume": 250000.0,
                        "price": 2500.0,
                        "normalizedVolume": 250000.0,
                        "normalizedCurrency": "USD",
                        "isNormalized": True,
                    }
                ],
                get_total_volume=lambda **kwargs: 250000.0,
                get_volume_by_quote_currency=lambda **kwargs: {"USD": 250000.0},
                get_volume_by_base_currency=lambda **kwargs: {"ETH": 100.0},
            ),
        ]

        result = self.runner.invoke(
            app,
            [
                "volume",
                "--market",
                "kraken,binance",
                "--compare",
                "--normalize-to",
                "USD",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Normalized Volume (USD)", result.output)
        self.assertIn("Normalized Volume by Exchange in USD", result.output)

    def test_price_rows_table_builder_exposes_expected_headers(self):
        table = _build_price_rows_table(
            exchange_name="kraken",
            symbol="BTC/USDT",
            timeframe="1h",
            price_type="close",
            rows=_sample_price_rows(),
        )

        self.assertEqual(
            [column.header for column in table.columns],
            ["#", "Timestamp", "Price Type", "Price", "Volume"],
        )

    def test_ohlcv_table_builder_exposes_expected_headers(self):
        table = _build_ohlcv_table(
            exchange_name="kraken",
            symbol="BTC/USDT",
            timeframe="1h",
            rows=_sample_ohlcv_rows(),
        )

        self.assertEqual(
            [column.header for column in table.columns],
            ["#", "Timestamp", "Open", "High", "Low", "Close", "Volume"],
        )

    @patch("pyccxt.cli.AsciiChart.render", return_value="ASCII CHART")
    @patch("pyccxt.cli.Exchange")
    def test_chart_command_renders_chart_title_and_plot(
        self, mock_exchange_class, mock_render
    ):
        fake_market = FakeMarket()
        mock_exchange_class.return_value = FakeExchange(market_obj=fake_market)

        result = self.runner.invoke(
            app,
            ["chart", "BTC", "USDT", "--market", "kraken", "--limit", "2"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("KRAKEN BTC/USDT 1h close", result.output)
        self.assertIn("ASCII CHART", result.output)
        self.assertEqual(
            fake_market.fetch_calls,
            [{"timeframe": "1h", "since": None, "limit": 2}],
        )
        self.assertEqual(fake_market.requested_price_types, ["close"])
        mock_render.assert_called_once()

    @patch("pyccxt.cli.AsciiChart.render", return_value="ASCII CHART")
    @patch("pyccxt.cli.Exchange")
    def test_chart_command_table_renders_price_headers(
        self, mock_exchange_class, _mock_render
    ):
        mock_exchange_class.return_value = FakeExchange(market_obj=FakeMarket())

        result = self.runner.invoke(
            app,
            ["chart", "BTC", "USDT", "--market", "kraken", "--table"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Timestamp", result.output)
        self.assertIn("Price Type", result.output)
        self.assertIn("Price", result.output)
        self.assertIn("Volume", result.output)

    @patch("pyccxt.cli.AsciiChart.render", return_value="ASCII CHART")
    @patch("pyccxt.cli.Exchange")
    def test_ohlcv_command_renders_chart_title_and_plot(
        self, mock_exchange_class, _mock_render
    ):
        fake_market = FakeMarket()
        mock_exchange_class.return_value = FakeExchange(market_obj=fake_market)

        result = self.runner.invoke(
            app,
            ["ohlcv", "BTC", "USDT", "--market", "kraken", "--limit", "2"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("KRAKEN BTC/USDT 1h close", result.output)
        self.assertIn("ASCII CHART", result.output)
        self.assertEqual(fake_market.requested_price_types, ["close"])

    @patch("pyccxt.cli.AsciiChart.render", return_value="ASCII CHART")
    @patch("pyccxt.cli.Exchange")
    def test_ohlcv_command_table_renders_candle_headers(
        self, mock_exchange_class, _mock_render
    ):
        mock_exchange_class.return_value = FakeExchange(market_obj=FakeMarket())

        result = self.runner.invoke(
            app,
            ["ohlcv", "BTC", "USDT", "--market", "kraken", "--table"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Timestamp", result.output)
        self.assertIn("Open", result.output)
        self.assertIn("High", result.output)
        self.assertIn("Low", result.output)
        self.assertIn("Close", result.output)
        self.assertIn("Volume", result.output)

    @patch("pyccxt.cli.Exchange")
    def test_chart_command_handles_missing_pair_cleanly(self, mock_exchange_class):
        mock_exchange_class.return_value = FakeExchange(market_obj=None)

        result = self.runner.invoke(
            app,
            ["chart", "BTC", "USDT", "--market", "kraken"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Trading pair BTC/USDT not found on kraken", result.output)
        self.assertIn("pyccxt markets kraken --base BTC --quote USDT", result.output)

    @patch("pyccxt.cli.Exchange")
    def test_chart_command_handles_failed_ohlc_fetch_cleanly(self, mock_exchange_class):
        mock_exchange_class.return_value = FakeExchange(
            market_obj=FakeMarket(fetch_result=False)
        )

        result = self.runner.invoke(
            app,
            ["chart", "BTC", "USDT", "--market", "kraken"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            "Could not fetch OHLCV data for BTC/USDT on kraken (1h)", result.output
        )
        self.assertIn("Requested exchange:", result.output)

    @patch("pyccxt.cli.Exchange")
    def test_chart_command_handles_unsupported_ohlcv_exchange_cleanly(
        self, mock_exchange_class
    ):
        mock_exchange_class.return_value = FakeExchange(
            market_obj=FakeMarket(), supports_ohlcv=False
        )

        result = self.runner.invoke(
            app,
            ["chart", "BTC", "USDT", "--market", "kraken"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("does not support OHLCV", result.output)
        self.assertIn("BTC/USDT", result.output)

    @patch("pyccxt.cli.Exchange")
    def test_ohlcv_command_handles_unsupported_ohlcv_exchange_cleanly(
        self, mock_exchange_class
    ):
        mock_exchange_class.return_value = FakeExchange(
            market_obj=FakeMarket(), supports_ohlcv=False
        )

        result = self.runner.invoke(
            app,
            ["ohlcv", "BTC", "USDT", "--market", "kraken"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("does not support OHLCV", result.output)

    @patch("pyccxt.cli.AsciiChart.render", return_value="ASCII CHART")
    @patch("pyccxt.cli.Exchange")
    def test_chart_command_handles_exchange_without_capability_metadata(
        self, mock_exchange_class, _mock_render
    ):
        mock_exchange_class.return_value = FakeNoSupportExchange(
            market_obj=FakeMarket()
        )

        result = self.runner.invoke(
            app,
            ["chart", "BTC", "USDT", "--market", "kraken"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("ASCII CHART", result.output)

    @patch("pyccxt.cli.AsciiChart.render", return_value="ASCII CHART")
    @patch("pyccxt.cli.Exchange")
    def test_chart_command_handles_empty_ohlcv_rows_without_crashing(
        self, mock_exchange_class, mock_render
    ):
        mock_exchange_class.return_value = FakeExchange(
            market_obj=FakeMarket(price_rows=[], ohlcv_rows=[])
        )

        result = self.runner.invoke(
            app,
            ["chart", "BTC", "USDT", "--market", "kraken", "--table"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No OHLCV price data available", result.output)
        mock_render.assert_not_called()
