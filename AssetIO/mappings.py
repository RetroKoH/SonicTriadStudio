# In the future, additional user-defined formats will be possible
# For that reason, this is stored outside of the loading functions
MAP_FORMATS = {
	1: {
		'header_size': 1,
		'piece_size': 5,
		'attr_bytes': 2,
		'x_bytes': 1
	},
	2: {
		'header_size': 2,
		'piece_size': 8,
		'attr_bytes': 4,
		'x_bytes': 2
	},
	3: {
		'header_size': 2,
		'piece_size': 6,
		'attr_bytes': 2,
		'x_bytes': 2
	}
}

def load_mappings(path, map_version=1):
    if path.suffix.lower() == ".asm":
        result = load_mappings_asm(path, map_version)
    else:
        result = load_mappings_bin(path, map_version)

    if not result[0]:
        raise ValueError("Mapping file contains no frames.")

    return result

def load_mappings_asm(path, map_version=1):
    contents = []

    # Get all content, removing comments & lead/trail whitespace
    with open(path, 'r') as f:
        for line in f:
            line = line.split(';', 1)[0].strip()

            if line:
                contents.append(line)

    # MapMacros check (Returned ASM command == mappingstableentry)
    if any(
        split_asm_line(line)[1].startswith('mappingstableentry')
        for line in contents
    ):
        # Jump to macro loading function
        return load_mappings_macro(contents)

    # Traditional ASM mapping files (Change this to use identical structure to macro version)
    map_label = None    # Get top-level map label
    frame_labels = []   # Get ordered frame labels from the pointer table

    # Get map frame attributes based on mapping version
    map_format = MAP_FORMATS[map_version]
    header_size = map_format['header_size']  # Number of bytes for the frame's piece count
    piece_size = map_format['piece_size']  # Number of bytes per piece for each frame

    # Get top-level map label (if it is in the file)
    if contents:
        first_label, _, _ = split_asm_line(contents[0])

        if first_label:
            map_label = first_label

    # Track the end of the pointer table so we can remove the header afterwards
    # It's far easier to just cut the header than to try indexing stuff early
    pointer_table_end = 0

    # Find frame pointers to get their labels
    for _i, line in enumerate(contents):
        defined_label, command, ptr_str = split_asm_line(line)

        # Once an already defined frame label is found, the pointer table is over
        if frame_labels and defined_label in frame_labels:
            break

        if command != 'dc.w':
            continue

        pointer_table_end = _i + 1  # Track end of pointer table

        # Split by comma in case multiple pointers are on a single line
        for ptr in ptr_str.split(','):
            ptr = ptr.strip()

            # For standard pointers formatted as: frame-base
            if '-' in ptr:
                frame_part, base_part = ptr.split('-', 1)

                # Append a frame label from the pointer
                label = frame_part.strip()
                if label:
                    frame_labels.append(label)

                # Fallback attempt to retrieve a top-level map label
                if not map_label:
                    map_label = base_part.strip()

            # If, for some reason, frame label pointers are not formatted as: frame-base
            else:
                label = ptr.strip()
                if label:
                    frame_labels.append(label)

    # Remove the header
    contents = contents[pointer_table_end:]

    # Now, index frame definitions
    frame_label_set = set(frame_labels)
    frame_starts = {}

    # Frame indexing
    for _i, line in enumerate(contents):
        defined_label, _, _ = split_asm_line(line)

        if defined_label in frame_label_set:
            # .setdefault indexes the defined label only if it hasn't be indexed already.
            # This preserves the definition if a malformed .asm file defines it twice.
            frame_starts.setdefault(defined_label, _i)

    # Used to recognize when collection reaches the next frame
    frame_start_indices = set(frame_starts.values())

    # Frame buffer
    frames = []

    # Locate each frame label and extract its data pieces
    for label in frame_labels:
        # Retrieve the previously indexed frame position
        start_idx = frame_starts.get(label)

        # If the referenced label wasn't found, raise error
        if start_idx is None:
            raise ValueError(f"Frame '{label}' is referenced but has no definition.")

        # If the label was found, begin extracting its frame data
        bytes_collected = []
        piece_count = None
        expected_bytes = None

        # Sprite piece data collection
        for _i in range(start_idx, len(contents)):
            line = contents[_i]

            # Stop when another indexed frame begins
            if _i != start_idx and _i in frame_start_indices:
                break

            # Get data line here in case frame_label and dc._ share the same line
            # (e.g.: M_Hog_Stand:   dc.b 2)
            _, command, piece = split_asm_line(line)

            # Ignore lines that aren't data declarations
            if not command.startswith('dc.'):
                continue

            # Process all dc._ types to support S2/S3 word alignment
            data_type = command[3:]  # b or w (l is also possible)

            # Handle invalid declaration types
            if data_type not in ('b', 'w', 'l'):
                raise ValueError(f"Frame '{label}' uses unsupported declaration " +
                    f"'{command}' in line: {line}"
                )

            # Look through each item in mapping piece data
            for _p in piece.split(','):
                _p = _p.strip()

                # if no data is present, continue onward
                if not _p:
                    continue

                try:
                    # Collect all bytes for this piece (determine hex or decimal)
                    val = parse_asm_number(_p)

                    if data_type == 'b':
                        bytes_collected.append(val & 0xFF)
                    elif data_type == 'w':
                        bytes_collected.extend([(val >> 8) & 0xFF, val & 0xFF])
                    elif data_type == 'l':
                        bytes_collected.extend([(val >> 24) & 0xFF, (val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF])

                # Reject unrecognized text
                except ValueError:
                    raise ValueError(f"Frame '{label}' contains an invalid value {_p!r} in line: {line}")

            # Set piece count and expected bytes from the very first byte(s) collected
            if piece_count is None and len(bytes_collected) >= header_size:
                piece_count = int.from_bytes(bytes(bytes_collected[:header_size]), byteorder='big')
                expected_bytes = header_size + piece_count * piece_size

            # Stop when we've collected the expected amount of bytes
            if expected_bytes is not None and len(bytes_collected) >= expected_bytes:
                break

        # Piece data collection finished. Now error-check and build frame
        # Error if there isn't frame data
        if piece_count is None:
            raise ValueError(f"Frame '{label}' has no readable piece count.")

        # Incomplete frame data
        if len(bytes_collected) < expected_bytes:
            raise ValueError(f"Frame '{label}' declares {piece_count} pieces, " +
                f"requiring {expected_bytes} bytes, but only {len(bytes_collected)} were found.")

        # Excess frame data
        if len(bytes_collected) > expected_bytes:
            raise ValueError(f"Frame '{label}' contains " +
                f"{len(bytes_collected) - expected_bytes} undeclared trailing byte(s).")

        # Construct mapping frame list
        frame_data = extract_frame_pieces(bytes_collected, header_size, piece_count, map_format)

        # Append to map frames data
        frames.append(frame_data)

    # Return mappings data
    return frames, frame_labels, map_label or "", False

def load_mappings_macro(contents):
    map_label = None    # Top-level map label
    frame_labels = []   # Ordered frame labels from the pointer table
    frame_starts = {}   # Dictionary: {frame_label: starting line index}

    # Run through contents to find labels
    for _i, line in enumerate(contents):
        defined_label, command, data = split_asm_line(line)

        if not command:
            continue

        # Find top-level map label
        if command == 'mappingstable' and defined_label:
            map_label = defined_label

        # Find frame pointers to get their labels
        elif command.startswith('mappingstableentry') and data:
            for entry in data.split(','):
                entry = entry.strip()
                if entry:
                    frame_labels.append(entry)

        # Frame indexing
        elif command == 'spriteheader' and defined_label:
            frame_starts[defined_label] = _i

    # With all labels found, create reverse lookup
    # {line number: frame label}
    frame_at_start = {
        start_idx: frame_label
        for frame_label, start_idx in frame_starts.items()
    }

    # if map_label == None, it will be user-specified in the editor

    # Frame buffer
    frames = []

    # Locate each frame label and extract its data pieces
    for label in frame_labels:
        # If this frame has no spriteHeader definition, reject
        if label not in frame_starts:
            raise ValueError(f"Frame '{label}' is referenced, but has no spriteHeader definition.")

        # Construct mapping frame list
        frame_data = []
        start_idx = frame_starts[label]

        # Start at the line AFTER the label and command
        for _i in range(start_idx + 1, len(contents)):
            line = contents[_i]

            # if another spriteHeader is found, this frame's missing an _End
            if frame_at_start.get(_i) is not None:
                raise ValueError(f"Frame '{label}' is missing its _End label:" +
                    f"{label}_End. Stopped at the next spriteHeader.")

            # Frame boundary check
            if line.split(None, 1)[0].rstrip(':') == label + '_End':
                break

            _, command, data = split_asm_line(line)

            # Skip non-piece lines
            if command != 'spritepiece':
                continue

            if not data:
                raise ValueError(f"Frame '{label}' has a spritePiece with no values.")

            # Get data directly from the values AFTER spritePiece
            try:
                values = [parse_asm_number(value) for value in data.split(',')]

            # If there is an erroneous value, reject
            except ValueError as error:
                raise ValueError(f"Frame '{label}' contains an invalid spritePiece value in line: {line} ({error}).")

            # If there's an invalid number of values, reject
            if len(values) != 9:
                raise ValueError(f"Frame '{label}' has a spritePiece {len(values)} values; Expected: 9. Line: {line}.")

            # Assign everything from values list, then perform validation checks
            x, y, width, height, tile, x_flip, y_flip, palette, priority = values

            # If map piece sizes are invalid, reject
            if not 1 <= width <= 4 or not 1 <= height <= 4:
                raise ValueError(f"Frame '{label}' has invalid dimensions " +
                    f"{width}x{height}; width and height must be 1–4.")

            # If flip flags have been given erroneous values, reject
            if x_flip not in (0, 1) or y_flip not in (0, 1):
                raise ValueError(f"Frame '{label}' has invalid flip flags. Flip flags must be 0 or 1.")

            # Reject invalid palette indices
            if not 0 <= palette <= 3:
                raise ValueError(f"Frame '{label}'  has invalid palette {palette}. Palette line index must be 0–3.")

            # Reject invalid priority flags
            if priority not in (0, 1):
                raise ValueError(f"Frame '{label}' has invalid priority {priority}. Priority flag must be 0 or 1.")

            # Append raw piece data (Includes label and actual data)
            frame_data.append({
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'tile': tile,
                'x_flip': x_flip,
                'y_flip': y_flip,
                'palette': palette,
                'priority': priority,
                'art_tile_2p': 0
            })

        # The final frame may reach EOF without encountering another spriteHeader
        else:
            raise ValueError(f"Frame '{label}' is missing its '{label}_End' label; reached the end of the file.")

        # Append to map frames data
        frames.append(frame_data)

    # Return mappings data
    return frames, frame_labels, map_label or "", True

def load_mappings_bin(path, map_version=1):
    # Store all bytes from the binary file in a list
    with open(path, "rb") as f:
        raw = f.read()

    # If this mapping file has no frame data, stop now
    if len(raw) < 2:
        raise ValueError("File is too short to contain a mapping pointer table.")

    # Generated labels in case we want to save to .ASM
    stem = path.stem.split(' ', 1)[0][:8]  # Create a top-level map label (Up to 8 char, stops at spaces)
    map_label = f"Map_{stem}"
    frame_labels = []  # Create ordered frame labels

    # Mappings begin with an array of word-length offsets for each frame.
    # Because the first mapping is expected immediately after this array,
    # the total number of frames is assumed to be the first offset div 2.
    first_offset = (raw[0] << 8) | raw[1]

    # Validation check
    if first_offset < 2 or first_offset % 2 or first_offset > len(raw):
        raise ValueError("Invalid mapping pointer-table size.")

    num_frames = first_offset // 2

    # Get map frame attributes based on mapping version
    map_format = MAP_FORMATS[map_version]
    header_size = map_format['header_size']  # Number of bytes for the frame's piece count
    piece_size = map_format['piece_size']  # Number of bytes per piece for each frame

    # Frame buffer
    frames = []

    for _i in range(num_frames):
        pointer_pos = _i * 2

        # Make sure both bytes of this pointer exist
        if pointer_pos + 1 >= len(raw):
            raise ValueError(f"Pointer table is truncated at frame index {_i}.")

        # Get word value directing to the next mapping frame
        offset = (raw[pointer_pos] << 8) | raw[pointer_pos + 1]

        # Get starting pointer of the next mapping frame
        start_ptr = offset + header_size

        # Reject offsets that do not contain a complete frame header
        if start_ptr > len(raw):
            raise ValueError(f"Frame {_i} points to offset ${offset:X}, " +
                "which does not contain a complete frame header.")

        # Read the piece count from the frame header
        piece_count = int.from_bytes(raw[offset:start_ptr], byteorder='big')

        # Get pointer for expected end of frame
        frame_end = start_ptr + piece_count * piece_size

        # Reject incomplete frames
        if frame_end > len(raw):
            available = len(raw) - start_ptr
            required = piece_count * piece_size

            raise ValueError(f"Frame {_i} declares {piece_count} pieces requiring " +
                f"{required} data bytes, but only {available} remain.")

        # Construct mapping frame list
        frame_data = extract_frame_pieces(raw, start_ptr, piece_count, map_format)

        # Append to map frames data
        frames.append(frame_data)

        # Add a generic frame counter label
        frame_labels.append(f"M_{stem}_Frame{_i}")

    # Return mappings data
    return frames, frame_labels, map_label or "", False

# Used by standard ASM and BIN loading
def extract_frame_pieces(data_array, start_ptr, piece_count, map_format):
    # Construct mapping frame list
    frame_data = []

    # Initialize frame piece pointer
    ptr = start_ptr

    # Get piece attributes from map format
    piece_size = map_format['piece_size']
    attr_bytes = map_format['attr_bytes']
    x_bytes = map_format['x_bytes']

    # Iterate through frame pieces
    for _i in range(piece_count):
        # Safety check for binary EOF
        if ptr + piece_size > len(data_array):
            raise ValueError("Mapping frame contains incomplete piece data.")

        # Y Offset (signed)
        y = data_array[ptr]
        if y > 127:
            y -= 256
        ptr += 1

        # Piece size
        size = data_array[ptr]
        width = ((size >> 2) & 3) + 1
        height = (size & 3) + 1
        ptr += 1

        # VDP attributes
        attributes = (data_array[ptr] << 8) | data_array[ptr + 1]

        # Break apart this word value
        # Sonic 2's 2P bytes get skipped
        tile = attributes & 0x7FF
        x_flip = (attributes >> 11) & 1
        y_flip = (attributes >> 12) & 1
        palette = (attributes >> 13) & 3
        priority = (attributes >> 15) & 1
        ptr += attr_bytes

        # X Offset (signed)
        x = int.from_bytes(
            bytes(data_array[ptr:ptr + x_bytes]),
            byteorder='big',
            signed=True
        )
        ptr += x_bytes

        # Append raw piece data
        frame_data.append({
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'tile': tile,
            'x_flip': x_flip,
            'y_flip': y_flip,
            'palette': palette,
            'priority': priority,
            'art_tile_2p': 0
        })

    # Return frame list
    return frame_data

# To-Do: These should be global ASM parsing functions
def split_asm_line(line):
    label = None
    clean_line = line.strip()   # is this needed (assuming lines are already stripped?)

    # Separate label from the rest of the line
    if ':' in clean_line:
        label, clean_line = clean_line.split(':', 1)
        label = label.strip()
        clean_line = clean_line.strip()

    # Separate command from data (split on whitespace)
    parts = clean_line.split(None, 1)

    # Return if the label is alone on this line
    if not parts:
        return label, '', ''

    command = parts[0].lower()
    data = parts[1].strip() if len(parts) == 2 else ''

    # Return all contents in this line, split apart
    return label, command, data

def parse_asm_number(value):
    value = value.strip()
    sign = 1

    # Check for sign operator, apply sign, and remove operator
    if value.startswith(('+', '-')):
        if value[0] == '-':
            sign = -1
        value = value[1:].strip()

    # Convert hex value
    if value.startswith('$'):
        value = int(value[1:], 16)
    # Convert binary value
    elif value.startswith('%'):
        value = int(value[1:], 2)
    else:
        value = int(value)

    # Return signed int
    return sign * value

