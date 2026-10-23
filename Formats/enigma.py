from Formats.decompress import Decompress
from Formats.compress import Compress


class EnigmaDecomp(Decompress):
    """
    Decompress an Enigma-encoded file.

    Credit: Devon
    """

    def __init__(self, data_input):
        super().__init__(data_input)
        self.tile_base = 0
        self.tile_bits = 0
        self.tile_flags = 0

    def get_inline(self):
        """
        Read an inline tile ID and its enabled flags.
        """
        tile = self.tile_base

        if (self.tile_flags & 0x10) != 0:
            if self.read_bits(1) == 1:
                tile |= 0x8000

        if (self.tile_flags & 8) != 0:
            if self.read_bits(1) == 1:
                tile += 0x4000

        if (self.tile_flags & 4) != 0:
            if self.read_bits(1) == 1:
                tile += 0x2000

        if (self.tile_flags & 2) != 0:
            if self.read_bits(1) == 1:
                tile |= 0x1000

        if (self.tile_flags & 1) != 0:
            if self.read_bits(1) == 1:
                tile |= 0x800

        return tile + self.read_bits(self.tile_bits)

    def decompress(self, tile_base=0):
        try:
            self.output = []

            self.tile_base = tile_base
            self.tile_bits = self.read_byte()
            self.tile_flags = self.read_byte()
            tile_inc = self.read_word() + tile_base
            tile_static = self.read_word() + tile_base

            while True:
                if self.read_bits(1) == 0:
                    mode = self.read_bits(1)
                    length = self.read_bits(4) + 1

                    for i in range(0, length):
                        if mode == 0:
                            self.write_word(tile_inc)
                            tile_inc += 1
                        else:
                            self.write_word(tile_static)
                else:
                    mode = self.read_bits(2)
                    length = self.read_bits(4) + 1

                    if mode < 3:
                        inline = self.get_inline()
                        for i in range(0, length):
                            self.write_word(inline)
                            if mode == 1:
                                inline += 1
                            elif mode == 2:
                                inline -= 1
                    else:
                        if length == 0x10:
                            return self.output
                        for i in range(0, length):
                            self.write_word(self.get_inline())

        except Exception as e:
            print(e)
            return None

    def decompress_data(self, data, tile_base=0, position=0):
        """
        Set input data and decode an Enigma stream at the given offset.
        """
        self.set_input(data, position)
        return self.decompress(tile_base)


class EnigmaComp(Compress):
    """Compress a file in the Enigma format (not implemented yet)."""

    def compress(self):
        pass


# ========================
# Callers
# ========================
__all__ = ["compress", "decompress"]


def compress(data, xor_mode=None):
    comp = EnigmaComp(data)
    # return comp.compress()


def decompress(data, tile_base=0):
    """Decode Enigma bytes, optionally applying a base tile ID/flags."""
    decomp = EnigmaDecomp(data)
    return decomp.decompress(tile_base)
