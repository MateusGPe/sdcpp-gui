"""
Pure Business Logic Handlers.
Separates logic from UI and State coordination.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from sd_cpp_gui.data.db.history_manager import HistoryManager
from sd_cpp_gui.data.db.model_manager import ModelManager
from sd_cpp_gui.domain.generation.processors import ArgumentProcessor
from sd_cpp_gui.domain.generation.states import StateManager
from sd_cpp_gui.ui.components.command_controller import CommandController


def handle_command_submit(
    tokens: List[str],
    controller: CommandController,
    state_manager: StateManager,
    arg_processor: ArgumentProcessor,
    models_mgr: ModelManager,
    general_panel_reset_callback: Callable[[], None],
) -> Optional[str]:
    """
    Processes a command line submission.
    Returns 'TRIGGER_GENERATE' if generation is requested,
    or a model_id string if a model switch occurred,
    or None if just parameters were updated.

    Logic: Handles special commands (/generate, /clear), fuzzy searches
    models, or updates parameters via state manager.
    """
    if "/generate" in tokens or "/run" in tokens:
        return "TRIGGER_GENERATE"
    if "/clear" in tokens:
        general_panel_reset_callback()
        return "TRIGGER_CLEAR"
    parsed_args = controller.execute(tokens)
    target_model_id = None
    if "_positional" in parsed_args:
        state_manager.update_prompt("prompt", parsed_args.pop("_positional"))
    with state_manager.programmatic_update():
        for flag, value in parsed_args.items():
            if value is None:
                continue
            if flag == "--model":
                target_model_id = _fuzzy_find_model(models_mgr, str(value))
                if target_model_id:
                    state_manager.state.model_id = target_model_id
                continue
            if arg_processor.is_prompt_flag(flag):
                state_manager.update_prompt("prompt", str(value))
            elif arg_processor.is_negative_prompt_flag(flag):
                state_manager.update_prompt("negative_prompt", str(value))
            else:
                state_manager.set_control_values(flag, value, enabled=True)
                state_manager.update_parameter(flag, value, enabled=True)
    return target_model_id


def _fuzzy_find_model(models_mgr: ModelManager, query: str) -> Optional[str]:
    """Helper to find model ID by name or partial name.

    Logic: Searches models by exact or partial name match."""
    all_models = models_mgr.get_all()
    target = next((m for m in all_models if m["name"] == query), None)
    if not target:
        target = next(
            (m for m in all_models if query.lower() in m["name"].lower()), None
        )
    return target["id"] if target else None


def configure_state_for_model(
    model_id: str,
    models_mgr: ModelManager,
    state_manager: StateManager,
    keep_params: bool,
) -> List[Tuple[str, Any, bool]]:
    """
    Retrieves model defaults and configures the StateManager.
    Returns the active configuration list (flag, value, enabled)
    for UI rendering.
    Logic: Configures state with model defaults if keep_params is False.
    """
    if not model_id:
        return []
    model_data = models_mgr.get_model(model_id)
    if not model_data:
        return []
    if not keep_params:
        return state_manager.configure_state_for_model(
            cast(Optional[Dict[str, Any]], model_data)
        )
    return []


def handle_network_change(
    network_type: str,
    name: str,
    value: Any,
    enabled: bool,
    state_manager: StateManager,
) -> None:
    """
    Updates logic state based on LoRA/Embedding UI changes.
    Expected value tuple structure:
    LoRA: (strength, dir_path, trigger, content_hash, remote_version_id)
    Embedding: (target, strength, dir_path, trigger, content_hash,
    remote_version_id)


    Logic: Updates state manager with LoRA or Embedding data changes."""
    if not value:
        if network_type == "lora":
            state_manager.update_lora(name)
        elif network_type == "embedding":
            state_manager.update_embedding(name)
        return
    content_hash = None
    remote_version_id = None
    original_name = name
    if network_type == "lora":
        strength = value[0]
        dir_path = value[1]
        trigger = value[2]
        if len(value) > 3:
            content_hash = value[3]
        if len(value) > 4:
            remote_version_id = value[4]
        state_manager.update_lora(
            name,
            strength,
            dir_path,
            enabled,
            trigger,
            content_hash,
            remote_version_id,
            original_name,
        )
    elif network_type == "embedding":
        target = value[0]
        strength = value[1]
        dir_path = value[2]
        trigger = value[3]
        if len(value) > 4:
            content_hash = value[4]
        if len(value) > 5:
            remote_version_id = value[5]
        state_manager.update_embedding(
            name,
            target,
            strength,
            dir_path,
            enabled,
            trigger,
            content_hash,
            remote_version_id,
            original_name,
        )


def restore_session_data(
    uuid: str,
    history_mgr: HistoryManager,
    arg_processor: ArgumentProcessor,
    state_manager: StateManager,
) -> Optional[Dict[str, Any]]:
    """
    Restores state from history.
    Returns data needed for UI updates (image path, model_id).

    Logic: Loads history entry, restores state via argument processor,
    and returns UI metadata.
    """
    entry = history_mgr.get(uuid)
    if not entry:
        return None
    model_id = entry.get("model_id")
    prompt = entry.get("prompt", "")
    metadata = entry.get("metadata", {})
    restored_state = arg_processor.restore_from_args(
        model_id=model_id,
        prompt=prompt,
        compiled_params=entry.get("compiled_params", []),
        metadata=metadata,
    )
    state_manager.restore_state(restored_state)
    img_path = entry.get("output_path")
    if isinstance(img_path, list) and img_path:
        img_path = img_path[0]
    return {"model_id": model_id, "image_path": img_path}
