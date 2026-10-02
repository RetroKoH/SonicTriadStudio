import json
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal


class Project(QObject):
    project_loaded = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.data = None # active project data
        self.root_dir = None # project root directory
        self.json_path = None # project JSON path

    def load(self, json_path):
        """
        Validates and loads project data from json file.

        Raises an exception if project data could not be loaded.
        """
        # Get absolute path
        path = Path(json_path).resolve()

        with open(path, "r", encoding="utf-8" ) as file:
            loaded_data = json.load(file)

        if not isinstance(loaded_data, dict):
            raise ValueError("Project JSON must contain a dictionary.")

        # Get subsections of data
        palettes = loaded_data.get("palettes", [])
        sprites = loaded_data.get("sprites", {})
        settings = loaded_data.get("settings", {})
        rom_path = loaded_data.get("rom_path", "")

        if not isinstance(palettes, list) or any(
                not isinstance(path, str)
                or not path for path in palettes
        ):
            raise ValueError("Project palettes must be a list of nonblank path strings.")

        if not isinstance(sprites, dict) or any(
            not isinstance(build, dict)
            for build in sprites.values()
        ):
            raise ValueError("Project sprites must contain build dictionaries.")

        if not isinstance(settings, dict):
            raise ValueError("Project settings must be a dictionary.")

        if rom_path is not None and not isinstance(rom_path, str):
            raise ValueError("Project ROM path must be a path string.")

        # Commit after validation success
        self.data = loaded_data
        self.root_dir = path.parent
        self.json_path = path

        # Signal that a new project is active
        self.project_loaded.emit()
