"""
parameters/parser.py
Parses raw text tokens into structured parameter dictionaries.
"""

from typing import Any, Dict, List

from sd_cpp_gui.domain.generation.commands_loader import CommandLoader


class CommandParser:
    """
    Translates a list of string tokens (e.g. ["--steps", "20"])
    into a dictionary (e.g. {"--steps": 20}).
    """

    def __init__(self, loader: CommandLoader) -> None:
        """Logic: Initializes parser."""
        self.loader = loader

    def parse(self, tokens: List[str]) -> Dict[str, Any]:
        """Parses tokens into a dict of flags and values.
        Logic: Parses token list into dictionary based on command
        definitions."""
        parsed: Dict[str, Any] = {}
        positional: List[str] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            cmd_def = self.loader.get_by_flag(token)
            if not cmd_def:
                positional.append(token)
                i += 1
                continue
            key = cmd_def["flag"]
            if cmd_def["type"] in ("flag", "boolean", "bool"):
                parsed[key] = True
                i += 1
            elif i + 1 < len(tokens):
                val_str = tokens[i + 1]
                next_is_flag = self.loader.get_by_flag(val_str) is not None
                if next_is_flag:
                    parsed[key] = None
                    i += 1
                else:
                    parsed[key] = self._convert_value(val_str, cmd_def["type"])
                    i += 2
            else:
                parsed[key] = None
                i += 1
        if positional:
            parsed["_positional"] = " ".join(positional)
        return parsed

    def _convert_value(self, value: str, type_str: str) -> Any:
        """Logic: Converts string value to appropriate type."""
        t = type_str.lower()
        try:
            if t in ("integer", "int"):
                return int(value)
            if t == "float":
                return float(value)
            if t in ("boolean", "bool"):
                return value.lower() in ("true", "1", "yes", "on")
        except ValueError:
            return value
        return value
