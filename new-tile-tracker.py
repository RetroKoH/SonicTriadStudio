"""
    NEW TILE USAGE TRACKER (v 2.1 -- Minor changes)
    This version gets rid of the redundant set, instead using a structure for non-overlapping tile ranges.
    Only considers a single file loaded into VRAM, and doesn't account for DPLCs.

New parameters:
    blocks: non-overlapping used ranges, and their order of first usage
    pieces: reference to pieces and their original starting tile indices, for later remapping

Old parameters:
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

        # Not creating usage here. That dictionary will be returned at the end

        art_start = min(self.vram_tiles)    # start of the art file
        art_end = max(self.vram_tiles) + 1  # end of the art file
        base_tile = 0       # self.vram_spinbox.value()

        # collect these in their own temp structures. We'll use these to form the blocks
        # Usage dictionary will be updated after that is finished
        runs = []
        piece_refs = []

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

                # If art is completely missing from the piece, skip piece
                if end <= art_start or start >= art_end:
                    continue

                # If partially loaded, raise exception (We will fix this)
                if start < art_start or end > art_end:
                    raise ValueError(
                        f"Frame {frame_index}, piece {piece_index} "
                        "has missing art tiles. Load its complete tile run "
                        "before optimizing.")

                # we no longer need a set of used tiles. This is scrapped
                # usage["used"].update(tile_range)
                # Add to the list of runs (with a zero-based usage index)
                runs.append((start, end, len(runs))) # formerly stored in usage["runs"]
                # Add piece (and its starting tile)
                piece_refs.append((piece, start)) # formerly stored in usage["pieces"]

        # Merge overlapping runs in their original tile order
        blocks = []

        # Note: Start is inclusive, end is exclusive: [10, 14) = [10, 11, 12, 13]
        for start, end, first_use in sorted(runs):
            # If this isn't the 1st block, and its start precedes the end of the last block...
            if blocks and start < blocks[-1][1]:
                old_start, old_end, old_use = blocks[-1]

                #... merge the current overlapping run into the last block instead of starting a new one
                blocks[-1] = (
                    old_start, # Preserve the earlier run start
                    max(old_end, end), # Use the later run end
                    min(old_use, first_use), # Preserve the earliest usage
                )

            # Otherwise, start a new block at the end of the list
            else:
                blocks.append((start, end, first_use))

        # Return usage dictionary
        return {"blocks": blocks, "pieces": piece_refs}

    def art_arrange_tiles(self):
        """
        Order each art buffer's used blocks by first mapping usage.
        """
        # Get tile usage across all loaded sprite frames
        try:
            usage = self.art_collect_tile_usage()
        except ValueError as e:
            print(f"error: {e}")
            return False

        # Count is purely for checking whether to ask for tile removal
        unused_count = len(self.vram_tiles) - sum(end - start for start, end, _ in usage["blocks"])

        if unused_count > 0:
            # Ask whether to remove unused tiles, or stick them at the end of the buffer
            print("A prompt to remove unused tiles goes here.")

        # Sort used tiles by order of first usage, leaving out unused tiles
        order = [
            index for start, end, _ in sorted(
                usage["blocks"], key=lambda block: block[2]
            )
            for index in range(start, end)
        ]

        # If the earlier prompt was answered 'YES', we skip this
        # section in order to remove unused tiles
        if True:
            # Append unused tiles in their original order
            cursor = min(self.vram_tiles)
            art_end = max(self.vram_tiles) + 1

            # Add unused tiles before, in-between, and after blocks
            for start, end, _ in usage["blocks"]:
                order.extend(range(cursor, start))
                cursor = end

            # Include unused tiles after the final block
            order.extend(range(cursor, art_end))

        return True

    def art_strip_unused_tiles(self):
        """
        Confirm removal without rearranging the remaining used tiles.
        """
        # Get tile usage across all loaded sprite frames
        try:
            usage = self.art_collect_tile_usage()
        except ValueError as e:
            print(f"error: {e}")
            return False

        # Count is purely for the prompt that notes number of tiles removed
        _unused_count = len(self.vram_tiles) - sum(end - start for start, end, _ in usage["blocks"])

        # Retain original tile order, and leave out unused tiles
        _order = [
            index for start, end, _ in usage["blocks"]
            for index in range(start, end)
        ]
        return True
