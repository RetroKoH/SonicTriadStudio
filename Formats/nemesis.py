from Formats.decompress import Decompress
from Formats.compress import Compress

class NemesisDecomp(Decompress):
    """
    Decompress a Nemesis-encoded file.
    """
    def decompress(self):
        try:
            self.output = []

            tile_count = self.read_word()
            xor_mode = tile_count >= 0x8000
            row_count = (tile_count & 0x7FFF) * 8

            code_lengths = [0] * 256
            code_pixels = [0] * 256
            code_repeats = [0] * 256

            pixel = 0

            while True:
                value = self.read_byte()

                if value >= 0x80:
                    if value == 0xFF:
                        break
                    pixel = value & 0xF

                else:
                    length = 8 - (value & 0xF)
                    offset = self.read_byte() << length
                    for i in range(0, 1 << length):
                        code_lengths[offset + i] = value & 0xF
                        code_pixels[offset + i] = pixel
                        code_repeats[offset + i] = ((value & 0x70) >> 4) + 1

            pixel_count = 8
            pixel_row = 0
            xor_row = 0

            while True:
                # Devon's code (and the original decomp) originally performed a fixed 8-bit peek
                # (A final Huffman code might need only 1 bit, yet the decoder still tries to peek at 8.)
                # Raised an error if any of those eight bits extend beyond the supplied data.
                # Instead, peek at up to 8 bits, and fill out the rest with zeroes

                # Peek at up to eight real bits.
                available = min(8, (len(self.data_input) - self.position) * 8 - self.bit)

                if available <= 0:
                    raise IndexError("Not enough data left to decode a Nemesis run.")

                # Zero-fill missing low bits for the table lookup only.
                index = self.read_bits(available, True) << (8 - available)

                if index >= 0b11111100:
                    self.read_bits(6)
                    pixel = self.read_bits(7)
                    repeat = ((pixel & 0x70) >> 4) + 1
                    pixel &= 0xF

                else:
                    self.read_bits(code_lengths[index])
                    pixel = code_pixels[index]
                    repeat = code_repeats[index]

                for i in range(0, repeat):
                    pixel_row = (pixel_row << 4) | pixel
                    pixel_count -= 1

                    if pixel_count <= 0:
                        if not xor_mode:
                            self.write_long(pixel_row)

                        else:
                            xor_row ^= pixel_row
                            self.write_long(xor_row)

                        row_count -= 1

                        if row_count <= 0:
                            return self.output

                        pixel_count = 8
                        pixel_row = 0

        except Exception as e:
            print(e)
            return None

class NemesisComp(Compress):
    """
    Compress a file in the Nemesis format.

    Credit: Clownacy (Original .c Huffman compressor)
    """
    # A symbol packs a pixel and a run length: (pixel << 3) | (repeat - 1).
    # Seven initial Huffman bits leave room for the reserved-prefix adjustment.
    MAX_CODE_BITS = 7
    INLINE_PREFIX = 0b111111

    def find_runs(self, xor_mode):
        runs = []
        occurrences = [0] * 128
        previous_pixel = -1
        repeat = 0

        for position, value in enumerate(self.data_input):
            # XOR against the previous ORIGINAL four-byte row, across tiles too.
            if xor_mode and position >= 4:
                value ^= self.data_input[position - 4]

            for pixel in (value >> 4, value & 0xF):
                if repeat and (pixel != previous_pixel or repeat == 8):
                    symbol = (previous_pixel << 3) | (repeat - 1)
                    runs.append(symbol)
                    occurrences[symbol] += 1
                    repeat = 0
                previous_pixel = pixel
                repeat += 1

        if repeat:
            symbol = (previous_pixel << 3) | (repeat - 1)
            runs.append(symbol)
            occurrences[symbol] += 1
        return runs, occurrences

    def compute_code_lengths(self, symbols, occurrences):
        """
        Package-merge: compute Huffman lengths limited to seven bits.
        """
        if not symbols:
            return {}
        if len(symbols) == 1:
            return {symbols[0]: 1}

        # Nodes are (weight, symbol, children). Leaves have no children.
        leaves = [(occurrences[symbol], symbol, None) for symbol in symbols]
        leaves.sort(key=lambda node: (node[0], node[1]))
        nodes = leaves
        for _level in range(1, self.MAX_CODE_BITS):
            packages = []
            for i in range(0, len(nodes) - 1, 2):
                left, right = nodes[i:i + 2]
                packages.append((left[0] + right[0], None, (left, right)))
            # Stable sorting puts leaves before equal-weight packages.
            nodes = sorted(leaves + packages, key=lambda node: node[0])

        lengths = dict.fromkeys(symbols, 0)
        pending = list(nodes[:2 * len(symbols) - 2])

        while pending:
            _weight, symbol, children = pending.pop()

            if children is None:
                lengths[symbol] += 1

            else:
                pending.extend(children)

        return lengths

    def compute_codes(self, lengths, occurrences):
        """
        Assign canonical codes while leaving 111111 for inline runs.
        """
        # Prefer frequent symbols on ties; the rare tail gets extended.
        symbols = sorted(lengths, key=lambda symbol: (
            lengths[symbol], -occurrences[symbol], symbol & 7, symbol >> 3))
        codes = {}
        code = -1
        previous_length = 0
        modifier = 0

        for symbol in symbols:
            length = lengths[symbol] + modifier
            code = (code + 1) << (length - previous_length)
            previous_length = length

            # Split the all-ones branch before six bits, or the 111110
            # branch at/after six bits. All subsequent codes gain one bit.
            if modifier == 0 and (
                    (length < 6 and code == (1 << length) - 1) or
                    (length >= 6 and code >> (length - 6) == 0b111110)
            ):
                code <<= 1
                length += 1
                previous_length = length
                modifier = 1
            codes[symbol] = (code, length)
        return codes

    def encoded_size(self, codes, occurrences, last_symbol):
        # Header + table terminator + pixel markers + two bytes per code.
        table_bytes = 3 + len({symbol >> 3 for symbol in codes}) + 2 * len(codes)
        data_bits = sum(count * codes.get(symbol, (0, 13))[1]
                        for symbol, count in enumerate(occurrences))
        last_length = codes.get(last_symbol, (0, 13))[1]
        # The reference decoder peeks eight bits even for a one-bit code.
        readable_bits = max(data_bits, data_bits - last_length + 8)
        return table_bytes + (readable_bits + 7) // 8, table_bytes * 8 + data_bits

    def compute_best_codes(self, occurrences, last_symbol):
        # As in the C approach, try dropping the rarest coded symbols.
        # This also accounts for the cost of storing the code table.
        symbols = sorted((symbol for symbol, count in enumerate(occurrences)
                          if count >= 3), key=lambda symbol: (occurrences[symbol], symbol))
        best_codes = {}
        best_size = self.encoded_size(best_codes, occurrences, last_symbol)

        for start in range(len(symbols)):
            lengths = self.compute_code_lengths(symbols[start:], occurrences)
            codes = self.compute_codes(lengths, occurrences)
            size = self.encoded_size(codes, occurrences, last_symbol)

            if size < best_size:
                best_codes = codes
                best_size = size

        return best_codes, best_size[0]

    def emit_code_table(self, codes):
        previous_pixel = -1

        for symbol in sorted(codes):
            pixel = symbol >> 3
            code, length = codes[symbol]

            if pixel != previous_pixel:
                self.write_byte(0x80 | pixel)
                previous_pixel = pixel
            self.write_byte(((symbol & 7) << 4) | length)
            self.write_byte(code)

        self.write_byte(0xFF)

    def compress(self, xor_mode=None):
        """
        Return a list of compressed bytes; errors propagate to the caller.

        xor_mode=None tries both modes and keeps the smaller (normal wins ties).
        False forces normal mode; True forces XOR mode.
        Input is never modified. Repeated calls reset output state.
        """
        self.reset_output()
        size = len(self.data_input)
        if size == 0 or size % 32:
            raise ValueError("Nemesis input must contain complete, nonempty 32-byte tiles.")
        if size // 32 > 0x7FFF:
            raise ValueError("Nemesis supports at most 32767 tiles.")
        if xor_mode is not None and type(xor_mode) is not bool:
            raise TypeError("xor_mode must be None, False, or True.")

        best = None
        for mode in ((False, True) if xor_mode is None else (xor_mode,)):
            runs, occurrences = self.find_runs(mode)
            codes, output_size = self.compute_best_codes(occurrences, runs[-1])
            if best is None or output_size < best[0]:
                best = output_size, mode, runs, codes

        output_size, self.xor_mode, runs, codes = best

        self.write_word((size // 32) | (0x8000 if self.xor_mode else 0))
        self.emit_code_table(codes)

        for symbol in runs:
            if symbol in codes:
                code, length = codes[symbol]
                self.write_bits(code, length)
            else:
                self.write_bits(self.INLINE_PREFIX, 6)
                self.write_bits(symbol & 7, 3)
                self.write_bits(symbol >> 3, 4)
        self.flush_bits()

        # Add at most one lookahead byte; it is not another decoded tile.
        if len(self.output) < output_size:
            self.write_byte(0)

        return self.output


# ========================
# Callers
# ========================
# This defines what gets imported if using 'from Editors import *'
__all__ = ["compress", "decompress"]

def compress(data, xor_mode=None):
    comp = NemesisComp(data)
    return comp.compress(xor_mode)

def decompress(data):
    decomp = NemesisDecomp(data)
    return decomp.decompress()
