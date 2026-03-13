import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pyccxt.exceptions import (
    ExchangeNotFoundError,
    MarketLoadError,
    TickerFetchError,
)
from pyccxt.exchange import Exchange


class TestExchangeExceptions(unittest.TestCase):
    @patch("pyccxt.exchange._import_ccxt")
    def test_unknown_exchange_raises_exchange_not_found(self, mock_import_ccxt):
        mock_import_ccxt.return_value = SimpleNamespace()

        with self.assertRaises(ExchangeNotFoundError):
            Exchange("unknown")

    @patch("pyccxt.exchange._import_ccxt")
    def test_market_load_failure_raises_market_load_error(self, mock_import_ccxt):
        mock_exchange = MagicMock()
        mock_exchange.load_markets.side_effect = RuntimeError("boom")
        mock_import_ccxt.return_value = SimpleNamespace(
            binance=MagicMock(return_value=mock_exchange)
        )

        with self.assertRaises(MarketLoadError):
            Exchange("binance")

    @patch("pyccxt.exchange._import_ccxt")
    def test_fetch_all_tickers_total_failure_raises_ticker_fetch_error(
        self, mock_import_ccxt
    ):
        mock_exchange = MagicMock()
        mock_exchange.load_markets.return_value = {
            "BTC/USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT"}
        }
        mock_exchange.has = {"fetchTickers": False}
        mock_exchange.fetch_ticker.side_effect = RuntimeError("ticker failed")
        mock_import_ccxt.return_value = SimpleNamespace(
            binance=MagicMock(return_value=mock_exchange)
        )

        exchange = Exchange("binance")

        with self.assertRaises(TickerFetchError):
            exchange.fetch_all_tickers()
