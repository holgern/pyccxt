import unittest
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from pyccxt.cli import app


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
