from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter

def render_tile(pixels, palette, *, palette_line=0, transparent_zero=True):
    """
    Render 64 palette indices into an unscaled 8×8 QImage.
    """
    if len(pixels) != 64:
        raise ValueError("A tile must contain exactly 64 pixels.")

    if not isinstance(palette_line, int) or not 0 <= palette_line <= 3:
        raise ValueError("Palette line must be an integer from 0 to 3.")

    # Create a transparent 8×8 image
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    # Each palette line contains 16 colors
    line_offset = palette_line * 16

    # loop through each pixel in the tile
    for index, pixel_value in enumerate(pixels):
        # Index zero is optionally transparent
        if transparent_zero and pixel_value == 0:
            continue

        # Color to use (based on palette line and pixel value)
        color_index = line_offset + pixel_value

        # Pixel coordinates
        x = index % 8   # COLUMN
        y = index // 8  # ROW

        # Render pixel
        image.setPixelColor(x, y, palette[color_index])

    # Return tile
    return image

def render_tile_grid(tiles, palette, *, columns=16, tile_count=2048, palette_line=0, transparent_zero=True):
    """Render tiles keyed by index into an unscaled grid image."""
    if not isinstance(columns, int) or columns < 1:
        raise ValueError("Grid columns must be a positive integer.")

    if not isinstance(tile_count, int) or tile_count < 1:
        raise ValueError("Tile count must be a positive integer.")

    # Round up to accommodate a partially filled final row
    rows = (tile_count + columns - 1) // columns

    # Create a transparent tile grid image
    image = QImage(columns * 8, rows * 8, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)

    try:
        for tile_index, pixels in tiles.items():
            # Ignore slots outside this grid
            if not 0 <= tile_index < tile_count:
                continue

            # Render tile
            tile_image = render_tile(pixels, palette, palette_line=palette_line, transparent_zero=transparent_zero)

            # Convert the slot index into grid coordinates
            x = (tile_index % columns) * 8
            y = (tile_index // columns) * 8

            # Draw rendered tile
            painter.drawImage(x, y, tile_image)

    finally:
        # Close painter, even on failure
        painter.end()

    return image
