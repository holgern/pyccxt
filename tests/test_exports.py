import unittest

import pyccxt
from pyccxt.exchange import Exchange, get_market_volumes_for_pair
from pyccxt.price_by_market import PriceByMarket


class TestExports(unittest.TestCase):
    def test_top_level_exports_are_truthful(self):
        self.assertIs(pyccxt.Exchange, Exchange)
        self.assertIs(pyccxt.PriceByMarket, Exchange)
        self.assertIs(pyccxt.get_market_volumes_for_pair, get_market_volumes_for_pair)

    def test_market_volume_fake_alias_is_removed(self):
        self.assertFalse(hasattr(pyccxt, "MarketVolume"))

    def test_price_by_market_module_is_honest_compatibility_shim(self):
        self.assertIs(PriceByMarket, Exchange)
        self.assertFalse(
            hasattr(
                __import__("pyccxt.price_by_market", fromlist=["*"]), "MarketVolume"
            )
        )
