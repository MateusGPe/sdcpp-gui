"""
Responsible for loading command definitions (flags) and layout configurations.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union

from sd_cpp_gui.infrastructure.i18n import I18nManager, get_i18n
from sd_cpp_gui.infrastructure.logger import get_logger

logger = get_logger(__name__)

i18n: I18nManager = get_i18n()


class CommandDefinition(TypedDict):
    """Structure of a command loaded from JSON."""

    name: str
    flag: str
    desc: str
    type: str
    default: Optional[Union[str, int, float, bool, List[Any]]]
    required: bool
    open_types: Optional[List[Tuple[str, str]]]
    open_mode: Optional[str]
    options: Optional[List[str]]


class CommandLoader:
    """Loads and manages command definitions."""

    def __init__(self, filepath: Path) -> None:
        """
        Initializes the loader.
        Args:
                filepath: Absolute path to commands.json.

        Logic: Initializes loader, loads commands, layout
        config, and flags mapping.
        """
        self.filepath: Path = filepath
        self.commands: List[CommandDefinition] = self._load_commands()
        self.layout_file = os.path.join(
            os.path.dirname(filepath), "commands_layout.json"
        )
        (
            self.categories_map,
            self.defaults_flags,
            self.ignored_flags,
            self.icons_map,
            self.i18n_keys_map,
        ) = self._load_layout_config()
        self.flags_mapping_file = os.path.join(
            os.path.dirname(filepath), "flags_mapping.json"
        )
        self.flags_mapping = self._load_flags_mapping()
        self._flag_commands_map: Dict[str, CommandDefinition] = {}
        for c in self.commands:
            flags = [f.strip() for f in c["flag"].split(",")]
            for f in flags:
                self._flag_commands_map[f] = c

    def _load_commands(self) -> List[CommandDefinition]:
        """Loads command definitions from JSON.

        Logic: Loads commands from JSON file."""
        if not os.path.exists(self.filepath):
            return []
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []
                normalized: List[CommandDefinition] = []
                for item in data:
                    item["type"] = item.get("type", "string").strip().lower()
                    if "argument" in item and "flag" not in item:
                        item["flag"] = item["argument"]
                    if "description" in item and "desc" not in item:
                        item["desc"] = item["description"]
                    normalized.append(item)
                return normalized
        except (json.JSONDecodeError, OSError) as err:
            logger.error("Error loading commands.json: %s", err, exc_info=True)
            return []

    def _load_layout_config(
        self,
    ) -> Tuple[
        Dict[str, List[str]],
        List[str],
        List[str],
        Dict[str, str],
        Dict[str, str],
    ]:
        """Loads layout configuration from JSON.

        Logic: Loads layout config."""
        if not os.path.exists(self.layout_file):
            logger.warning("Layout file not found: %s", self.layout_file)
            logger.warning("All commands will be listed under 'Others'.")
            return ({}, [], [], {}, {})
        try:
            with open(self.layout_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return (
                    data.get("categories", {}),
                    data.get("defaults", []),
                    data.get("ignored", []),
                    data.get("icons", {}),
                    data.get("i18n_keys", {}),
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                "Error reading commands_layout.json: %s", e, exc_info=True
            )
            return ({}, [], [], {}, {})

    def _load_flags_mapping(self) -> Dict[str, Any]:
        """Loads flags mapping from JSON.

        Logic: Loads flags mapping."""
        if not os.path.exists(self.flags_mapping_file):
            logger.warning(
                "Flags mapping file not found: %s", self.flags_mapping_file
            )
            return {}
        try:
            with open(self.flags_mapping_file, "r", encoding="utf-8") as f:
                return json.load(f).get("flags", {})  # type: ignore
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                "Error reading flags_mapping.json: %s", e, exc_info=True
            )
            return {}

    def _translate(self, cmd: CommandDefinition) -> CommandDefinition:
        """Translates command fields.

        Logic: Translates command fields."""
        c = cmd.copy()
        raw_flag = c.get("flag", "")
        parts = [p.strip() for p in raw_flag.split(",")]
        main_flag = next(
            (p for p in parts if p.startswith("--")), parts[0] if parts else ""
        )
        key = main_flag.lstrip("-")
        if key:
            c["name"] = i18n.get(f"cmd.{key}.name", c["name"])
            c["desc"] = i18n.get(f"cmd.{key}.desc", c.get("desc", ""))
        return c

    def get_all(self) -> List[CommandDefinition]:
        """Returns all translated commands.

        Logic: Returns all commands."""
        return [self._translate(c) for c in self.commands]

    def raw_all(self) -> List[CommandDefinition]:
        """Returns all raw commands.

        Logic: Returns raw commands."""
        return self.commands

    def get_by_flag(self, flag: str) -> Optional[CommandDefinition]:
        """Finds a translated command by flag.

        Logic: Gets command by flag."""
        found = self._flag_commands_map.get(flag)
        return self._translate(found) if found else None

    def raw_by_flag(self, flag: str) -> Optional[CommandDefinition]:
        """Finds a raw command by flag.

        Logic: Gets raw command by flag."""
        return self._flag_commands_map.get(flag)

    def get_all_flags(self) -> List[str]:
        """Returns list of command flags.

        Logic: Returns all flags."""
        return list(self._flag_commands_map.keys())

    def get_by_name(self, name: str) -> Optional[CommandDefinition]:
        """Finds a translated command by name.

        Logic: Gets command by name."""
        for c in self.commands:
            tc = self._translate(c)
            if tc["name"] == name:
                return tc
        return None

    def get_by_internal_name(self, name: str) -> Optional[CommandDefinition]:
        """Finds a command by internal name.

        Logic: Gets command by internal name."""
        return next((c for c in self.commands if c["name"] == name), None)

    def get_all_names(self) -> List[str]:
        """Returns list of command names.

        Logic: Returns all command names."""
        return [self._translate(c)["name"] for c in self.commands]

    def get_icon(self, category: str, default: str = "🔧") -> str:
        """Returns category icon.

        Logic: Returns icon for category."""
        return self.icons_map.get(category, default)

    def get_category_label(self, category: str) -> str:
        """Returns translated category name.

        Logic: Returns category label."""
        key = self.i18n_keys_map.get(category)
        if key:
            return i18n.get(key, category)
        return category

    def get_categorized_commands(self) -> Dict[str, List[CommandDefinition]]:
        """Returns commands grouped by category.

        Logic: Returns commands"""
        buckets: Dict[str, List[CommandDefinition]] = {
            cat: [] for cat in self.categories_map
        }
        buckets["others"] = []
        flag_to_cat = {}
        for cat, flags in self.categories_map.items():
            for f in flags:
                flag_to_cat[f] = cat
        for cmd in self.commands:
            flag = cmd["flag"]
            if flag in self.ignored_flags:
                continue
            t_cmd = self._translate(cmd)
            target_cat = flag_to_cat.get(flag)
            if target_cat:
                buckets[target_cat].append(t_cmd)
            else:
                buckets["others"].append(t_cmd)
        return {k: v for k, v in buckets.items() if v}
