from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from PyQt6.QtGui import QColor

from AssetIO.art import decode_art
from AssetIO.mappings import load_mappings, load_dplcs
from AssetIO.palettes import decode_palette
from constants import PALETTE_LINES, PALLINE_COLORS, PALETTE_MAXCOLORS, VRAM_MAXTILES


class ArtBuffer(NamedTuple):
    """
    Art tile buffer

    Tile pattern art is loaded from binary files into these buffers.
    Art from these buffers get loaded into dedicated VRAM storage to be used for sprite building.
    """
    path: Path | None
    compression: str
    offset: int
    count: int
    tiles: list


class FrameBuffer(NamedTuple):
    """
    General container for mapping and DPLC frame data.

    They use the same container structure, so only one class is needed for both.
    """
    path: Path | None
    frames: list
    frame_labels: list
    label: str
    use_macros: bool


class PaletteBuffer(NamedTuple):
    colors: list
    layout: tuple
    new_paths: set


@dataclass
class LoadedSpriteBuild:
    """Independent loaded buffers; no editor state or implicit file writes.

    After editing art or its placement, call refresh_vram(). Frame preparation
    returns a new slot dictionary; treat its static tile pixels as read-only.
    Use SpriteRenderer with frame_vram(), palette.colors, mappings.frames,
    base_tile and base_palette to render any frame.
    """

    art: list
    palette: PaletteBuffer
    mappings: FrameBuffer
    dplcs: FrameBuffer
    map_format: int
    base_tile: int
    base_palette: int
    dplcs_enabled: bool
    static_vram_tiles: dict = field(init=False, repr=False)

    def __post_init__(self):
        self.refresh_vram()

    def refresh_vram(self):
        self.static_vram_tiles = build_static_vram(
            self.art, dplcs_enabled=self.dplcs_enabled)

    def frame_vram(self, frame_index):
        """Return (tiles, diagnostic) for the requested mapping frame."""
        source = self.art[0] if self.art else None
        return prepare_frame_vram(
            self.static_vram_tiles,
            source.tiles if source is not None else [],
            self.dplcs.frames if self.dplcs.path is not None else None,
            frame_index,
            dplcs_enabled=self.dplcs_enabled,
            base_tile=self.base_tile,
            source_compression=source.compression if source else None,
        )


def palette_file_layout(entries, resolve_path):
    """
    Get the configured palette layout in table order.

    Returns:
        Tuple: (absolute Path or None, line count) for each entry.
        (Note: Blank paths reserve their configured palette lines.)
    Formerly Sprite Editor's palette_get_file_layout().
    """
    layout = []
    seen_paths = set()
    total_lines = 0

    for entry in entries:
        num_lines = entry.get("length", 1)

        if not 1 <= num_lines <= PALETTE_LINES:
            raise ValueError("Palette entries must fit within four lines.")

        total_lines += num_lines

        if total_lines > PALETTE_LINES:
            raise ValueError("Palette entries must fit within four lines.")

        # Resolve relative paths against the project root
        path = resolve_path(entry.get("path", "").strip())

        if path is not None:
            # Prevents writing to the same palette file twice from separate entries
            if path in seen_paths:
                raise ValueError(f"Palette file listed more than once: {path}")

            seen_paths.add(path)

        # Preserve row order and reserved lines
        layout.append((path, num_lines))

    # Includes blank entries as they reserve palette lines
    return tuple(layout)


def load_palette_buffers(entries, resolve_path, *, new_paths=()):
    """
    Load four palette lines.
    Blank entries reserve lines; said lines remain black.
    Existing files must contain at least their configured number of colors.

    File-loading and processing code taken from Sprite Editor's palette_prepare_load().
    """
    layout = palette_file_layout(entries, resolve_path) # (path, line count)
    colors = [QColor(0, 0, 0) for _ in range(PALETTE_MAXCOLORS)] # Temp buffer of 64 colors
    remaining_new_paths = set(new_paths) # editor.palette_new_paths.copy()
    current_index = 0 # Index to load the next color into

    for path, num_lines in layout:
        # Number of colors to load based on number of lines in the entry
        num_colors = num_lines * PALLINE_COLORS

        if path is not None:
            try:
                with open(path, "rb") as f:
                    data = f.read(num_colors * 2) # each color is 2 bytes

            except FileNotFoundError:
                # New, unsaved palettes remain black
                if path not in remaining_new_paths:
                    raise

            else:
                # Reject files shorter than their configured line count
                if len(data) != num_colors * 2:
                    raise ValueError(
                        f"{path.name}: expected {num_colors * 2} bytes, but read {len(data)}.")

                colors[current_index:current_index + num_colors] = decode_palette(data)

                # For file association management
                remaining_new_paths.discard(path)

        # Blank paths still reserve their palette lines
        current_index += num_colors

    return PaletteBuffer(colors, layout, remaining_new_paths)


def load_art_buffers(entries, resolve_path, *, dplcs_enabled=False):
    """
    Read art entries into independent buffers, preserving empty row slots.

    File-loading and processing code taken from Sprite Editor's art_prepare_load().
    """
    buffers = []
    seen_paths = set()

    for row_index, entry in enumerate(entries):
        # Resolve relative paths against the project directory
        path = resolve_path(entry.get("path", "").strip())

        # Get art data from entry fields
        compression = entry.get("compression", "Uncompressed")
        offset, count = entry.get("offset", 0), entry.get("count", 0)

        if type(offset) is not int or not offset < VRAM_MAXTILES:
            raise ValueError("Art offset must be a VRAM tile index from 0 to 2047.")

        if type(count) is not int or not count <= VRAM_MAXTILES:
            raise ValueError("Art count must be from 0 to 2048 (0 means all tiles).")

        tiles = []

        if path is not None:
            try:
                # Reject duplicate file assignments
                if path in seen_paths:
                    raise ValueError("Art file is listed more than once.")

                seen_paths.add(path)
                raw_data = path.read_bytes()

                # DPLCs read directly from uncompressed source art in buffer 1
                if row_index == 0 and dplcs_enabled and compression != "Uncompressed":
                    raise ValueError("DPLCs require uncompressed art in buffer 1. "
                                     "Choose Uncompressed and load an uncompressed art file.")

                # Unpack tiles and load into buffer storage
                tiles = decode_art(raw_data, compression)

            except Exception as e:
                raise ValueError(f"Could not load art file {path.name}:\n{e}") from e

        buffers.append(ArtBuffer(path, compression, offset, count, tiles))

    # Return all art buffers (Up to 3)
    return buffers


def load_mapping_buffer(path_value, map_format, resolve_path):
    """
    Read mappings, returning an empty buffer for an unassigned path.

    File-loading and processing code taken from Sprite Editor's mapping_prepare_load().
    """
    # Resolve relative path against the project directory
    path = resolve_path(path_value.strip())

    # For unconfigured mappings, use an empty buffer
    if path is None:
        return FrameBuffer(None, [], [], "", False)

    return FrameBuffer(path, *load_mappings(path, map_format))


def load_dplc_buffer(path_value, map_format, resolve_path, *, enabled=True):
    """
    Read DPLCs only when enabled, independently of whether art is loaded.

    File-loading and processing code taken from Sprite Editor's dplc_prepare_load().
    """
    # Stop now if DPLC's are not enabled
    if not enabled:
        return FrameBuffer(None, [], [], "", False)

    # Resolve relative path against the project directory
    path = resolve_path(path_value.strip())

    # For unconfigured mappings, use an empty buffer
    if path is None:
        return FrameBuffer(None, [], [], "", False)

    return FrameBuffer(path, *load_dplcs(path, map_format))


def load_sprite_build(config, resolve_path, *, new_palette_paths=()):
    """
    Loads a full configuration for non-Sprite Editors (e.g. Animation Editor).

    Example:
        build = load_sprite_build(project.get_asset(sprite_id), project.resolve_asset_path)
        tiles, status = build.frame_vram(frame_index)
        renderer.prepare(tiles, build.palette.colors)
        image = renderer.render_frame(build.mappings.frames[frame_index],
            base_tile=build.base_tile, base_palette=build.base_palette)
    """
    map_format = config.get("format", 1)
    mappings = config.get("mappings") or {}

    if isinstance(mappings, str):
        mappings = {"path": mappings}

    dplcs = config.get("dplcs") or {}
    dplcs_enabled = bool(dplcs.get("enabled", False))

    base_tile = config.get("vram_index", 0)
    base_palette = config.get("palette_line", 0)

    if type(base_tile) is not int or not 0 <= base_tile < VRAM_MAXTILES:
        raise ValueError("Base VRAM tile index must be from 0 to 2047.")
    if type(base_palette) is not int or not 0 <= base_palette < PALETTE_LINES:
        raise ValueError("Base palette line must be from 0 to 3.")

    return LoadedSpriteBuild(
        art=load_art_buffers(config.get("art", []), resolve_path, dplcs_enabled=dplcs_enabled),
        palette=load_palette_buffers(config.get("palettes", []), resolve_path, new_paths=new_palette_paths),
        mappings=load_mapping_buffer(mappings.get("path", ""), map_format, resolve_path),
        dplcs=load_dplc_buffer(dplcs.get("path", ""), map_format, resolve_path, enabled=dplcs_enabled),
        map_format=map_format, base_tile=base_tile, base_palette=base_palette, dplcs_enabled=dplcs_enabled)


def build_static_vram(art_buffers, *, dplcs_enabled=False):
    """
    Upload art in row order; later rows win where uploads overlap.
    A zero count uploads all available tiles, clipped at the end of VRAM.

    Buffer processing code taken from Sprite Editor's art_refresh_vram().
    """
    # Start with a clear static buffer
    tiles = {}

    for row_index, buffer in enumerate(art_buffers):
        # Buffer 1 is dynamic if DPLCs are enabled; If dynamic, skip
        if dplcs_enabled and row_index == 0:
            continue # The complete first buffer is source art, not a static upload

        # Copy from source to static buffer
        start = buffer.offset
        if not 0 <= start < VRAM_MAXTILES:
            raise ValueError("Art offset must be a VRAM tile index from 0 to 2047.")

        count = buffer.count
        if not 0 <= count <= VRAM_MAXTILES:
            raise ValueError("Art count must be from 0 to 2048 (0 means all tiles).")

        # If count == 0, load all tiles (Up to the end of VRAM)
        upload_count = min(count or len(buffer.tiles), len(buffer.tiles), VRAM_MAXTILES - start)
        for index in range(upload_count):
            tiles[start + index] = buffer.tiles[index].copy()

    # Return static buffer to be loaded to VRAM
    return tiles


def prepare_frame_vram(static_tiles, source_tiles, dplc_frames, frame_index, *,
                       dplcs_enabled=False, base_tile=0, source_compression="Uncompressed"):
    """
    Return (tiles, diagnostic), uploading the requested frame's DPLC cues.

    Code migrated from Sprite Editor's dplc_get_frame_vram()
    """
    tiles = static_tiles.copy()

    # Stop now if DPLC's are not enabled
    if not dplcs_enabled:
        return tiles, ""

    # DPLC load check
    if dplc_frames is None:
        return tiles, "Load a DPLC file to populate frame VRAM."

    if not 0 <= frame_index < len(dplc_frames):
        return tiles, f"No DPLC frame exists for mapping frame {frame_index}."

    if not source_tiles:
        return tiles, "Waiting for uncompressed art in buffer 1."

    if source_compression != "Uncompressed":
        return tiles, "DPLCs require buffer 1 to be loaded from uncompressed art."

    if not 0 <= base_tile < VRAM_MAXTILES:
        raise ValueError("Base VRAM tile index must be from 0 to 2047.")

    destination = base_tile
    status = ""

    for cue in dplc_frames[frame_index]:
        source_start, count = cue["tile"], cue["count"]

        # Stop if this entry starts AFTER the source buffer
        if source_start >= len(source_tiles):
            status = (f"DPLC frame {frame_index} requests source tiles "
                      f"starting at tile offset ${source_start:X}, "
                      "which is AFTER the end of the source buffer. "
                      "DPLC loading stopped prematurely.")
            break

        # Load only the tiles available in the source and destination
        available_count = min(count, len(source_tiles) - source_start, VRAM_MAXTILES - destination)

        for index in range(source_start, source_start + available_count):
            # Copy tiles from buffer 1 to VRAM
            tiles[destination] = source_tiles[index].copy()
            destination += 1

        # An incomplete entry ends loading for this frame
        if available_count < count:
            break

    return tiles, status
