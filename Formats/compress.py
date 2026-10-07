# To-Do: I could probably combine the read/write functions with those in decompress.py
class Compress:
    """
    General compression class
    """
    def __init__(self, data_input):
        self.data_input = self.set_input(data_input)
        self.output = []
        self.bit_buffer = 0
        self.bit_count = 0

    @staticmethod
    def set_input(data):
        """
        Validate and set input data.
        """
        if isinstance(data, (int, str)):
            raise TypeError("Input must be bytes or an iterable of byte values.")

        return bytes(data)

    def reset_output(self):
        """
        Reset output variables.
        """
        self.output = []
        self.bit_buffer = 0
        self.bit_count = 0

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

    def write_bits(self, value, bits):
        """
        Pack and write a series of bits.

        Parameters:
            value - value to write
            bits - number of bits to pack
        """
        self.bit_buffer = (self.bit_buffer << bits) | value
        self.bit_count += bits

        while self.bit_count >= 8:
            self.bit_count -= 8
            self.write_byte(self.bit_buffer >> self.bit_count)

        self.bit_buffer &= (1 << self.bit_count) - 1

    def flush_bits(self):
        """
        Flush all bits.
        """
        if self.bit_count:
            self.write_byte(self.bit_buffer << (8 - self.bit_count))
            self.bit_buffer = 0
            self.bit_count = 0
