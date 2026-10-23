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

    Credit: Clownacy (ClownLZSS)
    Reference: https://github.com/Clownacy/clownlzss
    Graph: compressors/clownlzss.c; format/costs: compressors/kosinski.h.
    Descriptor writer: bitfield.h. Costs exclude unused descriptor padding.
    """
    # Per FindOptimalMatches()
    MAX_SEARCH_DISTANCE = 0x2000
    MAX_MATCH_LENGTH = 0x100
    LITERAL_COST = 1 + 8

    @staticmethod
    def get_match_cost(distance, length):
        """
        ClownLZSS Kosinski::GetMatchCost()
        """
        if 2 <= length <= 5 and distance <= 0x100:
            return 2 + 2 + 8
        elif 3 <= length <= 9:
            return 2 + 16
        elif length >= 3:
            return 2 + 16 + 8

        # 0 means unencodable
        return 0

    def find_matches(self):
        """
        Return (position, length, distance) tuples.
        [See: See clownlzss.c -> FindOptimalMatches()]
        """
        data = self.data_input
        total_values = len(data)
        get_match_cost = self.get_match_cost

        # Initialize the string list nodes
        # next[] and list heads; groups by two bytes instead of one
        older_sources = [-1] * total_values
        source_heads = {}
        for position in range(total_values - 1):
            key = (data[position] << 8) | data[position + 1]
            older_sources[position] = source_heads.get(key, -1)
            source_heads[key] = position

        # These correspond to fields in Clownacy’s node_meta_array
        node_costs = [total_values * self.LITERAL_COST + 1] * (total_values + 1)
        node_costs[0] = 0
        previous_nodes = [0] * (total_values + 1)  # previous_node_index
        match_distances = [0] * (total_values + 1)

        # No explicit zero-check needed. This loop will not start without values
        # Advance through the data one step at a time
        for position in range(total_values):
            cost = node_costs[position]
            limit = min(self.MAX_MATCH_LENGTH, total_values - position)
            window_start = max(0, position - self.MAX_SEARCH_DISTANCE)
            source = older_sources[position]
            longest = 1
            prefix = data[position:position + 2]

            # This corresponds to Clownacy’s inner loop over match_string
            while source >= window_start:
                distance = position - source

                if data.startswith(prefix, source):
                    # Binary search replaces C's byte-by-byte j loop
                    low = longest + 1
                    high = limit

                    while low < high:
                        middle = (low + high + 1) // 2
                        if data.startswith(data[position:position + middle], source):
                            low = middle
                        else:
                            high = middle - 1

                    length = low

                    # Evaluate each j + 1 length through GetMatchCost()
                    for count in range(longest + 1, length + 1):
                        match_cost = get_match_cost(distance, count)
                        if match_cost == 0:
                            continue

                        # Update the cheaper edge in node_meta_array[end]
                        end = position + count
                        new_cost = cost + match_cost
                        if new_cost < node_costs[end]:
                            node_costs[end] = new_cost
                            previous_nodes[end] = position
                            match_distances[end] = distance

                    # Farther sources cannot improve covered lengths
                    longest = length
                    if longest == limit:
                        break
                    prefix = data[position:position + longest + 1]

                # next[match_string]
                source = older_sources[source]

            # literal edge after match search; >= makes literals win ties
            if node_costs[position + 1] >= cost + self.LITERAL_COST:
                node_costs[position + 1] = cost + self.LITERAL_COST
                previous_nodes[position + 1] = position
                match_distances[position + 1] = 0

        # reverse the chosen edges, then produce the matches array
        matches = []
        end = total_values

        while end:
            position = previous_nodes[end]
            matches.append((position, end - position, match_distances[end]))
            end = position

        matches.reverse()
        return matches

    def begin_descriptor(self):
        """
        ClownLZSS DescriptorFieldWriter::Begin(): reserve two bytes.
        """
        self.descriptor_position = len(self.output)
        self.descriptor_bit = 0
        self.write_bytes((0, 0))

    def write_descriptor_bit(self, value):
        """
        ClownLZSS WriterBase::Push(): write LSB-first descriptor bits.
        """
        position = self.descriptor_position + self.descriptor_bit // 8
        self.output[position] |= value << (self.descriptor_bit % 8)
        self.descriptor_bit += 1

        # C: WriteWhen::AfterPush reserves the next descriptor here.
        if self.descriptor_bit == 16:
            self.begin_descriptor()

    def write_match(self, distance, length):
        """The three copy branches in ClownLZSS Kosinski::Compress()."""
        offset = -distance

        if 2 <= length <= 5 and distance <= 0x100:
            # C: short copy (four descriptor bits, one payload byte).
            self.write_descriptor_bit(0)
            self.write_descriptor_bit(0)
            self.write_descriptor_bit(((length - 2) >> 1) & 1)
            self.write_descriptor_bit((length - 2) & 1)
            self.write_byte(offset)
        elif 3 <= length <= 9:
            # C: normal copy (two descriptor bits, two payload bytes).
            self.write_descriptor_bit(0)
            self.write_descriptor_bit(1)
            self.write_byte(offset)
            self.write_byte(((offset >> 5) & 0xF8) | (length - 2))
        else:
            # C: extended copy (two descriptor bits, three payload bytes).
            self.write_descriptor_bit(0)
            self.write_descriptor_bit(1)
            self.write_byte(offset)
            self.write_byte((offset >> 5) & 0xF8)
            self.write_byte(length - 1)

    def compress(self):
        """
        Return compressed byte values; errors propagate to the caller.

        Accept arbitrary byte lengths, including empty input. Input is never
        modified, and repeated calls reset all output and descriptor state.
        """
        self.reset_output()

        # Produce a series of LZSS compression matches
        matches = self.find_matches()  # FindOptimalMatches().
        self.begin_descriptor()  # DescriptorFieldWriter construction.

        # Iterate over matches in Kosinski::Compress()
        for position, length, distance in matches:
            if distance == 0:
                # CLOWNLZSS_MATCH_IS_LITERAL(match)
                self.write_descriptor_bit(1)
                self.write_byte(self.data_input[position])
            else:
                self.write_match(distance, length)

        # End marker, including the same unused offset bytes
        self.write_descriptor_bit(0)
        self.write_descriptor_bit(1)
        self.write_bytes((0x00, 0xF0, 0x00))
        return self.output


class KosinskiModComp(Compress):
    pass


# ========================
# Callers
# ========================
# This defines what gets imported if using 'from Editors import *'
__all__ = ["compress", "mod_compress", "decompress", "mod_decompress"]

def compress(data):
    comp = KosinskiComp(data)
    return comp.compress()

def mod_compress(data):
    return
    #comp = KosinskiModComp(data)
    #return comp.compress()

def decompress(data):
    decomp = KosinskiDecomp(data)
    return decomp.decompress()

def mod_decompress(data):
    decomp = KosinskiModDecomp(data)
    return decomp.decompress()
