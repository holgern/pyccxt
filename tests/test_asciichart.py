import unittest
from typing import Any, cast
from unittest.mock import patch

from pyccxt.asciichart import AsciiChart


class TestAsciiChart(unittest.TestCase):
    @patch("pyccxt.asciichart._get_asciiplot")
    def test_render_returns_non_empty_string_for_numeric_series(self, mock_get_plot):
        class FakeColor:
            BLUE_3B = "blue"
            RED_1 = "red"
            BLUE_VIOLET = "violet"

        mock_get_plot.return_value = (
            FakeColor,
            lambda prices, **kwargs: f"{kwargs['title']}: {','.join(map(str, prices))}",
        )

        chart = AsciiChart([1, 2.5, 3], title="BTC close")

        rendered = chart.render()

        self.assertTrue(rendered)
        self.assertIn("BTC close", rendered)
        self.assertIn("1.0,2.5,3.0", rendered)

    def test_empty_series_raises_value_error(self):
        with self.assertRaises(ValueError):
            AsciiChart([])

    def test_non_numeric_series_raises_value_error(self):
        with self.assertRaises(ValueError):
            AsciiChart(cast(Any, [1, "oops", 3]))

    @patch("pyccxt.asciichart._get_asciiplot", side_effect=TypeError("boom"))
    def test_render_falls_back_when_asciiplot_is_broken(self, _mock_get_plot):
        chart = AsciiChart([1, 2, 3], title="Fallback")

        rendered = chart.render(height=5, inter_points_margin=1)

        self.assertIn("Price:", rendered)
        self.assertIn("Time: 3 points", rendered)
        self.assertIn("Range: 1 -> 3", rendered)

    @patch("pyccxt.asciichart._get_asciiplot")
    def test_compatibility_shim_accepts_price_column_like_input(self, mock_get_plot):
        class FakeColor:
            BLUE_3B = "blue"
            RED_1 = "red"
            BLUE_VIOLET = "violet"

        mock_get_plot.return_value = (
            FakeColor,
            lambda prices, **kwargs: f"{kwargs['title']} {len(prices)}",
        )

        chart = AsciiChart(cast(Any, {"price": [1, 2, 3]}), title="Compat")

        rendered = chart.render()

        self.assertIn("Compat", rendered)
        self.assertIn("3", rendered)
