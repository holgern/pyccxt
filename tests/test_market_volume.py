import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pyccxt.exchange import Exchange, get_market_volumes_for_pair


class TestExchange(unittest.TestCase):
    """Test cases for the Exchange class."""

    @patch("pyccxt.exchange._import_ccxt")
    def test_initialization(self, mock_import_ccxt):
        """Test the Exchange initialization."""
        # Setup mock
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {"BTC/USDT": {}}
        mock_import_ccxt.return_value = SimpleNamespace(
            binance=MagicMock(return_value=mock_exchange)
        )

        # Create Exchange instance
        exchange = Exchange("binance")

        # Assertions
        self.assertEqual(exchange.name, "binance")
        self.assertIsNotNone(exchange.ccxt_exchange)
        mock_exchange.load_markets.assert_called_once()

    @patch("pyccxt.exchange._import_ccxt")
    def test_get_market_volumes(self, mock_import_ccxt):
        """Test getting market volumes."""
        # Setup mock
        mock_exchange = MagicMock()

        # Mock markets
        mock_markets = {
            "BTC/USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT"},
            "ETH/USDT": {"id": "ETHUSDT", "symbol": "ETH/USDT"},
            "BTC/EUR": {"id": "BTCEUR", "symbol": "BTC/EUR"},
        }
        mock_exchange.load_markets.return_value = mock_markets

        # Mock tickers
        mock_tickers = {
            "BTC/USDT": {
                "symbol": "BTC/USDT",
                "baseVolume": 1000.0,
                "quoteVolume": 30000000.0,
                "last": 30000.0,
                "timestamp": 1625097600000,
                "datetime": "2021-07-01T00:00:00.000Z",
            },
            "ETH/USDT": {
                "symbol": "ETH/USDT",
                "baseVolume": 5000.0,
                "quoteVolume": 10000000.0,
                "last": 2000.0,
                "timestamp": 1625097600000,
                "datetime": "2021-07-01T00:00:00.000Z",
            },
            "BTC/EUR": {
                "symbol": "BTC/EUR",
                "baseVolume": 500.0,
                "quoteVolume": 12500000.0,
                "last": 25000.0,
                "timestamp": 1625097600000,
                "datetime": "2021-07-01T00:00:00.000Z",
            },
        }

        def mock_fetch_ticker(symbol):
            return mock_tickers.get(symbol, {})

        mock_exchange.fetch_ticker = mock_fetch_ticker
        mock_exchange.fetch_tickers.return_value = mock_tickers
        mock_exchange.has = {"fetchTickers": True}

        mock_import_ccxt.return_value = SimpleNamespace(
            binance=MagicMock(return_value=mock_exchange)
        )

        # Create Exchange instance
        exchange = Exchange("binance")

        # Test that exchange was initialized
        self.assertIsNotNone(exchange.ccxt_exchange)

        # Test get_markets_by_base
        btc_markets = exchange.get_markets_by_base("BTC")
        self.assertEqual(len(btc_markets), 2)  # BTC/USDT and BTC/EUR
        for market in btc_markets:
            self.assertEqual(market.base_currency, "BTC")

        # Test get_markets_by_quote
        usdt_markets = exchange.get_markets_by_quote("USDT")
        self.assertEqual(len(usdt_markets), 2)  # BTC/USDT and ETH/USDT
        for market in usdt_markets:
            self.assertEqual(market.quote_currency, "USDT")

        # Test get_available_symbols
        symbols = exchange.get_available_symbols()
        self.assertIn("BTC/USDT", symbols)
        self.assertIn("ETH/USDT", symbols)
        self.assertIn("BTC/EUR", symbols)

    @patch("pyccxt.exchange._import_ccxt")
    def test_get_market(self, mock_import_ccxt):
        """Test getting a specific market."""
        # Setup mock
        mock_exchange = MagicMock()
        mock_markets = {
            "BTC/USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT"},
        }
        mock_exchange.load_markets.return_value = mock_markets
        mock_import_ccxt.return_value = SimpleNamespace(
            binance=MagicMock(return_value=mock_exchange)
        )

        # Create Exchange instance
        exchange = Exchange("binance")

        # Test get_market
        market = exchange.get_market("BTC/USDT")
        self.assertIsNotNone(market)
        if market:
            self.assertEqual(market.symbol, "BTC/USDT")
            self.assertEqual(market.base_currency, "BTC")
            self.assertEqual(market.quote_currency, "USDT")

        # Test non-existent market
        market = exchange.get_market("INVALID/PAIR")
        self.assertIsNone(market)


class TestMarketVolumesCrossExchange(unittest.TestCase):
    """Test cases for cross-exchange volume comparison."""

    def test_get_market_volumes_for_pair(self):
        """Test getting volumes for a pair across exchanges."""
        # This is more of an integration test and would require actual API calls
        # For unit testing, we would need to mock multiple exchanges
        # For now, just test that the function exists and can be called
        self.assertTrue(callable(get_market_volumes_for_pair))


if __name__ == "__main__":
    unittest.main()
