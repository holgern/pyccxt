import datetime
import unittest
from unittest.mock import MagicMock, patch

from pyccxt.market_volume import MarketVolume


class TestMarketVolume(unittest.TestCase):
    """Test cases for the MarketVolume class."""

    @patch("ccxt.binance")
    def test_initialization(self, mock_binance):
        """Test the MarketVolume initialization."""
        # Setup mock
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {"BTC/USDT": {}}
        mock_binance.return_value = mock_exchange

        # Create MarketVolume instance
        market_volume = MarketVolume()

        # Assertions
        self.assertEqual(market_volume.market, "binance")
        self.assertEqual(market_volume.base_currency, "BTC")
        self.assertIsNotNone(market_volume.exchange)
        mock_exchange.load_markets.assert_called_once()

    @patch("ccxt.binance")
    def test_get_volumes(self, mock_binance):
        """Test getting market volumes."""
        # Setup mock
        mock_exchange = MagicMock()

        # Mock markets
        mock_markets = {
            "BTC/USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT"},
            "ETH/USDT": {"id": "ETHUSDT", "symbol": "ETH/USDT"},
            "BTC/EUR": {"id": "BTCEUR", "symbol": "BTC/EUR"},
            "ETH/BTC": {"id": "ETHBTC", "symbol": "ETH/BTC"},
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
            "ETH/BTC": {
                "symbol": "ETH/BTC",
                "baseVolume": 3000.0,
                "quoteVolume": 200.0,
                "last": 0.0667,
                "timestamp": 1625097600000,
                "datetime": "2021-07-01T00:00:00.000Z",
            },
        }

        mock_exchange.fetch_tickers.return_value = mock_tickers
        mock_exchange.has = {"fetchTickers": True}

        # Mock BTC prices
        def mock_fetch_ticker(symbol):
            if symbol == "BTC/USDT":
                return {"last": 30000.0}
            elif symbol == "BTC/EUR":
                return {"last": 25000.0}
            return mock_tickers.get(symbol, {})

        mock_exchange.fetch_ticker = mock_fetch_ticker

        mock_binance.return_value = mock_exchange

        # Create MarketVolume instance - disable base filtering for test
        market_volume = MarketVolume(filter_by_base=False)
        market_volume._last_update = datetime.datetime.now() - datetime.timedelta(
            hours=1
        )

        # Setup the necessary internal state manually for testing
        market_volume._markets = mock_markets
        from pyccxt.ticker import Ticker

        market_volume._tickers = {
            "BTC/USDT": Ticker.from_ccxt(mock_tickers["BTC/USDT"]),
            "ETH/USDT": Ticker.from_ccxt(mock_tickers["ETH/USDT"]),
            "BTC/EUR": Ticker.from_ccxt(mock_tickers["BTC/EUR"]),
            "ETH/BTC": Ticker.from_ccxt(mock_tickers["ETH/BTC"]),
        }
        market_volume._prices = {
            "USDT": 30000.0,
            "EUR": 25000.0,
        }

        # Calculate volumes directly
        market_volume._volumes = market_volume._calculate_volumes()

        # Test get_volumes
        volumes = market_volume.get_volumes()

        # Assertions
        self.assertTrue(len(volumes) > 0)

        # Check that volumes are sorted by BTC volume in descending order
        for i in range(len(volumes) - 1):
            self.assertGreaterEqual(
                volumes[i]["volume"], volumes[i + 1]["volume"]
            )

        # Test get_top_markets
        top_markets = market_volume.get_top_markets(limit=2)
        self.assertEqual(len(top_markets), 2)

        # Test get_total_volume
        total_volume = market_volume.get_total_volume()
        self.assertGreater(total_volume, 0)

        # Test volume by currency
        quote_volumes = market_volume.get_volume_by_quote_currency()
        self.assertIn("USDT", quote_volumes)

        base_volumes = market_volume.get_volume_by_base_currency()
        self.assertIn("BTC", base_volumes)


if __name__ == "__main__":
    unittest.main()
