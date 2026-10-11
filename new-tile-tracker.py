"""
    NEW TILE USAGE TRACKER (v 1)
    This version only considers a single file loaded into VRAM, and doesn't account for DPLCs.

    used: which tiles are referenced by mappings
    runs: each piece's consecutive tile range, and its order of first usage.
    pieces: reference to pieces and their original starting tile indices, for later remapping
"""

# Throwaway object to build this function
class Tracker(object):
    def __init__(self):
        self.map_frames = None
        self.vram_tiles = None

    def art_collect_tile_usage(self):
        if not self.map_frames:
            raise ValueError("Load or create mapping frames before optimization.")

        if not self.vram_tiles:
            raise ValueError("Load art tiles before optimization.")

        usage = {"used": set(), "runs": [], "pieces": []}
        base_tile = 0       # self.vram_spinbox.value()

        # Iterate through every frame in the sprite
        for frame_index, pieces  in enumerate(self.map_frames):
            # Iterate through every piece in each frame
            for piece_index, piece in enumerate(pieces):
                width, height = piece["width"], piece["height"]

                # Validation check: dimensions
                if not 1 <= width <= 4 or not 1 <= height <= 4:
                    raise ValueError(f"Frame {frame_index}, piece {piece_index} has invalid dimensions.")

                # Get first tile, last tile, and range of tiles for this piece
                start = (base_tile + piece["tile"]) & 2047
                end = start + width * height
                tile_range = range(start, end)

                # Check how much of this piece's tiles are loaded into VRAM
                loaded_count = sum(index in self.vram_tiles for index in tile_range)

                # If art is completely missing, skip piece
                if loaded_count == 0:
                    continue

                # If partially loaded, raise exception (We will fix this)
                if loaded_count != len(tile_range):
                    raise ValueError(
                        f"Frame {frame_index}, piece {piece_index} "
                        "has missing art tiles. Load its complete tile run "
                        "before optimizing.")

                # Give the run a zero-based index
                first_use = len(usage["runs"])

                # Update set of used tiles with those in range (duplicate indices ignored)
                usage["used"].update(tile_range)
                # Add to the list of runs
                usage["runs"].append((start, end, first_use))
                # Add piece (and its starting tile)
                usage["pieces"].append((piece, start))

        return usage

""" Example: If the first piece uses tiles 10–13, and the second uses tiles 12–15.
{
    "used": {10, 11, 12, 13, 14, 15},
    "runs": [
        (10, 14, 0),
        (12, 16, 1),
    ],
    "pieces": [
        (first_piece, 10),
        (second_piece, 12),
    ],
}
"""