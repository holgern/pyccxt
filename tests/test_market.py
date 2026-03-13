import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

from pyccxt.market import Market
from pyccxt.ohlc import OHLC


class TestMarketPrecision(unittest.TestCase):
    def test_format_price_to_precision_uses_ccxt_helper(self):
        ccxt_exchange = MagicMock()
        ccxt_exchange.price_to_precision.return_value = "123.4500"
        exchange = SimpleNamespace(
            name="binance", ccxt_exchange=ccxt_exchange, _tickers={}
        )
        market = Market(
            exchange=cast(Any, exchange),
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
            exchange=cast(Any, exchange),
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
            exchange=cast(Any, exchange),
            symbol="BTC/USDT",
            base_currency="BTC",
            quote_currency="USDT",
            market_info={"precision": {"price": 2}},
        )

        result = market.format_price_to_precision(123.4567)

        self.assertEqual(result, 123.46)


class TestMarketOhlcvRows(unittest.TestCase):
    def setUp(self):
        self.exchange = SimpleNamespace(
            name="binance", ccxt_exchange=object(), _tickers={}
        )
        self.market = Market(
            exchange=cast(Any, self.exchange),
            symbol="BTC/USDT",
            base_currency="BTC",
            quote_currency="USDT",
            market_info={"precision": {"price": 2}},
        )
        self.market._ohlc_timeframe = "1h"
        self.market._ohlc_data = MagicMock()
        self.market._ohlc_data.get_price_list.return_value = [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "timestamp_ms": 1704067200000,
                "price": 42000.0,
                "price_type": "close",
                "volume": 10.0,
            }
        ]
        self.market._ohlc_data.get_ohlc_data.return_value = [
            OHLC(
                timestamp=1704067200000,
                open_price=41900.0,
                high_price=42100.0,
                low_price=41850.0,
                close_price=42000.0,
                volume=10.0,
                symbol="BTC/USDT",
                timeframe="1h",
            )
        ]

    def test_get_price_rows_returns_collection_rows(self):
        result = self.market.get_price_rows(price_type="close")

        self.assertEqual(result[0]["price"], 42000.0)
        collection = cast(Any, self.market._ohlc_data)
        collection.get_price_list.assert_called_once_with(price_type="close")

    def test_get_ohlcv_rows_returns_normalized_candle_rows(self):
        result = self.market.get_ohlcv_rows()

        self.assertEqual(result[0]["timestamp"], 1704067200000)
        self.assertEqual(result[0]["open"], 41900.0)
        self.assertEqual(result[0]["high"], 42100.0)
        self.assertEqual(result[0]["low"], 41850.0)
        self.assertEqual(result[0]["close"], 42000.0)
        self.assertEqual(result[0]["volume"], 10.0)
        self.assertEqual(result[0]["symbol"], "BTC/USDT")
        self.assertEqual(result[0]["timeframe"], "1h")
