"""
NEW TILE USAGE TRACKER (v 3.51)
    Bugfix: Padded blank tiles would erroneously decrement the unused tile count. This has been fixed.

    Now accounts for pieces only partially covered by loaded art. There are two methods for handling this:
        Their loaded tiles stay at the corresponding file boundary when arranging (ala Flex2).
        Unlike Flex2, this considers leading pieces that may start before the loaded art file as well.
    +++ No Padding:
        Missing tiles stay missing with no blank tiles added.
        Partial runs stay as they are, and their tiles bookend the art file.
    +++ Padding:
        All tiles are rearranged by usage, and partial runs are completed.
        Blank tiles are added to pad out space to avoid sprite corruption.
    Instead of tracking EVERY used tile, this uses a structure of non-overlapping tile ranges.
    Only considers a single file loaded into VRAM, and doesn't account for DPLCs.

Parameters:
    blocks: non-overlapping used ranges, and their order of first usage, along with partial run flags.
    pieces: reference to pieces and their original starting tile indices, for later remapping
    head/tail_padding: counts of planned blanks from before/after the ORIGINAL art range
"""

# Throwaway object to build this function
class Tracker(object):
    def __init__(self):
        self.map_frames = None
        self.vram_tiles = None

    def art_collect_tile_usage(self, pad_missing=False):
        if not self.map_frames:
            raise ValueError("Load or create mapping frames before optimization.")

        if not self.vram_tiles:
            raise ValueError("Load art tiles before optimization.")

        # Not creating usage here. That dictionary will be returned at the end

        art_start = min(self.vram_tiles)    # start of the art file
        art_end = max(self.vram_tiles) + 1  # end of the art file
        base_tile = 0       # self.vram_spinbox.value()

        # Collect these in their own temp structures. We'll use these to form blocks
        # Usage dictionary will be updated after that is finished
        runs = []
        candidates = [] # Actual piece references determined later

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
                # With padding, keep candidates until we know which pieces the
                # enlarged output may reach, including shared missing tiles.
                if not pad_missing and (end <= art_start or start >= art_end):
                    continue

                if pad_missing:
                    # Track loaded tiles; Missing indices act as blank placeholders
                    run_start, run_end = start, end
                    keep_start = keep_end = False
                else:
                    # Track only loaded tiles and preserve partial coverage
                    run_start = max(start, art_start) # actual start (piece's starting index, or art's starting index)
                    run_end = min(end, art_end) # actual end (piece's end index, or art's end index)
                    keep_start = start < art_start # For partial runs that start BEFORE the art file
                    keep_end = end > art_end # For partial runs that start AFTER the art file

                # Add to the list of runs (with a zero-based usage index)
                runs.append((run_start, run_end, len(runs), keep_start, keep_end))
                # Add piece candidate
                candidates.append((piece, start, end))

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

        # Art tile padding handling starts here
        head_padding = tail_padding = 0

        if pad_missing:
            # Start with complete merged blocks touching original art.
            # Padding grows output while maintaining the starting address.
            # If that growth reaches a wholly missing piece, include its candidate too.
            # This way, rearrangement won't make that piece display unrelated art.
            all_blocks = blocks
            output_end = art_end

            while True:
                blocks = [
                    block for block in all_blocks
                    if block[0] < output_end and block[1] > art_start
                ]

                # Merged blocks do not overlap, so shared missing tiles count once
                head_padding = sum(
                    max(0, min(end, art_start) - start)
                    for start, end, *_ in blocks
                )
                tail_padding = sum(
                    max(0, end - max(start, art_end))
                    for start, end, *_ in blocks
                )
                padded_end = art_end + head_padding + tail_padding

                if padded_end == output_end:
                    break
                output_end = padded_end

            # Include every piece belonging to a selected complete block,
            # including ones sharing only its missing tile positions
            piece_refs = [
                (piece, start)
                for piece, start, end in candidates
                if any(block[0] <= start and end <= block[1] for block in blocks)
            ]
        else:
            # Preserve original starts, including starts before loaded art
            piece_refs = [(piece, start) for piece, start, _ in candidates]

        # Return usage dictionary
        return {"blocks": blocks, "pieces": piece_refs, "head_padding": head_padding, "tail_padding": tail_padding}

    def art_arrange_tiles(self, pad_missing=False, remove_unused=False):
        """
        Order each art buffer's used blocks by first mapping usage.
        """
        # Get tile usage across all loaded sprite frames
        try:
            usage = self.art_collect_tile_usage(pad_missing=pad_missing)
        except ValueError as e:
            print(f"error: {e}")
            return False

        # Count only used ORIGINAL tiles; padding positions are not loaded art.
        art_start = min(self.vram_tiles)
        art_end = max(self.vram_tiles) + 1
        loaded_used = sum(
            max(0, min(end, art_end) - max(start, art_start))
            for start, end, *_ in usage["blocks"]
        )
        # Count is purely for checking whether to ask for tile removal
        unused_count = len(self.vram_tiles) - loaded_used

        padded_count = len(self.vram_tiles) + usage["head_padding"] + usage["tail_padding"]

        if unused_count > 0:
            # Ask whether to remove unused tiles, or stick them at the end of the buffer
            # This prototype uses the remove_unused parameter
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

        # Retain unused ORIGINAL tiles only if removal was not requested
        if not remove_unused:
            # Append unused tiles BEFORE trailing partial blocks
            cursor = art_start

            # Add unused tiles before, in-between, and after blocks
            for start, end, *_ in usage["blocks"]:
                loaded_start = max(start, art_start)
                loaded_end = min(end, art_end)
                if loaded_start >= loaded_end:
                    continue
                order.extend(range(cursor, loaded_start))
                cursor = loaded_end

            # Include unused tiles after the final block
            order.extend(range(cursor, art_end))

        # Keep trailing partial blocks at the actual end of the output
        # otherwise these pieces would display unused art in place of missing tiles
        order.extend(
            index for start, end, *_ in trailing_blocks
            for index in range(start, end)
        )

        # Validate the final placement, not the virtual original indices used
        # for blanks. The output keeps the original art load address
        if min(self.vram_tiles) + len(order) > 2048:
            print("error: The arranged art would exceed VRAM tile 2047.")
            return False

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

        # Use the same loaded-range count as Arrange, excluding padding positions.
        art_start = min(self.vram_tiles)
        art_end = max(self.vram_tiles) + 1
        loaded_used = sum(
            max(0, min(end, art_end) - max(start, art_start))
            for start, end, *_ in usage["blocks"]
        )
        # Count is purely for the prompt that notes number of tiles removed
        _unused_count = len(self.vram_tiles) - loaded_used

        # Retain original tile order, and leave out unused tiles
        _order = [
            index for start, end, *_ in usage["blocks"]
            for index in range(start, end)
        ]

        return True

""" Example:
Consider a Motobug Sprite with only ONE frame. Its art is located at $200, with the last tile at $210 (17 tiles).

Here are its pieces:
Piece 0: 4*2 tiles starting at Tile 0 ($200-$207).
Piece 1: 4*1 tiles starting at Tile 8 ($208-$20B).
Piece 2: 1*2 tiles starting at Tile 12 ($20C-$20D).
Piece 3: 3*1 tiles starting at Tile 14 ($20E-$210).

Suppose we want to make the Motobug larger. Here are the new pieces. Art is still at [$200-$211):
Piece 0: 4*2 tiles starting at Tile -3 ($1FD-$204). <- partially covered
Piece 1: 4*2 tiles starting at Tile 5 ($205-$20C).
Piece 2: 1*3 tiles starting at Tile 13 ($20D-$20F).
Piece 3: 4*1 tiles starting at Tile 16 ($210-$213). <- partially covered

Now let's swap pieces 2 and 3, so that we would actually WANT to rearrange tiles accordingly.
Piece 0: 4*2 tiles starting at Tile -3 ($1FD-$204). <- partially covered
Piece 1: 4*2 tiles starting at Tile 5 ($205-$20C).
Piece 2: 4*1 tiles starting at Tile 16 ($210-$213). <- partially covered
Piece 3: 1*3 tiles starting at Tile 13 ($20D-$20F).

By standard function, our new piece 2 (formerly piece 3) still has its tiles appended at the end of the file.

With the new optional functionality, it has its one tile ($210) moved to where piece 2 starts,
and has 3 blank tiles following it. Then the 3 tiles for the new Piece 3 will follow.
At the same time, Piece 0's 3 leading tiles, which are outside of the art file, would be accounted for,
with 3 padding tiles at the start of the newly arranged art.
"""
