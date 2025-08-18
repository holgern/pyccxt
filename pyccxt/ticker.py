from typing import Any, Optional


class Ticker:
    def __init__(self, symbol: str, info: Optional[dict[str, Any]] = None):
        """
        Initialize a ticker for a cryptocurrency trading pair.

        Args:
            symbol: The trading pair symbol (e.g. 'BTC/USD', 'ETH/BTC')
            info: The original response from the exchange API
        """
        self.symbol: str = symbol
        self.info: dict[str, Any] = info or {}
        self.timestamp: Optional[int] = None
        self.datetime: Optional[str] = None
        self.high: Optional[float] = None
        self.low: Optional[float] = None
        self.bid: Optional[float] = None
        self.bidVolume: Optional[float] = None
        self.ask: Optional[float] = None
        self.askVolume: Optional[float] = None
        self.vwap: Optional[float] = None
        self.open: Optional[float] = None
        self.close: Optional[float] = None
        self.last: Optional[float] = None
        self.previousClose: Optional[float] = None
        self.change: Optional[float] = None
        self.percentage: Optional[float] = None
        self.average: Optional[float] = None
        self.baseVolume: Optional[float] = None
        self.quoteVolume: Optional[float] = None

    @classmethod
    def from_ccxt(cls, ccxt_ticker: dict[str, Any]) -> "Ticker":
        """
        Create a Ticker instance from a CCXT ticker response.

        Args:
            ccxt_ticker: The ticker response from CCXT

        Returns:
            A new Ticker instance populated with data from the CCXT response
        """
        ticker = cls(ccxt_ticker.get("symbol", ""))
        ticker.info = ccxt_ticker.get("info", {})
        ticker.timestamp = ccxt_ticker.get("timestamp")
        ticker.datetime = ccxt_ticker.get("datetime")
        ticker.high = ccxt_ticker.get("high")
        ticker.low = ccxt_ticker.get("low")
        ticker.bid = ccxt_ticker.get("bid")
        ticker.bidVolume = ccxt_ticker.get("bidVolume")
        ticker.ask = ccxt_ticker.get("ask")
        ticker.askVolume = ccxt_ticker.get("askVolume")
        ticker.vwap = ccxt_ticker.get("vwap")
        ticker.open = ccxt_ticker.get("open")
        ticker.close = ccxt_ticker.get("close")
        ticker.last = ccxt_ticker.get("last")
        ticker.previousClose = ccxt_ticker.get("previousClose")
        ticker.change = ccxt_ticker.get("change")
        ticker.percentage = ccxt_ticker.get("percentage")
        ticker.average = ccxt_ticker.get("average")
        ticker.baseVolume = ccxt_ticker.get("baseVolume")
        ticker.quoteVolume = ccxt_ticker.get("quoteVolume")

        return ticker

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the ticker to a dictionary.

        Returns:
            A dictionary representation of the ticker
        """
        return {
            "symbol": self.symbol,
            "info": self.info,
            "timestamp": self.timestamp,
            "datetime": self.datetime,
            "high": self.high,
            "low": self.low,
            "bid": self.bid,
            "bidVolume": self.bidVolume,
            "ask": self.ask,
            "askVolume": self.askVolume,
            "vwap": self.vwap,
            "open": self.open,
            "close": self.close,
            "last": self.last,
            "previousClose": self.previousClose,
            "change": self.change,
            "percentage": self.percentage,
            "average": self.average,
            "baseVolume": self.baseVolume,
            "quoteVolume": self.quoteVolume,
        }
