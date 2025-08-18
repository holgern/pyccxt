import unittest

from pyccxt.ticker import Ticker


class TestTicker(unittest.TestCase):
    def test_ticker_initialization(self):
        """Test basic initialization of Ticker class."""
        ticker = Ticker("BTC/USD")
        self.assertEqual(ticker.symbol, "BTC/USD")
        self.assertEqual(ticker.info, {})
        self.assertIsNone(ticker.timestamp)
        self.assertIsNone(ticker.high)
        self.assertIsNone(ticker.low)
        self.assertIsNone(ticker.bid)
        self.assertIsNone(ticker.ask)

    def test_ticker_from_ccxt(self):
        """Test creating a Ticker from CCXT response."""
        # Sample CCXT ticker response
        ccxt_ticker = {
            "symbol": "BTC/USD",
            "timestamp": 1625097600000,
            "datetime": "2021-07-01T00:00:00.000Z",
            "high": 35000.0,
            "low": 33000.0,
            "bid": 34000.0,
            "bidVolume": 1.5,
            "ask": 34100.0,
            "askVolume": 2.0,
            "vwap": 34500.0,
            "open": 33500.0,
            "close": 34800.0,
            "last": 34800.0,
            "previousClose": 33600.0,
            "change": 1300.0,
            "percentage": 3.88,
            "average": 34150.0,
            "baseVolume": 1000.0,
            "quoteVolume": 34500000.0,
            "info": {"raw_exchange_data": "value"},
        }

        ticker = Ticker.from_ccxt(ccxt_ticker)

        self.assertEqual(ticker.symbol, "BTC/USD")
        self.assertEqual(ticker.timestamp, 1625097600000)
        self.assertEqual(ticker.datetime, "2021-07-01T00:00:00.000Z")
        self.assertEqual(ticker.high, 35000.0)
        self.assertEqual(ticker.low, 33000.0)
        self.assertEqual(ticker.bid, 34000.0)
        self.assertEqual(ticker.bidVolume, 1.5)
        self.assertEqual(ticker.ask, 34100.0)
        self.assertEqual(ticker.askVolume, 2.0)
        self.assertEqual(ticker.vwap, 34500.0)
        self.assertEqual(ticker.open, 33500.0)
        self.assertEqual(ticker.close, 34800.0)
        self.assertEqual(ticker.last, 34800.0)
        self.assertEqual(ticker.previousClose, 33600.0)
        self.assertEqual(ticker.change, 1300.0)
        self.assertEqual(ticker.percentage, 3.88)
        self.assertEqual(ticker.average, 34150.0)
        self.assertEqual(ticker.baseVolume, 1000.0)
        self.assertEqual(ticker.quoteVolume, 34500000.0)
        self.assertEqual(ticker.info, {"raw_exchange_data": "value"})

    def test_ticker_to_dict(self):
        """Test converting a Ticker to dictionary."""
        ticker = Ticker("BTC/USD")
        ticker.timestamp = 1625097600000
        ticker.high = 35000.0
        ticker.low = 33000.0

        ticker_dict = ticker.to_dict()

        self.assertEqual(ticker_dict["symbol"], "BTC/USD")
        self.assertEqual(ticker_dict["timestamp"], 1625097600000)
        self.assertEqual(ticker_dict["high"], 35000.0)
        self.assertEqual(ticker_dict["low"], 33000.0)
        self.assertIsNone(ticker_dict["ask"])


class TestPrice(unittest.TestCase):
    # Mock responses for Price tests
    pass
