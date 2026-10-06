# To-Do: import formats

def decode_art(data, compression="Uncompressed"):
    """
    Decode binary art data into a series of 64-index tiles.

    Empty input is rejected; empty decompressed output produces an empty tile list.
    """
    raw_data = bytearray(data)
    if not raw_data:
        raise ValueError("Art file contains no tile data.")

    """if compression == "Nemesis":
        raw_data = decompress.nemesis(raw_data)
    elif compression == "Kosinski":
        raw_data = decompress.kosinski(raw_data)
    elif compression == "Kosinski-M":
        raw_data = decompress.kosinski_mod(raw_data)
    elif compression != "Uncompressed":
        raise ValueError(f"Unsupported art compression format: {compression}")"""

    if len(raw_data) % 32:
        raise ValueError(f"Art data contains {len(raw_data)} bytes; expected a multiple of 32.")

    tiles = []

    for start in range(0, len(raw_data), 32):
        pixels = []
        for byte in raw_data[start:start + 32]:
            pixels.extend((byte >> 4, byte & 0x0F))
        tiles.append(pixels)

    return tiles

def encode_art(tiles, compression="Uncompressed"):
    """Validate and encode 64-index tiles into binary art data.

    Saving does not support compression yet.
    """

    art_data = bytearray()

    for tile_index, pixels in enumerate(tiles):
        if len(pixels) != 64:
            raise ValueError(f"Art tile {tile_index} must contain exactly 64 pixels.")
        if any(not isinstance(pixel, int) or not 0 <= pixel <= 15 for pixel in pixels):
            raise ValueError(f"Art tile {tile_index} pixel indices must be integers from 0 to 15.")
        for index in range(0, 64, 2):
            art_data.append((pixels[index] << 4) | pixels[index + 1])

    if not art_data:
        raise ValueError("No art tiles are available to encode.")

#    if compression == "Nemesis":
#        art_data = compress.nemesis(art_data)

    return bytes(art_data)
