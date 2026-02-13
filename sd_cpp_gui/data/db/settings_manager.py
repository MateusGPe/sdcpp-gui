"""
Settings Manager
"""

from typing import Any, Dict, List, Optional

from sd_cpp_gui.data.db.database import db
from sd_cpp_gui.data.db.init_db import Database
from sd_cpp_gui.data.db.models import SettingModel
from sd_cpp_gui.infrastructure.paths import OUTPUT_DIR


class SettingsManager:
    """Manages global application settings."""

    def __init__(self) -> None:
        """Logic: Initializes DB."""
        Database()

    def _get_setting(self, key: str, default: Any) -> Any:
        """
        Internal method to fetch a raw setting value.

        Args:
                key: The setting key.
                default: Value to return if key doesn't exist.

        Returns:
                The stored value or default.
        """
        setting = SettingModel.get_or_none(SettingModel.key == key)
        return setting.value if setting else default

    def get_app(self) -> str:
        """Returns the executable path.

        Logic: Gets executable path."""
        return str(self._get_setting("executable", "./sd"))

    def set_app(self, path: str) -> None:
        """Sets the executable path.

        Logic: Sets executable path."""
        SettingModel.replace(key="executable", value=path).execute()

    def get_output_dir(self) -> str:
        """Returns the executable path or default.

        Logic: Gets output dir."""
        return str(self._get_setting("output_dir", str(OUTPUT_DIR)))

    def set_output_dir(self, path: str) -> None:
        """Sets the executable path.

        Logic: Sets output dir."""
        SettingModel.replace(key="output_dir", value=path).execute()

    def get_str(self, key: str, default: Optional[str] = "") -> Optional[str]:
        """Returns a string value.

        Logic: Gets string setting."""
        var_str = self._get_setting(key, "")
        return str(var_str) if var_str else default

    def set_str(self, key: str, value: str) -> None:
        """
        Saves or updates a string setting.

        Args:
                key: The setting key.
                value: The string value to store.
        """
        SettingModel.replace(key=key, value=value).execute()

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Returns a boolean value.

        Logic: Gets boolean setting."""
        val = self._get_setting(key, str(default))
        return str(val).lower() == "true"

    def set_bool(self, key: str, value: bool) -> None:
        """
        Saves or updates a boolean setting.

        Args:
                key: The setting key.
                value: The boolean value.
        """
        SettingModel.replace(key=key, value=str(value).lower()).execute()

    def set_bulk(self, settings: List[Dict[str, Any]]) -> None:
        """
        Updates or inserts multiple settings at once.
        Expects a list of dicts with 'key' and 'value'.

        Logic: Bulk updates settings.
        """
        data = []
        for item in settings:
            if "key" not in item:
                continue
            val = item.get("value")
            s_val = str(val) if val is not None else None
            data.append({"key": item["key"], "value": s_val})
        if data:
            with db.atomic():
                SettingModel.insert_many(data).on_conflict_replace().execute()

    get = get_str
    set = set_str
