import json
from uuid import UUID, uuid4
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile

from PyQt6.QtCore import QObject, pyqtSignal


class Project(QObject):
    project_loaded = pyqtSignal()
    project_saved = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.data = None # active project data
        self.root_dir = None # project root directory
        self.json_path = None # project JSON path

    @staticmethod
    def new_asset_id():
        """
        Generate a unique ID for a new project asset.
        """
        return str(uuid4())

    @staticmethod
    def validate_data(data):
        """
        Validate project data without altering it.
        """
        if not isinstance(data, dict):
            raise ValueError("Project JSON must contain a dictionary.")

        seen_ids = set()

        # Check each section (Each editor has a section)
        for section in ("palettes", "sprites"):
            entries = data.get(section, {})

            if not isinstance(entries, dict):
                raise ValueError(f"Project '{section}' must contain a dictionary.")

            for asset_id, config in entries.items():
                if not isinstance(asset_id, str):
                    raise ValueError(f"Asset IDs in '{section}' must be strings.")

                try:
                    parsed_id = UUID(asset_id)
                except ValueError:
                    raise ValueError(f"Asset ID {asset_id} in '{section}' is not a valid UUID.") from None

                if str(parsed_id) != asset_id:
                    raise ValueError(f"UUID {asset_id!r} must use lowercase, hyphenated form.")

                if asset_id in seen_ids:
                    raise ValueError(f"Duplicate asset ID: {asset_id}.")

                # If valid, add to seen UUIDs
                seen_ids.add(asset_id)

                if not isinstance(config, dict):
                    raise ValueError(f"Asset {asset_id!r} must contain a dictionary.")

                # Get asset name
                name = config.get("name")

                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"Asset {asset_id!r} must have a nonblank name.")

                if section == "palettes":
                    palette_path = config.get("path")

                    if not isinstance(palette_path, str) or not palette_path.strip():
                        raise ValueError(f"Palette {name!r} must have a nonblank path.")

        if not isinstance(data.get("settings", {}), dict):
            raise ValueError("Project settings must be a dictionary.")

        rom_path = data.get("rom_path", "")

        if rom_path is not None and not isinstance(rom_path, str):
            raise ValueError("Project ROM path must be a path string.")

    @staticmethod
    def _json_object(pairs):
        """
        Read a JSON object without accepting duplicate keys.

        We need this because a JSON reader keeps only the last occurrence of a repeated key.
        Once that happens, the validator cannot detect that two entries originally shared the same UUID.
        """
        result = {}

        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key!r}.")

            result[key] = value

        return result

    @property
    def is_loaded(self):
        return self.data is not None

    def load(self, json_path):
        """
        Validate and load project data from JSON, committing only after success.

        Raises an exception if project data could not be loaded.
        """
        # Get absolute path
        project_path = Path(json_path).resolve()

        with open(project_path, "r", encoding="utf-8" ) as file:
            loaded_data = json.load(file, object_pairs_hook=self._json_object)

        # Validate project
        self.validate_data(loaded_data)

        # Commit after validation success
        self.data = loaded_data
        self.root_dir = project_path.parent
        self.json_path = project_path

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

        # Validate proposed project data
        proposed = deepcopy(proposed_data)
        self.validate_data(proposed)
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
        self.project_saved.emit()

    def save(self, proposed_data):
        """Prepare, write, and commit proposed project data."""
        prepared = self.prepare_save(proposed_data)
        self.save_prepared(prepared)
