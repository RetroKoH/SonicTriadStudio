from .palettes import PaletteEditor
from .sprites import SpriteEditor
from .animations import AnimationEditor
from .levels import LevelEditor
from .objdef import ObjectDefEditor
from .tilemaps import TilemapEditor
from .specialstage import SpecStageEditor

# This defines what gets imported if using 'from Editors import *'
__all__ = [
    "PaletteEditor",
    "SpriteEditor",
    "AnimationEditor",
    "LevelEditor",
    "ObjectDefEditor",
    "TilemapEditor",
    "SpecStageEditor"
]