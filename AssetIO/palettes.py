from PyQt6.QtGui import QColor

from constants import MDCOLOR_VALUES
from UI.md_color import snap_to_md_color


def decode_palette(data):
    """
    Convert binary palette data into QColor objects.

    Empty data returns an empty list.
    Incomplete words raise ValueError.
    """
    # Reject incomplete data
    if len(data) % 2:
        raise ValueError("Palette data must contain complete 2-byte colors.")

    colors = []

    # Each word: 0000 BBB0 GGG0 RRR0
    for index in range(0, len(data), 2):
        value = (data[index] << 8) | data[index + 1]

        colors.append(QColor(
            MDCOLOR_VALUES[(value >> 1) & 7],
            MDCOLOR_VALUES[(value >> 5) & 7],
            MDCOLOR_VALUES[(value >> 9) & 7],
        ))

    return colors


def encode_palette(colors):
    """
    Convert QColor objects into binary palette data.

    Channels use the existing MD color snapping rules.
    """
    data = bytearray()

    for color in colors:
        red = snap_to_md_color(color.red())
        green = snap_to_md_color(color.green())
        blue = snap_to_md_color(color.blue())

        data.append(blue << 1)
        data.append((green << 5) | (red << 1))

    return bytes(data)
