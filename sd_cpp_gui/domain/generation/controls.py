from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Dict, List, Optional, Set

from sd_cpp_gui.domain.generation.commands_loader import CommandDefinition
from sd_cpp_gui.ui.controls.base import BaseArgumentControl
from sd_cpp_gui.ui.controls.boolean_control import BooleanControl
from sd_cpp_gui.ui.controls.choice_control import ChoiceControl
from sd_cpp_gui.ui.controls.numeric_control import NumericControl
from sd_cpp_gui.ui.controls.path_control import PathControl
from sd_cpp_gui.ui.controls.string_control import StringControl


def detect_path_type(arg_data: CommandDefinition) -> Optional[str]:
    """Helper to determine if a string-like argument is a path.

    Logic: Detects path type from argument data."""
    if arg_data.get("open_mode") in ["file_open", "file_save", "directory"]:
        return arg_data["open_mode"]  # type: ignore
    name_str = arg_data.get("name", "").lower()
    flag_str = arg_data.get("flag", "")
    if "dir" in name_str:
        return "directory"
    if flag_str == "-o" or "output" in name_str:
        return "file_save"
    if any((x in name_str for x in ["path", "file", "model", "image"])):
        return "file_open"
    return None


def new_argument_control(
    parent: tk.Widget, flag: str, arg_data: CommandDefinition, **kwargs: Any
) -> Optional[BaseArgumentControl]:
    """
    Factory function that creates, registers, and returns the appropriate
    argument control widget based on the command's data type.

    Logic: Creates control widget.
    """
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
        path_mode = detect_path_type(arg_data)
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


def remove_control(
    controls: Dict[str, Set[BaseArgumentControl]],
    flag: str,
    control: BaseArgumentControl,
) -> None:
    """
    Unregisters a specific control from the dictionary.

    Logic: Removes control.
    """
    if flag in controls:
        if control in controls[flag]:
            controls[flag].remove(control)
        if not controls[flag]:
            del controls[flag]


def cleanup_dead_controls(
    controls: Dict[str, Set[BaseArgumentControl]],
) -> None:
    """
    Iterates through the controls dict and removes references
    to destroyed widgets.

    Logic: Cleans up dead controls.
    """
    flags_to_remove: List[str] = []
    for flag, control_set in controls.items():
        dead_controls = {c for c in control_set if not c.winfo_exists()}
        control_set.difference_update(dead_controls)
        if not control_set:
            flags_to_remove.append(flag)
    for flag in flags_to_remove:
        del controls[flag]


def set_overriden_controls(
    controls: Dict[str, Set[BaseArgumentControl]],
    overriders: Dict[str, BaseArgumentControl],
) -> None:
    """
    Updates the override status for all controls.

    Args:
        controls: The dictionary of all active controls.
        overriders: A map of flags to the controls that should be
        active (not overridden).
    """
    for flag, control_set in controls.items():
        if flag not in overriders:
            for c in control_set:
                c.set_override_mode(False)
            continue
        current = overriders[flag]
        for c in control_set:
            c.set_override_mode(c != current)


def bind_control_callbacks(
    control: BaseArgumentControl,
    on_value_change: Callable[..., None],
    on_enabled_change: Callable[..., None],
) -> None:
    """
    Attaches callbacks to the control's internal Tkinter variables.
    Abstracts away the .trace_add logic.

    Logic: Binds callbacks.
    """
    if hasattr(control, "var_value"):
        control.var_value.trace_add("write", on_value_change)
    if hasattr(control, "var_enabled"):
        control.var_enabled.trace_add("write", on_enabled_change)


def get_control(
    controls: Dict[str, Set[BaseArgumentControl]], flag: str
) -> Optional[BaseArgumentControl]:
    """Gets a live control widget associated with a flag.

    Logic: Returns active control."""
    if flag in controls:
        for control in controls[flag]:
            if not control.is_overridden and control.winfo_exists():
                return control
    return None


def _apply_to_controls(
    controls: Set[BaseArgumentControl],
    action: Callable[[BaseArgumentControl], None],
) -> None:
    """Helper to iterate safely over controls and apply an action.

    Logic: Applies action to controls."""
    if not controls:
        return
    for control in controls:
        if control.winfo_exists():
            action(control)


def set_value(controls: Set[BaseArgumentControl], value: Any) -> None:
    """Sets the value for all controls associated with a flag.

    Logic: Sets value on controls."""

    def _action(c: BaseArgumentControl) -> None:
        if hasattr(c, "set_value"):
            c.set_value(value)
        elif hasattr(c, "var_value"):
            c.var_value.set(value)

    _apply_to_controls(controls, _action)


def set_enabled(controls: Set[BaseArgumentControl], enabled: bool) -> None:
    """Sets the enabled state for all controls associated with a flag.

    Logic: Sets enabled state on controls."""

    def _action(c: BaseArgumentControl) -> None:
        c.var_enabled.set(enabled)
        c.toggle_state()

    _apply_to_controls(controls, _action)


def set_control_values(
    controls: Set[BaseArgumentControl], value: Any, enabled: bool
) -> None:
    """
    Updates both the value and the enabled state for a set of controls.

    Args:
            controls: Set of controls to update.
            value: The new value.
            enabled: The new enabled state.
    """

    def _action(c: BaseArgumentControl) -> None:
        if hasattr(c, "set_value"):
            c.set_value(value)
        elif hasattr(c, "var_value"):
            c.var_value.set(value)
        c.var_enabled.set(enabled)
        c.toggle_state()

    _apply_to_controls(controls, _action)


def consolidate_params(
    controls: Dict[str, Set[BaseArgumentControl]],
) -> Dict[str, Any]:
    """
    Aggregates the current state (value and enabled) from all active
    UI controls.

    Returns:
        A dictionary mapping flags to their current UI state:
        {'--flag': {'enabled': bool, 'value': Any}, ...}
    """
    params = {}
    for flag, control_set in controls.items():
        for ctrl in control_set:
            if not ctrl.is_overridden and ctrl.winfo_exists():
                params[flag] = {
                    "enabled": ctrl.var_enabled.get(),
                    "value": ctrl.var_value.get(),
                }
                break
    return params
