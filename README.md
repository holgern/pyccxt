# pyccxt

A Python library for accessing cryptocurrency exchange data via CCXT. Get ticker prices and market volumes across different exchanges with aggregated analysis capabilities.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Overview

pyccxt provides a unified interface to access cryptocurrency market data from multiple exchanges. Built on top of the popular [CCXT](https://github.com/ccxt/ccxt) library, it offers:

- **Price aggregation** across multiple exchanges
- **Volume analysis** by market and currency
- **CLI tools** for quick market data access
- **Market comparison** and analysis
- **Exchange filtering** by features and supported pairs

## Installation

```bash
pip install pyccxt
```

### Development Installation

```bash
git clone https://github.com/holgern/pyccxt.git
cd pyccxt
pip install -e .
```

## Quick Start

### Python API

```python
from pyccxt import Exchange

# Initialize exchange
exchange = Exchange("binance")

# Get market volumes
volumes = exchange.get_market_volumes(base_currency="BTC", limit=10)
for volume_data in volumes:
    print(f"{volume_data['symbol']}: {volume_data['volume']:.2f}")

# Get price for specific pair
market = exchange.get_market("BTC/USDT")
if market:
    ticker = market.get_ticker()
    print(f"BTC/USDT: ${ticker.last:.2f}")
```

### Command Line Interface

```bash
# Get price for a trading pair
pyccxt price BTC USD --market binance

# Show market volumes
pyccxt volume --market binance --limit 10

# List available exchanges
pyccxt exchanges

# Filter exchanges by features
pyccxt exchanges --features --filter fetchOHLCV
```

## Features

### Exchange Data Access

- **Multiple Exchange Support**: Access 100+ cryptocurrency exchanges
- **Unified API**: Consistent interface across all exchanges
- **Market Data**: Real-time prices, volumes, and market info
- **OHLC Data**: Historical price data with multiple timeframes

### Volume Analysis

```python
from pyccxt import Exchange

# Compare volumes across exchanges
from pyccxt.exchange import get_market_volumes_for_pair

volumes = get_market_volumes_for_pair("BTC", "USDT", max_exchanges=5)
for vol in volumes:
    print(f"{vol['exchange']}: {vol['volume']:.2f} USDT")
```

### Market Filtering

```python
# Get markets by base currency
btc_markets = exchange.get_markets_by_base("BTC")

# Get markets by quote currency  
usd_markets = exchange.get_markets_by_quote("USD")

# Filter by minimum volume
high_volume = exchange.get_market_volumes(min_volume=1000000)
```

## CLI Usage

### Price Commands

```bash
# Basic price lookup
ccxt price BTC USD

# Specify exchange
ccxt price ETH EUR --market kraken

# Get detailed price info with spread and 24h change
ccxt price BTC USDT --market binance
```

### Volume Commands

```bash
# Show top volumes for an exchange
ccxt volume --market binance --limit 20

# Filter by quote currency
ccxt volume --market coinbase --quote USD --limit 15

# Compare volumes across exchanges
ccxt volume --base BTC --exchanges binance,kraken,coinbase
```

### Exchange Commands

```bash
# List all exchanges
ccxt exchanges

# Show exchange features
ccxt exchanges --features

# Filter by supported features
ccxt exchanges --filter fetchOHLCV,fetchTicker

# Filter by supported trading pairs
ccxt exchanges --base BTC --quote USD
```

## API Reference

### Exchange Class

```python
from pyccxt import Exchange

exchange = Exchange("binance")
```

#### Methods

- `get_market(symbol)` - Get Market instance for symbol
- `get_markets_by_base(currency)` - Filter by base currency
- `get_markets_by_quote(currency)` - Filter by quote currency
- `get_market_volumes(base_currency, min_volume, limit)` - Get volume data
- `fetch_all_tickers()` - Get all ticker data
- `get_total_volume(base_currency)` - Get total exchange volume

### Market Class

```python
market = exchange.get_market("BTC/USDT")
```

#### Methods

- `get_ticker()` - Get current price ticker
- `get_price()` - Get current price
- `refresh()` - Update market data
- `fetch_ohlc(timeframe, limit)` - Get OHLC data

### Ticker Class

```python
ticker = market.get_ticker()
print(f"Price: {ticker.last}")
print(f"24h Change: {ticker.percentage}%")
print(f"Volume: {ticker.quoteVolume}")
```

## Examples

### Market Volume Analysis

```python
from pyccxt import Exchange

def analyze_btc_markets():
    """Analyze BTC trading volumes across top exchanges."""
    
    # Top exchanges by volume
    exchanges = ["binance", "coinbase", "kraken", "huobi", "okx"]
    
    total_volumes = {}
    
    for exchange_name in exchanges:
        try:
            exchange = Exchange(exchange_name)
            btc_volumes = exchange.get_market_volumes(
                base_currency="BTC", 
                limit=10
            )
            
            total_vol = sum(vol['volume'] for vol in btc_volumes)
            total_volumes[exchange_name] = total_vol
            
            print(f"{exchange_name}: {total_vol:.2f} BTC volume")
            
        except Exception as e:
            print(f"Error with {exchange_name}: {e}")
    
    # Sort by volume
    sorted_exchanges = sorted(
        total_volumes.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    print("\\nTop exchanges by BTC volume:")
    for exchange, volume in sorted_exchanges:
        print(f"{exchange}: {volume:.2f} BTC")

if __name__ == "__main__":
    analyze_btc_markets()
```

### Price Comparison

```python
from pyccxt.exchange import get_market_volumes_for_pair

def compare_prices(base="BTC", quote="USDT"):
    """Compare prices across multiple exchanges."""
    
    volumes = get_market_volumes_for_pair(base, quote, max_exchanges=10)
    
    prices = []
    for vol_data in volumes:
        exchange_name = vol_data['exchange']
        try:
            exchange = Exchange(exchange_name)
            market = exchange.get_market(f"{base}/{quote}")
            if market:
                ticker = market.get_ticker()
                if ticker and ticker.last:
                    prices.append({
                        'exchange': exchange_name,
                        'price': ticker.last,
                        'volume': vol_data['volume']
                    })
        except Exception as e:
            print(f"Error getting price from {exchange_name}: {e}")
    
    # Sort by price
    prices.sort(key=lambda x: x['price'])
    
    print(f"\\n{base}/{quote} Price Comparison:")
    for price_data in prices:
        print(f"{price_data['exchange']}: ${price_data['price']:.2f} "
              f"(Vol: {price_data['volume']:.2f})")

if __name__ == "__main__":
    compare_prices("BTC", "USDT")
    compare_prices("ETH", "USD")
```

## Configuration

### Environment Variables

```bash
# Optional: Set default exchange
export PYCCXT_DEFAULT_EXCHANGE=binance

# Optional: Set API timeout
export PYCCXT_TIMEOUT=30
```

### Exchange-Specific Settings

```python
# Custom exchange configuration
exchange = Exchange("binance", {
    'timeout': 30000,
    'enableRateLimit': True,
    'sandbox': False  # Use sandbox/testnet if available
})
```

## Development

### Setup

```bash
git clone https://github.com/holgern/pyccxt.git
cd pyccxt
pip install -e .
pip install -r requirements-test.txt
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pyccxt

# Run specific test
pytest -k "test_exchange"
```

### Code Quality

```bash
# Format and lint
ruff check .
ruff format .

# Run pre-commit hooks
pre-commit run --all-files
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Run linting: `ruff check .`
6. Commit your changes: `git commit -am 'Add feature'`
7. Push to the branch: `git push origin feature-name`
8. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on top of [CCXT](https://github.com/ccxt/ccxt) - Cryptocurrency trading library
- CLI powered by [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
- Inspired by the need for unified cryptocurrency market analysis

## Changelog

### Latest Changes

- Modern Python type hints with `X | None` syntax
- Comprehensive CLI with market filtering
- Volume aggregation across exchanges
- Market comparison tools
- Improved error handling and logging

## Support

- **Issues**: [GitHub Issues](https://github.com/holgern/pyccxt/issues)
- **Documentation**: This README and inline code documentation
- **Examples**: See the `examples/` directory for usage examples

---

**Note**: This library is for informational purposes only. Always verify data from multiple sources before making trading decisions.
