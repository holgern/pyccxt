import unittest
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from pyccxt.cli import app
from pyccxt.exceptions import MarketLoadError


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
