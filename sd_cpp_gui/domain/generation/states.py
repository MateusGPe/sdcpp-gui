from __future__ import annotations

import tkinter as tk
from contextlib import contextmanager
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
)

from sd_cpp_gui.domain.generation import controls
from sd_cpp_gui.domain.generation.commands_loader import (
    CommandDefinition,
    CommandLoader,
)
from sd_cpp_gui.domain.generation.processors import ArgumentProcessor
from sd_cpp_gui.domain.generation.types import (
    EmbeddingData,
    GenerationState,
    LoraData,
)
from sd_cpp_gui.ui.controls.base import BaseArgumentControl

ListenerCallback = Callable[[str, str, Any], None]


class StateManager:
    """
    A unified controller that manages Data Logic, View Logic and Sync.
    """

    def __init__(
        self,
        cmd_loader: CommandLoader,
        generation_state: GenerationState,
        arg_processor: ArgumentProcessor,
    ) -> None:
        """Logic: Initializes state manager."""
        self.cmd_loader = cmd_loader
        self.state = generation_state
        self.arg_processor = arg_processor
        self.controls: Dict[str, Set[BaseArgumentControl]] = {}
        self._is_programmatic_update = False
        self._listeners: List[ListenerCallback] = []
        self.state.add_triggers = {"lora": False, "embedding": False}

    def append_triggers(
        self, name: Literal["lora", "embedding"], value: bool
    ) -> None:
        """
        Updates whether trigger words should be automatically appended
        for a network type.

        Args:
            name: Either 'lora' or 'embedding'.
            value: True to enable auto-triggers.
        """
        self.state.add_triggers[name] = value

    def add_listener(self, callback: ListenerCallback) -> None:
        """Adds a callback to be notified on state changes.

        Logic: Adds listener."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: ListenerCallback) -> None:
        """Removes a listener callback.

        Logic: Removes listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, event_type: str, key: str, value: Any = None) -> None:
        """
        Notifies all listeners of a state change.
        event_type: 'parameter', 'lora', 'embedding', 'prompt', 'reset'

        Logic: Notifies listeners.
        """
        for listener in self._listeners:
            listener(event_type, key, value)

    def update_prompt(self, attr_name: str, value: str) -> None:
        """
        Updates a prompt attribute in the state and notifies listeners.

        Args:
                attr_name: 'prompt' or 'negative_prompt'.
                value: The new text value.
        """
        current_val = getattr(self.state, attr_name, None)
        if current_val != value:
            setattr(self.state, attr_name, value)
            self._notify("prompt", attr_name, value)

    def update_parameter(self, flag: str, value: Any, enabled: bool) -> bool:
        """
        Updates a CLI parameter in the state.

        Args:
            flag: The CLI flag (e.g., '--steps').
            value: The value for the parameter.
            enabled: If False, the parameter is removed from the active state.

        Returns:
            True if the state was actually changed.
        """
        changed = False
        current_val = self.state.parameters.get(flag)
        if enabled:
            if current_val != value:
                self.state.parameters[flag] = value
                changed = True
                self._notify("parameter", flag, value)
        elif flag in self.state.parameters:
            del self.state.parameters[flag]
            changed = True
            self._notify("parameter", flag, None)
        return changed

    def configure_state_for_model(
        self, model_data: Optional[Dict[str, Any]]
    ) -> List[Tuple[str, Any, bool]]:
        """
        Resets the state and applies default parameters from a selected model.

        Args:
                model_data: The dictionary of model information from the DB.

        Returns:
                A list of (flag, value, enabled) tuples representing the new
                configuration for the UI.
        """
        defaults = (
            self.arg_processor.get_model_defaults(model_data)
            if model_data
            else []
        )
        active_config: List[Tuple[str, Any, bool]] = []
        with self.programmatic_update():
            self.state.parameters.clear()
            self.state.loras.clear()
            self.state.embeddings.clear()
            self.cleanup_controls()
            reset_flags = set(self.controls.keys()).difference(
                self.arg_processor.get_persistent_flags()
            )
            for flag in reset_flags:
                self.set_enabled(flag, False)
            self._notify("reset", "all", {"keep_networks": False})
            for param in defaults:
                flag = param["flag"]
                value = param["value"]
                enabled = param.get("enabled", True)
                if self.arg_processor.is_prompt_flag(flag):
                    self.update_prompt("prompt", str(value))
                    continue
                if self.arg_processor.is_negative_prompt_flag(flag):
                    self.update_prompt("negative_prompt", str(value))
                    continue
                if self.arg_processor.is_excluded(flag):
                    continue
                self.update_parameter(flag, value, enabled)
                ctrl = self.get_control(flag)
                if ctrl:
                    ctrl.set_override_mode(True)
                    self.set_control_values(flag, value, enabled)
                active_config.append((flag, value, enabled))
        self.sync_all_controls()
        return sorted(active_config, key=lambda x: x[0])

    def restore_state(self, restored_state: GenerationState) -> None:
        """
        Restores a full state (params, prompts, networks) from a
        GenerationState object.
        Updates both Logic (Data) and View (UI Controls).

        Logic: Replaces current state with restored state and updates UI.
        """
        with self.programmatic_update():
            reset_flags = set(self.controls.keys()).difference(
                self.arg_processor.get_persistent_flags()
            )
            for flag in reset_flags:
                self.set_enabled(flag, False)
            for flag, value in restored_state.parameters.items():
                self.update_parameter(flag, value, enabled=True)
                self.set_control_values(flag, value, enabled=True)
            self.update_prompt("prompt", restored_state.prompt)
            self.update_prompt(
                "negative_prompt", restored_state.negative_prompt
            )
            self.state.loras.clear()
            self.state.embeddings.clear()
            for name, data in restored_state.loras.items():
                self.update_lora(
                    name,
                    data.strength,
                    data.dir_path,
                    True,
                    data.triggers,
                    content_hash=data.content_hash,
                    remote_version_id=data.remote_version_id,
                    original_name=data.original_name,
                )
            for name, data in restored_state.embeddings.items():
                self.update_embedding(
                    name,
                    data.target,
                    data.strength,
                    data.dir_path,
                    True,
                    data.triggers,
                    content_hash=data.content_hash,
                    remote_version_id=data.remote_version_id,
                    original_name=data.original_name,
                )

    def sync_all_controls(self):
        """
        Forces a synchronization of the internal state parameters from the
        current values held by all registered UI controls.
        """
        res = controls.consolidate_params(self.controls)
        for flag, data in res.items():
            enabled = data["enabled"]
            value = data["value"]
            if enabled:
                if (
                    flag not in self.state.parameters
                    or self.state.parameters[flag] != value
                ):
                    self.state.parameters[flag] = value
            elif flag in self.state.parameters:
                del self.state.parameters[flag]

    def update_lora(
        self,
        name: str,
        strength: float = 0.0,
        dir_path: str = "",
        enabled: bool = False,
        triggers: Optional[str] = None,
        content_hash: Optional[str] = None,
        remote_version_id: Optional[str] = None,
        original_name: Optional[str] = None,
    ) -> bool:
        """
        Updates or removes a LoRA in the generation state.

        Args:
                name: The name/identifier of the LoRA.
                strength: The influence weight.
                dir_path: Local directory containing the file.
                enabled: If False, the LoRA is removed.
                triggers: Trigger words for this LoRA.
                content_hash: SHA256 hash for robust identification.

        Returns:
                True if the state was changed.
        """
        changed = False
        if enabled:
            new_data = LoraData(
                strength,
                dir_path,
                triggers,
                content_hash,
                remote_version_id,
                original_name,
            )
            current_data = self.state.loras.get(name)
            if current_data != new_data:
                self.state.loras[name] = new_data
                changed = True
                self._notify("lora", name, new_data)
        elif name in self.state.loras:
            del self.state.loras[name]
            changed = True
            self._notify("lora", name, None)
        return changed

    def update_embedding(
        self,
        name: str,
        target: str = "",
        strength: float = 0.0,
        dir_path: str = "",
        enabled: bool = False,
        triggers: Optional[str] = None,
        content_hash: Optional[str] = None,
        remote_version_id: Optional[str] = None,
        original_name: Optional[str] = None,
    ) -> bool:
        """
        Updates or removes an Embedding in the generation state.

        Args:
                name: The name/identifier.
                target: 'positive' or 'negative' prompt target.
                strength: The influence weight.
                dir_path: Local directory.
                enabled: If False, the embedding is removed.
                triggers: Trigger words.

        Returns:
                True if the state was changed.
        """
        changed = False
        if enabled:
            new_data = EmbeddingData(
                target,
                strength,
                dir_path,
                triggers,
                content_hash,
                remote_version_id,
                original_name,
            )
            current_data = self.state.embeddings.get(name)
            if current_data != new_data:
                self.state.embeddings[name] = new_data
                changed = True
                self._notify("embedding", name, new_data)
        elif name in self.state.embeddings:
            del self.state.embeddings[name]
            changed = True
            self._notify("embedding", name, None)
        return changed

    @contextmanager
    def programmatic_update(self) -> Generator[None, None, None]:
        """Context manager to suppress UI callbacks during bulk updates.

        Logic: Sets programmatic flag during context."""
        previous = self._is_programmatic_update
        self._is_programmatic_update = True
        try:
            yield
        finally:
            self._is_programmatic_update = previous

    def get_control(self, flag: str) -> Optional[BaseArgumentControl]:
        """Logic: Gets control for flag."""
        return controls.get_control(self.controls, flag)

    def set_value(self, flag: str, value: Any) -> None:
        """
        Sets the value for UI controls (does not trigger logic if programmatic).

        Logic: Sets control value.
        """
        with self.programmatic_update():
            controls.set_value(self.controls.get(flag, set()), value)

    def set_enabled(self, flag: str, enabled: bool) -> None:
        """Sets the enabled state for UI controls.

        Logic: Sets control enabled state."""
        with self.programmatic_update():
            controls.set_enabled(self.controls.get(flag, set()), enabled)

    def set_control_values(self, flag: str, value: Any, enabled: bool) -> None:
        """Sets the value for UI controls.

        Logic: Sets control values and state."""
        with self.programmatic_update():
            controls.set_control_values(
                self.controls.get(flag, set()), value, enabled
            )

    def remove_control(self, flag: str, control: BaseArgumentControl) -> None:
        """Logic: Removes control reference."""
        controls.remove_control(self.controls, flag, control)

    def cleanup_controls(self) -> None:
        """Logic: Removes destroyed controls."""
        controls.cleanup_dead_controls(self.controls)

    def set_overriden_controls(
        self, overriders: Dict[str, BaseArgumentControl]
    ) -> None:
        """Logic: Sets override mode on controls."""
        controls.set_overriden_controls(self.controls, overriders)

    def register_control(
        self, flag: str, control: BaseArgumentControl, unique: bool = False
    ) -> bool:
        """
        Registers a control and links its events to the State Logic methods.

        Logic: Registers control and binds callbacks.
        """
        if flag not in self.controls:
            self.controls[flag] = set()
        elif unique:
            return False
        self.controls[flag].add(control)

        def _standard_update(*_: Any) -> None:
            if control.is_overridden or self._is_programmatic_update:
                return
            try:
                enabled = control.var_enabled.get()
                value = control.var_value.get() if enabled else None
                self.update_parameter(flag, value, enabled)
            except (tk.TclError, ValueError):
                pass

        def _create_attr_updater(attr_name: str) -> Callable[..., None]:
            def _update(*_: Any) -> None:
                if control.is_overridden or self._is_programmatic_update:
                    return
                val = (
                    str(control.var_value.get())
                    if control.var_enabled.get()
                    else ""
                )
                self.update_prompt(attr_name, val)

            return _update

        prompt_flag = self._get_flag_by_internal_name("Prompt")
        neg_prompt_flag = self._get_flag_by_internal_name("Negative Prompt")
        callback_fn = _standard_update
        if flag == prompt_flag:
            callback_fn = _create_attr_updater("prompt")
        elif flag == neg_prompt_flag:
            callback_fn = _create_attr_updater("negative_prompt")
        controls.bind_control_callbacks(
            control=control,
            on_value_change=callback_fn,
            on_enabled_change=callback_fn,
        )
        return True

    def _get_flag_by_internal_name(self, name: str) -> str:
        """Logic: Gets flag by internal name."""
        cmd = self.cmd_loader.get_by_internal_name(name)
        return cmd["flag"] if cmd else ""

    def new_argument_control(
        self, parent: tk.Widget, flag: str, unique: bool = False, **kwargs: Any
    ) -> Optional[BaseArgumentControl]:
        """Logic: Creates and registers new argument control."""
        arg_data: Optional[CommandDefinition] = self.cmd_loader.get_by_flag(
            flag
        )
        if not arg_data:
            return None
        control = controls.new_argument_control(
            parent, flag, arg_data, **kwargs
        )
        if control:
            if not self.register_control(flag, control, unique=unique):
                control.destroy()
                return None
        return control

    def consolidate_params(self) -> Dict[str, Any]:
        """Logic: Consolidates parameters from controls."""
        return controls.consolidate_params(self.controls)
