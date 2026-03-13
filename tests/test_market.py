import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from pyccxt.market import Market


class TestMarketPrecision(unittest.TestCase):
    def test_format_price_to_precision_uses_ccxt_helper(self):
        ccxt_exchange = MagicMock()
        ccxt_exchange.price_to_precision.return_value = "123.4500"
        exchange = SimpleNamespace(
            name="binance", ccxt_exchange=ccxt_exchange, _tickers={}
        )
        market = Market(
            exchange=exchange,
            symbol="BTC/USDT",
            base_currency="BTC",
            quote_currency="USDT",
            market_info={"precision": {"price": 2}},
        )

        result = market.format_price_to_precision(123.4567)

        self.assertEqual(result, 123.45)
        ccxt_exchange.price_to_precision.assert_called_once_with("BTC/USDT", 123.4567)

    def test_format_amount_to_precision_uses_ccxt_helper(self):
        ccxt_exchange = MagicMock()
        ccxt_exchange.amount_to_precision.return_value = "0.12340000"
        exchange = SimpleNamespace(
            name="binance", ccxt_exchange=ccxt_exchange, _tickers={}
        )
        market = Market(
            exchange=exchange,
            symbol="BTC/USDT",
            base_currency="BTC",
            quote_currency="USDT",
            market_info={"precision": {"amount": 4}},
        )

        result = market.format_amount_to_precision(0.12345678)

        self.assertEqual(result, 0.1234)
        ccxt_exchange.amount_to_precision.assert_called_once_with(
            "BTC/USDT", 0.12345678
        )

    def test_precision_fallback_is_used_when_ccxt_helper_is_unavailable(self):
        exchange = SimpleNamespace(name="binance", ccxt_exchange=object(), _tickers={})
        market = Market(
            exchange=exchange,
            symbol="BTC/USDT",
            base_currency="BTC",
            quote_currency="USDT",
            market_info={"precision": {"price": 2}},
        )

        result = market.format_price_to_precision(123.4567)

        self.assertEqual(result, 123.46)
