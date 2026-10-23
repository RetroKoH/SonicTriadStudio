"""
Kosinski and Moduled Kosinski
"""

from Formats.decompress import Decompress
from Formats.compress import Compress

class KosinskiDecomp(Decompress):
    """
    Decompress a Kosinski-encoded file.

    Credit: Devon
    """
    def __init__(self, data_input):
        super().__init__(data_input)
        self.descriptor = 0
        self.descriptor_bit = 0

    def reset_descriptor(self):
        """
        Read the next little-endian, 16-bit descriptor.
        """
        self.descriptor = self.read_byte() | (self.read_byte() << 8)
        self.descriptor_bit = 0

    def read_descriptor_bit(self):
        """
        Read descriptor bits from least significant to most significant.
        """
        value = (self.descriptor >> self.descriptor_bit) & 1
        self.descriptor_bit += 1

        # Reset every 16 bits (in little-endian order)
        if self.descriptor_bit >= 16:
            self.reset_descriptor()

        return value

    def decompress(self):
        try:
            self.output = []
            self.reset_descriptor()

            while True:
                if self.read_descriptor_bit() == 0:
                    if self.read_descriptor_bit() == 0:
                        count = ((self.read_descriptor_bit() << 1) | self.read_descriptor_bit()) + 2
                        offset = self.read_byte() - 0x100

                    else:
                        low = self.read_byte()
                        high = self.read_byte()
                        offset = (((high & 0xF8) - 0x100) << 5) + low
                        count = (high & 7) + 2
                        if count == 2:
                            count = self.read_byte() + 1
                            if count == 1:
                                return self.output
                            elif count == 2:
                                continue

                    for i in range(0, count):
                        self.write_byte(self.output[len(self.output) + offset])
                else:
                    value = self.read_byte()
                    self.write_byte(value)

        except Exception as e:
            print(e)
            return None

    def decompress_data(self, data, position=0):
        """
        Decode a stream at an input offset
        (This will be used by Moduled Kosinski)
        """
        self.set_input(data, position)
        return self.decompress()


class KosinskiModDecomp(Decompress):
    def __init__(self, data_input):
        super().__init__(data_input)
        self.kosinski = None

    def decompress(self):
        try:
            self.output = []
            self.kosinski = KosinskiDecomp(self.data_input)

            size = self.read_word()
            while size > 0:
                self.write_bytes(self.kosinski.decompress_data(self.data_input, self.position))
                self.position = self.kosinski.position + ((2 - self.kosinski.position) & 0xF)
                size -= 0x1000
            return self.output

        except Exception as e:
            print(e)
            return None


class KosinskiComp(Compress):
    """
    Compress a file in the Kosinski format.

    Not ready yet.
    """
    def compress(self):
        pass


class KosinskiModComp(Compress):
    pass


# ========================
# Callers
# ========================
# This defines what gets imported if using 'from Editors import *'
__all__ = ["compress", "mod_compress", "decompress", "mod_decompress"]

def compress(data, xor_mode=None):
    return
    #comp = KosinskiComp(data)
    #return comp.compress()

def mod_compress(data, xor_mode=None):
    return
    #comp = KosinskiModComp(data)
    #return comp.compress()

def decompress(data):
    decomp = KosinskiDecomp(data)
    return decomp.decompress()

def mod_decompress(data):
    decomp = KosinskiModDecomp(data)
    return decomp.decompress()
