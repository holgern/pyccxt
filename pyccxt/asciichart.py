import pandas as pd
from asciiplot import Color, asciiize


class AsciiChart:
    def __init__(self, df: pd.DataFrame, title="Price Chart"):
        self.df = df
        self.title = title

    def plot(self, height=20, inter_points_margin=2):
        if self.df.empty:
            print("DataFrame is empty. Nothing to plot.")
            return

        prices = self.df["price"].tolist()

        print(
            asciiize(
                prices,
                sequence_colors=[Color.BLUE_3B],
                height=height,
                inter_points_margin=inter_points_margin,
                background_color=Color.LIGHT_SALMON_1,
                tick_point_color=Color.RED_1,
                label_color=Color.BLUE_VIOLET,
                label_background_color=Color.DEEP_PINK_3A,
                title=self.title,
                title_color=Color.RED_1,
                x_axis_description="Time",
                y_axis_description="Price",
                center_horizontally=True,
            )
        )
