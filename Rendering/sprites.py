from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter

from Rendering.tiles import render_tile

class SpriteRenderer:
    """
    Builds pieces from tiles in VRAM, and mapping data.
    """
    def __init__(self):
        self.tiles = {}
        self.palette = ()
        self.source_state = None
        self.piece_cache = {}

    def prepare(self, tiles, palette, *, art_revision=None):
        """
        Discard cached piece images when their shared source data changes.
        From: sprite_prepare_piece_cache
        """
        # Get pixel and color data of the current sprite
        state = (art_revision, tuple(color.rgba() for color in palette))

        # If data changed, clear cache
        if (art_revision is None or tiles is not self.tiles
            or state != self.source_state):
                self.piece_cache.clear()

        self.tiles = tiles
        self.palette = palette
        self.source_state = state

    def render_piece(self, piece, *, base_tile=0, base_palette=0):
        """
        Renders the given frame piece. Missing tiles stay transparent.
        From: sprite_get_piece_image
        """
        if self.source_state is None:
            raise RuntimeError("Source state not prepared before rendering sprites.")

        # Get piece dimensions (and validate them)
        width, height = piece["width"], piece["height"]
        if (not isinstance(width, int) or not isinstance(height, int)
                or not 1 <= width <= 4 or not 1 <= height <= 4):
            raise ValueError("Sprite piece width & height must be 1–4 tiles.")

        start_tile = (base_tile + piece["tile"]) & 2047
        pal_line = (base_palette + piece["palette"]) & 3
        x_flip, y_flip = bool(piece["x_flip"]), bool(piece["y_flip"])

        # Only properties that affect the piece's pixels belong in the key
        key = (start_tile, width, height, pal_line, x_flip, y_flip)
        cached = self.piece_cache.get(key)

        # Return cached piece image if we don't need to redraw
        if cached is not None:
            return QImage(cached)

        # Build a piece-sized image only when it is missing from the cache
        image = QImage(width * 8, height * 8, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)

        try:
            # Tiles are ordered top-to-bottom, then left-to-right
            for tx in range(width):
                for ty in range(height):
                    tile_index = start_tile + tx * height + ty
                    pixels = self.tiles.get(tile_index)

                    # if nothing to draw here, skip to the next tile
                    if pixels is None:
                        continue

                    # Render tile
                    tile_image = render_tile(pixels, self.palette,
                        palette_line=pal_line, transparent_zero=True)

                    # Draw rendered tile
                    painter.drawImage(tx * 8, ty * 8, tile_image)

        finally:
            # Close painter, even on failure
            painter.end()

        # Mirror/flip image AFTER drawing tiles, instead of altering placement mid-draw
        if x_flip or y_flip:
            image = image.mirrored(x_flip, y_flip)

        # Cache and return sprite piece (key = piece data; value = image)
        self.piece_cache[key] = image
        return QImage(image)

    def render_frame(self, pieces, *, canvas_size=(256, 256), origin=None, base_tile=0, base_palette=0):
        """
        Build a frame from the given pieces. Pieces are drawn in reverse-mapping order.
        From: sprite_build_frame_image

        (Note: This does not apply overlay, or hover transparency. Just renders the frame)
        """
        canvas_w, canvas_h = canvas_size
        if origin is None:
            origin = (canvas_w // 2, canvas_h // 2)
        center_x, center_y = origin

        image = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)

        try:
            # Build frame, with earlier indexed pieces overlapping later ones
            for piece in reversed(pieces):
                piece_image = self.render_piece(piece, base_tile=base_tile, base_palette=base_palette)
                painter.drawImage(center_x + piece["x"], center_y + piece["y"], piece_image)

        finally:
            # Close painter, even on failure
            painter.end()

        # Return compiled sprite frame
        return image
