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

        self.asset_index = {} # In-memory asset lookup

    @staticmethod
    def new_asset_id():
        """
        Generate a unique ID for a new project asset.
        """
        return str(uuid4())

    @staticmethod
    def validate_data(data):
        """
        Validate project data and return asset index.
        """
        if not isinstance(data, dict):
            raise ValueError("Project JSON must contain a dictionary.")

        if any(key in data for key in ("palettes", "sprites", "asset_tree")):
            raise ValueError("This project must be converted to the nested assets schema.")

        asset_index = {}

        def check_entries(entries):
            if not isinstance(entries, list):
                raise ValueError("Assets and folder children must be lists.")

            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("Each asset or folder must be a dictionary.")

                asset_id = entry.get("id")

                if not isinstance(asset_id, str):
                    raise ValueError("Each asset or folder must have a UUID.")

                try:
                    parsed_id = UUID(asset_id)
                except ValueError:
                    raise ValueError(f"Invalid asset UUID: {asset_id!r}") from None

                if str(parsed_id) != asset_id:
                    raise ValueError(f"UUID {asset_id!r} must use lowercase, hyphenated form.")

                if asset_id in asset_index:
                    raise ValueError(f"Duplicate asset UUID: {asset_id}")

                name = entry.get("name")

                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"Entry {asset_id!r} must have a nonblank name.")

                asset_type = entry.get("type")

                if asset_type not in ("folder", "palette", "sprite"):
                    raise ValueError(f"Entry {name!r} has an unsupported type: {asset_type!r}")

                asset_index[asset_id] = entry

                if asset_type == "folder":
                    check_entries(entry.get("children"))

                else:
                    if "children" in entry:
                        raise ValueError("Only folders may contain children.")

                    if asset_type == "palette":
                        palette_path = entry.get("path")

                        if (not isinstance(palette_path, str) or not palette_path.strip()):
                            raise ValueError(f"Palette {name!r} must have a nonblank path.")

        # Check for assets
        check_entries(data.get("assets", []))

        if not isinstance(data.get("settings", {}), dict):
            raise ValueError("Project settings must be a dictionary.")

        rom_path = data.get("rom_path", "")

        if rom_path is not None and not isinstance(rom_path, str):
            raise ValueError("Project ROM path must be a path string.")

        return asset_index

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

        # Validate project and get asset index
        asset_index = self.validate_data(loaded_data)

        # Commit after validation success
        self.data = loaded_data
        self.asset_index = asset_index
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
            raise ValueError("The active project destination changed after preparation.")

        asset_index = self.validate_data(proposed)

        temp_path = None

        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as file:
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
        self.asset_index = asset_index
        self.project_saved.emit()

    def save(self, proposed_data):
        """Prepare, write, and commit proposed project data."""
        prepared = self.prepare_save(proposed_data)
        self.save_prepared(prepared)

    @staticmethod
    def find_asset_location(entries, asset_id):
        """
        Finds the list containing an entry, and its position within that list.

        Return the containing list, and index for a given UUID.
        """
        for index, entry in enumerate(entries):
            if entry["id"] == asset_id:
                return entries, index

            if entry["type"] == "folder":
                location = Project.find_asset_location(entry["children"], asset_id)

                if location is not None:
                    return location

        return None

    def get_asset(self, asset_id):
        """
        Return an asset or folder by UUID, or None.
        """
        return self.asset_index.get(asset_id)

    def get_assets(self, asset_type):
        """
        Return entries of one type, in tree traversal order.
        """
        return {
            asset_id: entry
            for asset_id, entry in self.asset_index.items()
            if entry["type"] == asset_type
        }

    def set_asset(self, data, entry, *, beside_id=None):
        """
        Add or replace an entry in a proposed project snapshot.
        """
        # Find the entry to be replaced
        entries = data.get("assets", [])
        location = self.find_asset_location(entries, entry["id"])

        # If the to-be-replaced entry is found, replace
        if location is not None:
            siblings, index = location
            siblings[index] = deepcopy(entry)
            return

        # For a new entry, beside_id determines where it is inserted
        if beside_id is not None:
            location = self.find_asset_location(entries, beside_id)

            if location is None:
                raise ValueError("The destination asset no longer exists.")

            siblings, index = location
            siblings.insert(index + 1, deepcopy(entry))

        # If such an index isn't given, append the new entry
        else:
            data.setdefault("assets", []).append(deepcopy(entry))

    def remove_asset(self, data, asset_id):
        """
        Remove an entry from a proposed project snapshot.
        """
        location = self.find_asset_location(data.get("assets", []), asset_id)

        if location is None:
            raise ValueError("The asset no longer exists.")

        siblings, index = location
        del siblings[index]
