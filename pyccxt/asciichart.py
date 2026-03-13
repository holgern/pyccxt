from __future__ import annotations

import shutil
from collections.abc import Iterable, Sequence
from importlib import import_module
from typing import Any


def _get_asciiplot() -> tuple[Any, Any]:
    try:
        asciiplot = import_module("asciiplot")
    except ImportError as exc:
        raise RuntimeError(
            "asciiplot is required to render ASCII charts. Install 'asciiplot'."
        ) from exc
    return asciiplot.Color, asciiplot.asciiize


class AsciiChart:
    def __init__(
        self,
        prices: Sequence[float],
        title: str = "Price Chart",
        x_axis_description: str = "Time",
        y_axis_description: str = "Price",
    ) -> None:
        self.prices = self._normalize_prices(prices)
        self.title = title
        self.x_axis_description = x_axis_description
        self.y_axis_description = y_axis_description

    def _normalize_prices(self, prices: Sequence[float]) -> list[float]:
        values: object = prices

        if hasattr(values, "__getitem__"):
            try:
                price_column = values["price"]  # type: ignore[index]
            except (KeyError, TypeError, IndexError):
                price_column = None
            else:
                values = price_column

        if isinstance(values, (str, bytes)):
            raise ValueError("Price data must be a non-empty numeric sequence.")

        if not isinstance(values, Sequence):
            if not isinstance(values, Iterable):
                raise ValueError("Price data must be a non-empty numeric sequence.")
            values = list(values)

        if len(values) == 0:
            raise ValueError("Price data must not be empty.")

        normalized_prices: list[float] = []
        for price in values:
            try:
                normalized_prices.append(float(price))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Price data must contain only numeric values."
                ) from exc

        return normalized_prices

    def render(self, height: int = 20, inter_points_margin: int = 2) -> str:
        try:
            color, asciiize = _get_asciiplot()
        except Exception:
            return self._render_fallback(height, inter_points_margin)

        try:
            return asciiize(
                self.prices,
                sequence_colors=[color.BLUE_3B],
                height=height,
                inter_points_margin=inter_points_margin,
                tick_point_color=color.RED_1,
                label_color=color.BLUE_VIOLET,
                title=self.title,
                title_color=color.RED_1,
                x_axis_description=self.x_axis_description,
                y_axis_description=self.y_axis_description,
                center_horizontally=True,
            )
        except Exception:
            return self._render_fallback(height, inter_points_margin)

    def _render_fallback(self, height: int, inter_points_margin: int) -> str:
        chart_height = max(2, int(height))
        min_price = min(self.prices)
        max_price = max(self.prices)
        price_range = max_price - min_price
        label_width = max(
            len(self._format_label(max_price)), len(self.y_axis_description)
        )
        terminal_width = shutil.get_terminal_size((100, chart_height + 5)).columns
        available_width = max(10, terminal_width - label_width - 4)

        prices = self.prices
        if len(prices) > available_width and available_width > 1:
            last_index = len(prices) - 1
            prices = [
                prices[round((last_index * index) / (available_width - 1))]
                for index in range(available_width)
            ]

        step = max(1, int(inter_points_margin))
        width = 1 + ((len(prices) - 1) * step)
        if width > available_width and len(prices) > 1:
            step = 1
            width = 1 + (len(prices) - 1)

        points: list[tuple[int, int]] = []
        for index, price in enumerate(prices):
            x_pos = index * step
            if price_range == 0:
                y_pos = chart_height // 2
            else:
                scaled = (price - min_price) / price_range
                y_pos = chart_height - 1 - int(round(scaled * (chart_height - 1)))
            points.append((x_pos, y_pos))

        grid = [[" "] * width for _ in range(chart_height)]
        previous_x: int | None = None
        previous_y: int | None = None
        for x_pos, y_pos in points:
            if previous_x is not None and previous_y is not None:
                span = x_pos - previous_x
                if span > 1:
                    for offset in range(1, span):
                        ratio = offset / span
                        interpolated_y = int(
                            round(previous_y + ((y_pos - previous_y) * ratio))
                        )
                        if grid[interpolated_y][previous_x + offset] == " ":
                            grid[interpolated_y][previous_x + offset] = "."
            grid[y_pos][x_pos] = "*"
            previous_x = x_pos
            previous_y = y_pos

        lines = [f"{self.y_axis_description}:"]

        for row_index, row in enumerate(grid):
            if price_range == 0:
                row_value = min_price
            else:
                row_value = max_price - ((price_range * row_index) / (chart_height - 1))
            label = self._format_label(row_value).rjust(label_width)
            lines.append(f"{label} |{''.join(row)}|")

        lines.append(f"{' ' * label_width} +{'-' * width}+")
        lines.append(f"{self.x_axis_description}: {len(prices)} points")
        lines.append(
            f"Range: {self._format_label(min_price)} -> {self._format_label(max_price)}"
        )
        return "\n".join(lines)

    def _format_label(self, value: float) -> str:
        absolute_value = abs(value)
        if absolute_value >= 100:
            precision = 2
        elif absolute_value >= 1:
            precision = 4
        else:
            precision = 6
        return f"{value:,.{precision}f}".rstrip("0").rstrip(".")
