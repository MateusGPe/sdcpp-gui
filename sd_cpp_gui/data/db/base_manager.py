"""
Base Manager with Import/Export capabilities.
"""

import json
from typing import Any, Dict, Generic, List, Type, TypeVar, Union

import peewee

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False
try:
    import toml

    HAS_TOML = True
except ImportError:
    HAS_TOML = False
TModel = TypeVar("TModel", bound=peewee.Model)


class ImportExportMixin:
    """Mixin for Import/Export functionality."""

    def get_all(self) -> Union[List[Any], Dict[str, Any]]:
        """Must be implemented by the child class.

        Logic: Abstract method."""
        raise NotImplementedError

    def _process_import_data(
        self, data: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Must be implemented by the child class.

        Logic: Abstract method."""
        raise NotImplementedError

    @staticmethod
    def _safe_load_json(val: Any, default: Any = None) -> Any:
        """Helper to safely parse JSON strings from DB.

        Logic: Safely parses JSON string."""
        if not val:
            return default
        try:
            return json.loads(str(val))
        except (json.JSONDecodeError, TypeError):
            return default

    def export_to_json(self, filepath: str) -> None:
        """Exports data to a JSON file.

        Logic: Exports data to JSON."""
        data = self.get_all()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def import_from_json(self, filepath: str) -> None:
        """Imports data from a JSON file.

        Logic: Imports data from JSON."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._process_import_data(data)

    def export_to_yaml(self, filepath: str) -> None:
        """Exports data to a YAML file.

        Logic: Exports data to YAML."""
        if not HAS_YAML:
            raise ImportError("Install 'pyyaml' for YAML support.")
        data = self.get_all()
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

    def import_from_yaml(self, filepath: str) -> None:
        """Imports data from a YAML file.

        Logic: Imports data from YAML."""
        if not HAS_YAML:
            raise ImportError("Install 'pyyaml' for YAML support.")
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._process_import_data(data)

    def export_to_toml(self, filepath: str, root_key: str = "data") -> None:
        """Exports data to a TOML file.

        Logic: Exports data to TOML."""
        if not HAS_TOML:
            raise ImportError("Install 'toml' for TOML support.")
        data = self.get_all()
        with open(filepath, "w", encoding="utf-8") as f:
            toml.dump({root_key: data}, f)

    def import_from_toml(self, filepath: str, root_key: str = "data") -> None:
        """Imports data from a TOML file.

        Logic: Imports data from TOML."""
        if not HAS_TOML:
            raise ImportError("Install 'toml' for TOML support.")
        with open(filepath, "r", encoding="utf-8") as f:
            data = toml.load(f)
        if root_key in data:
            self._process_import_data(data[root_key])


class RemoteIndexMixin(Generic[TModel]):
    """
    Mixin for managers that handle assets linked to remote
    repositories (Civitai/HF).
    Requires the model class to have `remote_version_id`
    and `path` fields.
    """

    model_class: Type[TModel]

    def get_remote_index(self) -> Dict[str, str]:
        """
        Returns a map of {remote_version_id: local_path} for fast lookup.
        Used by the browser to check ownership.

        Logic: Returns remote ID to path mapping.
        """
        if not hasattr(self, "model_class"):
            raise NotImplementedError(
                "Classes using RemoteIndexMixin must define 'model_class'"
            )
        model = self.model_class
        query = model.select(model.remote_version_id, model.path)  # type: ignore

        return {
            str(e.remote_version_id): str(e.path)  # type: ignore
            for e in query
            if e.remote_version_id  # type: ignore
        }
