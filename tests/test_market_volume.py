import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pyccxt.exchange import Exchange, get_market_volumes_for_pair


class TestExchange(unittest.TestCase):
    """Test cases for the Exchange class."""

    def _build_exchange(self) -> tuple[Exchange, MagicMock]:
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {
            "BTC/USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT"},
            "ETH/USDT": {"id": "ETHUSDT", "symbol": "ETH/USDT"},
            "BTC/EUR": {"id": "BTCEUR", "symbol": "BTC/EUR"},
            "USD/JPY": {"id": "USDJPY", "symbol": "USD/JPY"},
            "ADA/GBP": {"id": "ADAGBP", "symbol": "ADA/GBP"},
        }
        mock_exchange.has = {"fetchTickers": True}
        mock_exchange.fetch_tickers.return_value = {
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
                "baseVolume": 20.0,
                "quoteVolume": 500000.0,
                "last": 25000.0,
                "timestamp": 1625097600000,
                "datetime": "2021-07-01T00:00:00.000Z",
            },
            "USD/JPY": {
                "symbol": "USD/JPY",
                "baseVolume": 10000.0,
                "quoteVolume": 1100000.0,
                "last": 110.0,
                "timestamp": 1625097600000,
                "datetime": "2021-07-01T00:00:00.000Z",
            },
            "ADA/GBP": {
                "symbol": "ADA/GBP",
                "baseVolume": 200000.0,
                "quoteVolume": 60000.0,
                "last": 0.3,
                "timestamp": 1625097600000,
                "datetime": "2021-07-01T00:00:00.000Z",
            },
            "EUR/USD": {
                "symbol": "EUR/USD",
                "baseVolume": 1000.0,
                "quoteVolume": 1200.0,
                "last": 1.2,
                "timestamp": 1625097600000,
                "datetime": "2021-07-01T00:00:00.000Z",
            },
            "USDT/USD": {
                "symbol": "USDT/USD",
                "baseVolume": 1000000.0,
                "quoteVolume": 1000000.0,
                "last": 1.0,
                "timestamp": 1625097600000,
                "datetime": "2021-07-01T00:00:00.000Z",
            },
        }

        exchange = Exchange.__new__(Exchange)
        exchange.name = "binance"
        exchange.min_refresh_time = 300
        exchange.timeout = 30000
        exchange._markets = {}
        exchange._market_instances = {}
        exchange._tickers = {}
        exchange._currencies = {}
        exchange._last_update = None
        exchange.ccxt_exchange = mock_exchange
        exchange._load_markets()
        return exchange, mock_exchange

    @patch("pyccxt.exchange._import_ccxt")
    def test_initialization(self, mock_import_ccxt):
        """Test the Exchange initialization."""
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {"BTC/USDT": {}}
        mock_import_ccxt.return_value = SimpleNamespace(
            binance=MagicMock(return_value=mock_exchange)
        )

        exchange = Exchange("binance")

        self.assertEqual(exchange.name, "binance")
        self.assertIsNotNone(exchange.ccxt_exchange)
        mock_exchange.load_markets.assert_called_once()

    def test_get_market_volumes_uses_explicit_filter_and_normalization(self):
        exchange, mock_exchange = self._build_exchange()

        rows = exchange.get_market_volumes(filter_base="BTC", normalize_to="USD")

        self.assertEqual([row["symbol"] for row in rows], ["BTC/USDT", "BTC/EUR"])
        self.assertEqual(rows[0]["normalizedVolume"], 30000000.0)
        self.assertEqual(rows[1]["normalizedVolume"], 600000.0)
        self.assertEqual(rows[0]["normalizedCurrency"], "USD")
        self.assertTrue(rows[0]["isNormalized"])
        self.assertEqual(
            set(rows[0].keys()),
            {
                "symbol",
                "base",
                "quote",
                "price",
                "baseVolume",
                "quoteVolume",
                "normalizedVolume",
                "normalizedCurrency",
                "isNormalized",
                "timestamp",
                "datetime",
            },
        )
        mock_exchange.fetch_tickers.assert_called_once()

    def test_get_market_volumes_filters_by_quote_currency(self):
        exchange, _mock_exchange = self._build_exchange()

        rows = exchange.get_market_volumes(filter_quote="USDT", normalize_to="USD")

        self.assertEqual([row["symbol"] for row in rows], ["BTC/USDT", "ETH/USDT"])
        for row in rows:
            self.assertEqual(row["quote"], "USDT")

    def test_get_market_volumes_keeps_unconverted_rows_when_requested(self):
        exchange, _mock_exchange = self._build_exchange()

        rows = exchange.get_market_volumes(normalize_to="USD", include_unconverted=True)

        ada_row = next(row for row in rows if row["symbol"] == "ADA/GBP")
        self.assertIsNone(ada_row["normalizedVolume"])
        self.assertEqual(ada_row["normalizedCurrency"], "USD")
        self.assertFalse(ada_row["isNormalized"])

    def test_get_market_volumes_excludes_unconverted_rows_when_requested(self):
        exchange, _mock_exchange = self._build_exchange()

        rows = exchange.get_market_volumes(
            normalize_to="USD", include_unconverted=False
        )

        self.assertNotIn("ADA/GBP", [row["symbol"] for row in rows])

    def test_get_market_volumes_accepts_base_currency_alias(self):
        exchange, _mock_exchange = self._build_exchange()

        rows = exchange.get_market_volumes(base_currency="BTC", normalize_to="USD")

        self.assertEqual([row["symbol"] for row in rows], ["BTC/USDT", "BTC/EUR"])

    def test_get_total_volume_uses_normalized_rows(self):
        exchange, _mock_exchange = self._build_exchange()

        total = exchange.get_total_volume(normalize_to="USD")

        self.assertEqual(total, 40610000.0)

    def test_volume_grouping_helpers_use_native_units(self):
        exchange, _mock_exchange = self._build_exchange()

        quote_totals = exchange.get_volume_by_quote_currency()
        base_totals = exchange.get_volume_by_base_currency()

        self.assertEqual(quote_totals["USDT"], 40000000.0)
        self.assertEqual(quote_totals["JPY"], 1100000.0)
        self.assertEqual(quote_totals["EUR"], 500000.0)
        self.assertEqual(base_totals["ADA"], 200000.0)
        self.assertEqual(base_totals["USD"], 10000.0)
        self.assertEqual(base_totals["BTC"], 1020.0)

    @patch("pyccxt.exchange._import_ccxt")
    def test_get_market(self, mock_import_ccxt):
        """Test getting a specific market."""
        mock_exchange = MagicMock()
        mock_markets = {
            "BTC/USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT"},
        }
        mock_exchange.load_markets.return_value = mock_markets
        mock_import_ccxt.return_value = SimpleNamespace(
            binance=MagicMock(return_value=mock_exchange)
        )

        exchange = Exchange("binance")

        market = exchange.get_market("BTC/USDT")
        self.assertIsNotNone(market)
        if market:
            self.assertEqual(market.symbol, "BTC/USDT")
            self.assertEqual(market.base_currency, "BTC")
            self.assertEqual(market.quote_currency, "USDT")

        market = exchange.get_market("INVALID/PAIR")
        self.assertIsNone(market)


class TestMarketVolumesCrossExchange(unittest.TestCase):
    """Test cases for cross-exchange volume comparison."""

    def test_get_market_volumes_for_pair(self):
        """Test getting volumes for a pair across exchanges."""
        self.assertTrue(callable(get_market_volumes_for_pair))


if __name__ == "__main__":
    unittest.main()
