from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from sd_cpp_gui.domain.generation.commands_loader import (
    CommandDefinition,
    CommandLoader,
)
from sd_cpp_gui.domain.generation.parser import CommandParser
from sd_cpp_gui.infrastructure.logger import get_logger

if TYPE_CHECKING:
    pass
logger = get_logger("CommandController")


class CommandController:
    """
    Integrates the CommandBar UI with the business logic defined in
    commands.json.
    Generates rich suggestions (Name + Flag) while keeping tokens technical.
    """

    def __init__(self, loader: CommandLoader) -> None:
        """Logic: Initializes controller with command loader and parser."""
        self.loader = loader
        self.parser = CommandParser(loader)

    def get_suggestions(
        self, tokens: List[str]
    ) -> Tuple[Union[List[Tuple[str, str]], List[str], type, Tuple, None], str]:
        """
        Main callback.
        Returns suggestions as [(Display, Value), ...] or Lists or Validators.

        Logic: Determines context (command vs value) and returns appropriate
        suggestions or validation rules."""
        if not tokens:
            internal: List[Tuple[str, str]] = [
                ("Clear all", "/clear"),
                ("Generate", "/generate"),
            ]
            return (
                self._get_all_flag_suggestions() + internal,
                "Select a command...",
            )
        last_flag_def = self._get_pending_flag_definition(tokens)
        if last_flag_def:
            return self._get_value_suggestions(last_flag_def)
        return (self._get_all_flag_suggestions(), "Select next command...")

    def _get_all_flag_suggestions(self) -> List[Tuple[str, str]]:
        """
        Generates the list of (Label, Flag) for the UI.
        Label: "Steps (--steps)"
        Value: "--steps"
        """
        suggestions = []
        cmds = self.loader.get_all()
        for cmd in cmds:
            flag = cmd["flag"]
            if flag in self.loader.ignored_flags:
                continue
            main_flag = flag.split(",")[0].strip()
            name = cmd["name"]
            label = f"{name} ({main_flag})"
            suggestions.append((label, main_flag))
        return suggestions

    def _get_value_suggestions(self, cmd: CommandDefinition) -> Tuple[Any, str]:
        """
        Returns value suggestions or type validators for a specific command.
        """
        t = cmd["type"].lower()
        name = cmd["name"]
        if t == "enum" and cmd.get("options"):
            return (cmd["options"], f"Select {name}...")
        if t == "integer":
            return (int, f"Enter {name} (Integer)...")
        if t == "float":
            return (float, f"Enter {name} (Float)...")
        return ([], f"Type {name}...")

    def _get_pending_flag_definition(
        self, tokens: List[str]
    ) -> Optional[CommandDefinition]:
        """
        Determines if the last token is a flag that requires a value next.
        """
        expecting_val = False
        current_def = None
        for token in tokens:
            is_known_flag = self.loader.get_by_flag(token) is not None
            if expecting_val:
                if is_known_flag and (
                    current_def := self.loader.get_by_flag(token)
                ):
                    expecting_val = current_def["type"] not in (
                        "flag",
                        "boolean",
                        "bool",
                    )
                else:
                    expecting_val = False
                    current_def = None
            else:
                cmd = self.loader.get_by_flag(token)
                if cmd:
                    if cmd["type"] in ("flag", "boolean", "bool"):
                        expecting_val = False
                    else:
                        expecting_val = True
                        current_def = cmd
                else:
                    expecting_val = False
        return current_def if expecting_val else None

    def execute(self, tokens: List[str]) -> Dict[str, Any]:
        """Delegates parsing to the parameters module."""
        return self.parser.parse(tokens)
