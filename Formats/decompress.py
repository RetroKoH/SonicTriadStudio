# To-Do: I could probably combine the read/write functions with those in compress.py
class Decompress:
    """
    General decompression class
    """
    def __init__(self, data_input):
        self.data_input = data_input
        self.position = 0
        self.bit = 0
        self.output = []

    def set_input(self, data, position=0):
        """
        Set input data.

        Parameters:
            data - Input data
            position - Input data position
        """
        self.data_input = data
        self.position = position
        self.bit = 0

    def reset_bit(self):
        """
        Reset input data.
        """
        if self.bit > 0:
            self.bit = 0
            self.position += 1

    def read_byte(self, peek=False):
        """
        Read a single byte.

        Parameters:
            peek - Peek flag
        Returns:
            value - byte read
        """
        if not self.data_input:
            raise IndexError("No data to read byte from.")

        if self.position >= len(self.data_input):
            raise IndexError("Not enough data left to read byte from.")
        self.reset_bit()

        value = self.data_input[self.position]

        if not peek:
            self.position += 1

        return value

    def read_word(self, peek=False):
        """
        Read a word (2 bytes).

        Parameters:
            peek - Peek flag
        Returns:
            value - word read
        """
        if not self.data_input:
            raise IndexError("No data to read word from.")

        if (self.position + 2) > len(self.data_input):
            raise IndexError("Not enough data left to read word from.")

        self.reset_bit()

        value = ((self.data_input[self.position] << 8) |
                 self.data_input[self.position + 1])

        if not peek:
            self.position += 2

        return value

    def read_long(self, peek=False):
        """
        Read a longword (4 bytes).

        Parameters:
            peek - Peek flag
        Returns:
            value - longword read
        """
        if not self.data_input:
            raise IndexError("No data to read longword from.")

        if (self.position + 4) > len(self.data_input):
            raise IndexError("Not enough data left to read longword from.")
        self.reset_bit()

        value = ((self.data_input[self.position] << 24) |
                 (self.data_input[self.position + 1] << 16) |
                 (self.data_input[self.position + 2] << 8) |
                 self.data_input[self.position + 3])

        if not peek:
            self.position += 4

        return value

    def read_bits(self, bits, peek=False):
        """
        Read a given number of bits.

        Parameters:
            bits - Number of bits to read
            peek - Peek flag
        Returns:
            value - bit read
        """
        if not self.data_input:
            raise IndexError("No data to read bits from.")

        value = 0
        pos = self.position
        bit = self.bit
        for i in range(0, bits):
            if pos >= len(self.data_input):
                raise IndexError("Not enough data left to read bits from.")

            value = (value << 1) | ((self.data_input[pos] >> (7 - bit)) & 1)
            bit += 1
            if (bit >= 8):
                bit = 0
                pos += 1

        if not peek:
            self.position = pos
            self.bit = bit

        return value

    def write_byte(self, value):
        """
        Write a single byte.

        Parameters:
            value - value to write
        """
        self.output.append(value & 0xFF)

    def write_bytes(self, values):
        """
        Write a list of bytes.

        Parameters:
            value - values to write (list)
        """
        self.output.extend(values)

    def write_word(self, value):
        """
        Write a word (2 bytes).

        Parameters:
            value - value to write
        """
        self.write_byte(value >> 8)
        self.write_byte(value)

    def write_long(self, value):
        """
        Write a longword (4 bytes).

        Parameters:
            value - value to write
        """
        self.write_word(value >> 16)
        self.write_word(value)
