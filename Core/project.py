import json
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile

from PyQt6.QtCore import QObject, pyqtSignal


class Project(QObject):
    project_loaded = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.data = None # active project data
        self.root_dir = None # project root directory
        self.json_path = None # project JSON path

    @property
    def is_loaded(self):
        return self.data is not None

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

    def resolve_asset_path(self, path_value):
        """
        Return an absolute Path.

        Relative paths use the active project root when available.
        Blank paths return None.
        """
        if not path_value:
            return None

        path = Path(path_value)

        if self.root_dir is not None and not path.is_absolute():
            path = self.root_dir / path

        return path.resolve()

    def store_asset_path(self, path_value):
        """
        Return a path string suitable for project JSON.

        Prefer paths relative to the project root.
        Blank paths return an empty string.
        """
        path = self.resolve_asset_path(path_value)

        if path is None:
            return ""

        if self.root_dir is not None:
            try:
                return str(path.relative_to(self.root_dir))
            except ValueError:
                pass

        return str(path)

    def snapshot(self):
        """Return an independent copy of the active project data."""
        if not self.is_loaded:
            raise ValueError("No project is loaded.")

        return deepcopy(self.data)

    def prepare_save(self, proposed_data):
        """
        Validate and serialize proposed project data without writing it.

        Returns:
            (destination, proposed_data_copy, JSON text)
        """
        if not self.is_loaded:
            raise ValueError("No project is loaded.")

        if self.json_path is None:
            raise ValueError("The project has no JSON file path.")

        path = self.json_path

        if path.is_dir():
            raise IsADirectoryError(
                f"Project destination is a directory: {path}"
            )

        if not path.parent.is_dir():
            raise FileNotFoundError(
                f"Project directory does not exist: {path.parent}"
            )

        if not isinstance(proposed_data, dict):
            raise ValueError("Project data must be a dictionary.")

        proposed = deepcopy(proposed_data)
        json_text = json.dumps(proposed, indent=2)

        return path, proposed, json_text

    def save_prepared(self, prepared):
        """
        Write prepared JSON, then commit the saved project data.

        Raises an exception on failure.
        """
        path, proposed, json_text = prepared

        if path != self.json_path:
            raise ValueError(
                "The active project destination changed after preparation."
            )

        temp_path = None

        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                suffix=".tmp",
                delete=False,
            ) as file:
                temp_path = Path(file.name)
                file.write(json_text)

            # Replace the destination only after the temporary file closes
            temp_path.replace(path)
            temp_path = None

        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

        # Commit only after the file replacement succeeds
        self.data = proposed

    def save(self, proposed_data):
        """Prepare, write, and commit proposed project data."""
        prepared = self.prepare_save(proposed_data)
        self.save_prepared(prepared)
