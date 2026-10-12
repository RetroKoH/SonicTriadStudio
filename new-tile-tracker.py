"""
NEW TILE USAGE TRACKER (v 3)
    Now accounts for pieces only partially covered by loaded art.
        Their loaded tiles stay at the corresponding file boundary when arranging (ala Flex2).
        Unlike Flex2, this considers leading pieces that may start before the loaded art file as well.
        Missing tiles stay missing with no blank tiles added (Might introduce this as an option).
    Instead of tracking EVERY used tile, this uses a structure of non-overlapping tile ranges.
    Only considers a single file loaded into VRAM, and doesn't account for DPLCs.

Parameters:
    blocks: non-overlapping used ranges, and their order of first usage
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

                # Track only loaded tiles. A partial run must remain at the
                # boundary so its missing portion stays outside the art file
                loaded_start = max(start, art_start) # actual start (piece's starting index, or art's starting index)
                loaded_end = min(end, art_end) # actual end (piece's end index, or art's end index)
                keep_start = start < art_start # For partial runs that start BEFORE the art file
                keep_end = end > art_end # For partial runs that start AFTER the art file

                # Add to the list of runs (with a zero-based usage index)
                runs.append((loaded_start, loaded_end, len(runs), keep_start, keep_end))
                # Add piece (Keep the original start index, even if it is before loaded art)
                piece_refs.append((piece, start))

        # Merge overlapping runs in their original tile order
        blocks = []

        # Note: Start is inclusive, end is exclusive: [10, 14) = [10, 11, 12, 13]
        for start, end, first_use, keep_start, keep_end in sorted(runs):
            # If this isn't the 1st block, and its start precedes the end of the last block...
            if blocks and start < blocks[-1][1]:
                old_start, old_end, old_use, old_keep_start, old_keep_end = blocks[-1]

                #... merge the current overlapping run into the last block instead of starting a new one
                blocks[-1] = (
                    old_start, # Preserve the earlier run start
                    max(old_end, end), # Use the later run end
                    min(old_use, first_use), # Preserve the earliest usage
                    old_keep_start or keep_start,  # Preserve leading partial coverage
                    old_keep_end or keep_end,  # Preserve trailing partial coverage
                )

            # Otherwise, start a new block at the end of the list
            else:
                blocks.append((start, end, first_use, keep_start, keep_end))

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
        unused_count = len(self.vram_tiles) - sum(end - start for start, end, *_ in usage["blocks"])

        if unused_count > 0:
            # Ask whether to remove unused tiles, or stick them at the end of the buffer
            print("A prompt to remove unused tiles goes here.")

        # Partition blocks according to their boundary constraints
        # Leading = pieces start with a tile index BEFORE the loaded art
        # Trailing = pieces end with a tile index AFTER the loaded art
        leading_blocks, ordinary_blocks, trailing_blocks = [], [], []

        for block in usage["blocks"]:
            if block[3]: # 3 = keep_start flag
                # A block constrained at BOTH edges covers the entire loaded file
                # Include it once at the beginning, no other blocks fit
                leading_blocks.append(block)
            elif block[4]: # 4 = keep_end flag
                trailing_blocks.append(block)
            else:
                ordinary_blocks.append(block)

        # Sort used tiles by order of first usage, leaving out unused tiles
        # Leading partial blocks go first, then ordinary blocks by first usage
        order = [
            index for start, end, *_ in (
                leading_blocks + sorted(ordinary_blocks, key=lambda block: block[2])
            )
            for index in range(start, end)
        ]

        # If the earlier prompt was answered 'YES', we skip this
        # section in order to remove unused tiles
        if True:
            # Append unused tiles BEFORE trailing partial blocks
            cursor = min(self.vram_tiles)
            art_end = max(self.vram_tiles) + 1

            # Add unused tiles before, in-between, and after blocks
            for start, end, *_ in usage["blocks"]:
                order.extend(range(cursor, start))
                cursor = end

            # Include unused tiles after the final block
            order.extend(range(cursor, art_end))

        # Keep trailing partial blocks at the actual end of the output
        # otherwise these pieces would display unused art in place of missing tiles
        order.extend(
            index for start, end, *_ in trailing_blocks
            for index in range(start, end)
        )

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
        _unused_count = len(self.vram_tiles) - sum(end - start for start, end, *_ in usage["blocks"])

        # Retain original tile order, and leave out unused tiles
        _order = [
            index for start, end, *_ in usage["blocks"]
            for index in range(start, end)
        ]
        return True
