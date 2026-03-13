import unittest
from unittest.mock import MagicMock, patch

from pyccxt.exchanges import Exchanges


class TestExchangesFallback(unittest.TestCase):
    @patch("pyccxt.exchanges.requests.get")
    @patch("pyccxt.exchanges._import_ccxt")
    def test_get_exchange_markets_falls_back_to_kraken_api(
        self, mock_import_ccxt, mock_requests_get
    ):
        ccxt_error = ModuleNotFoundError(
            "No module named 'ccxt.static_dependencies.lighter_client'"
        )
        ccxt_error.name = "ccxt.static_dependencies.lighter_client"
        mock_import_ccxt.side_effect = ccxt_error

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": [],
            "result": {
                "XXBTZEUR": {
                    "base": "XXBT",
                    "quote": "ZEUR",
                    "status": "online",
                    "pair_decimals": 1,
                    "lot_decimals": 8,
                    "buy_leverage": [2, 3],
                    "sell_leverage": [2, 3],
                },
                "XETHZEUR": {
                    "base": "XETH",
                    "quote": "ZEUR",
                    "status": "online",
                    "pair_decimals": 2,
                    "lot_decimals": 8,
                    "buy_leverage": [],
                    "sell_leverage": [],
                },
            },
        }
        mock_requests_get.return_value = mock_response

        markets = Exchanges.get_exchange_markets(
            "kraken", base_currency="BTC", quote_currency="EUR"
        )

        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0]["symbol"], "BTC/EUR")
        self.assertEqual(markets[0]["base"], "BTC")
        self.assertEqual(markets[0]["quote"], "EUR")
        self.assertTrue(markets[0]["margin"])
        mock_requests_get.assert_called_once()

    def test_get_exchange_name_uses_fallback_display_name(self):
        self.assertEqual(Exchanges.get_exchange_name("kraken"), "Kraken")
        self.assertEqual(Exchanges.get_exchange_name("customex"), "customex")
