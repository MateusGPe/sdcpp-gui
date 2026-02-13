"""
Factory for creating Argument Control Widgets.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, Optional

from sd_cpp_gui.domain.generation import controls
from sd_cpp_gui.domain.generation.commands_loader import CommandDefinition
from sd_cpp_gui.domain.generation.processors import ArgumentProcessor
from sd_cpp_gui.ui.controls.base import BaseArgumentControl
from sd_cpp_gui.ui.controls.boolean_control import BooleanControl
from sd_cpp_gui.ui.controls.choice_control import ChoiceControl
from sd_cpp_gui.ui.controls.numeric_control import NumericControl
from sd_cpp_gui.ui.controls.path_control import PathControl
from sd_cpp_gui.ui.controls.string_control import StringControl


def create_argument_control(
    parent: tk.Widget,
    flag: str,
    arg_data: CommandDefinition,
    processor: ArgumentProcessor,
    **kwargs: Any,
) -> Optional[BaseArgumentControl]:
    """
    Factory function that creates the appropriate argument control widget.

    Logic: Determines control type (Boolean, Choice, Numeric, Path, String)
    based on argument data and returns instance."""
    arg_type = arg_data["type"]
    common_params: Dict[str, Any] = {
        "name": arg_data.get("name", "Unnamed"),
        "flag": flag,
        "arg_type": arg_type,
        "description": arg_data.get("desc", ""),
        "default_val": arg_data.get("default"),
        "is_required": arg_data.get("required", False),
    }
    if arg_type in ["flag", "boolean", "bool"]:
        return BooleanControl(parent, **common_params, **kwargs)
    elif arg_type in ["enum", "list", "selection"]:
        return ChoiceControl(
            parent,
            options=arg_data.get("options", []),
            **common_params,
            **kwargs,
        )
    elif arg_type in ["integer", "float", "int"]:
        return NumericControl(parent, **common_params, **kwargs)
    elif "array" in arg_type or arg_type in ["str", "string"]:
        path_mode = controls.detect_path_type(arg_data)
        if path_mode:
            return PathControl(
                parent,
                open_mode=path_mode,
                file_types=arg_data.get("open_types"),
                **common_params,
                **kwargs,
            )
        else:
            return StringControl(parent, **common_params, **kwargs)
    else:
        return StringControl(parent, **common_params, **kwargs)
