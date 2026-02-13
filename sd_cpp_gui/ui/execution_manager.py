"""
Execution Manager for the UI.
Refactored to use ArgumentProcessor from sd_cpp_gui.domain.generation.
"""

from __future__ import annotations

import gc
import os
import threading
import time
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from sd_cpp_gui.constants import (
    CHANNEL_APP_EVENTS,
    MSG_GENERATION_FINISHED,
    MSG_QUEUE_PROCESSING_STARTED,
    MSG_QUEUE_PROCESSING_STOPPED,
)
from sd_cpp_gui.data.db.data_manager import QueueManager
from sd_cpp_gui.data.db.models import QueueData
from sd_cpp_gui.domain.generation import ArgumentProcessor, GenerationState
from sd_cpp_gui.domain.generation.server_backend import (
    SDServerRunner,
    ServerProcessManager,
)
from sd_cpp_gui.infrastructure.event_bus import EventBus
from sd_cpp_gui.infrastructure.i18n import get_i18n
from sd_cpp_gui.infrastructure.logger import get_logger

if TYPE_CHECKING:
    from sd_cpp_gui.data.db.data_manager import EmbeddingManager, ModelManager
    from sd_cpp_gui.data.db.settings_manager import SettingsManager
    from sd_cpp_gui.domain.generation.commands_loader import CommandLoader
    from sd_cpp_gui.domain.generation.engine import ExecutionResult
    from sd_cpp_gui.domain.generation.interfaces import IGenerator
    from sd_cpp_gui.infrastructure.i18n import I18nManager

logger = get_logger(__name__)

i18n: I18nManager = get_i18n()


class ExecutionManager:
    """A stateless service that executes a generation based on a given state."""

    def __init__(
        self,
        settings: SettingsManager,
        cmd_loader: CommandLoader,
        model_manager: ModelManager,
        embedding_manager: EmbeddingManager,
        cli_runner: IGenerator,
        server_runner: IGenerator,
    ) -> None:
        """
        Logic: Initializes manager, runners, queue manager,
        and argument processor.
        """
        self.settings = settings
        self.cmd_loader = cmd_loader
        self.models = model_manager
        self.embeddings = embedding_manager
        self.cli_runner = cli_runner
        self.server_runner = server_runner
        self.preview_path: Optional[str] = None
        self.queue_manager = QueueManager()
        self.processing_queue = False
        self.current_runner: Optional[IGenerator] = None
        self.flags_mapping = cmd_loader.flags_mapping
        self.arg_processor = ArgumentProcessor(self.cmd_loader, self.embeddings)

    def start_generation(self, state: GenerationState) -> None:
        """
        The primary entry point to start a generation.
        Validates that a model and prompt are present, converts the high-level
        state into CLI arguments, and triggers the runner.

        Args:
            state: The GenerationState object containing all user inputs.
        """
        if not state.prompt:
            messagebox.showwarning(
                i18n.get("msg.warning"), i18n.get("msg.empty_prompt")
            )
            return
        if not state.model_id:
            messagebox.showwarning(
                i18n.get("msg.warning"), i18n.get("msg.select_model")
            )
            return
        prompt, params = self.arg_processor.convert_to_cli(state)
        self._execute_generation(
            model_id=state.model_id, prompt=prompt, params=params
        )

    def add_to_queue(self, state: GenerationState) -> None:
        """
        Converts the current state into a queue task and persists it.

        Args:
            state: The GenerationState object to queue.
        """
        if not state.model_id or not state.prompt:
            messagebox.showwarning(
                i18n.get("msg.warning"), "Model and prompt are required."
            )
            return
        prompt, params = self.arg_processor.convert_to_cli(state)
        self.queue_manager.add(
            model_id=state.model_id,
            prompt=prompt,
            compiled_params=params,
            metadata={},
        )
        messagebox.showinfo(
            i18n.get("msg.info"), i18n.get("msg.added_to_queue")
        )

    def _prepare_preview(
        self, params: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Prepares preview path and updates params if a preview
        method is selected.

        Logic: Configures preview output path if preview method
        is enabled in params.
        """
        preview_path = None
        preview_cmd = self.cmd_loader.get_by_internal_name("Preview Method")
        if not preview_cmd:
            return (params, None)
        preview_flag = preview_cmd["flag"]
        preview_arg = next(
            (p for p in params if p["flag"] == preview_flag), None
        )
        if preview_arg and str(preview_arg["value"]).lower() not in (
            "none",
            "",
        ):
            output_dir = self.settings.get_output_dir()
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError:
                pass
            preview_path = os.path.join(output_dir, "preview.png")
            path_cmd = self.cmd_loader.get_by_internal_name("Preview Path")
            if path_cmd:
                preview_path_flag = path_cmd["flag"]
                params = [p for p in params if p["flag"] != preview_path_flag]
                params.append(
                    {"flag": preview_path_flag, "value": preview_path}
                )
            if os.path.exists(preview_path):
                try:
                    os.remove(preview_path)
                except OSError:
                    pass
        return (params, preview_path)

    def _execute_generation(
        self,
        model_id: str,
        prompt: str,
        params: List[Any],
        queue_item: Optional[QueueData] = None,
    ) -> None:
        """
        Logic: Retrieves model data, prepares paths/runners, and starts
        the generation runner (CLI or Server).
        """
        EventBus.publish(CHANNEL_APP_EVENTS, {"type": "generation_started"})
        model_data = self.models.get_model(model_id)
        if not model_data:
            self._finish(
                success=False,
                result={
                    "error": "Model not found",
                    "files": [],
                    "seed": None,
                    "generation_time": None,
                    "command": None,
                },
                prompt=prompt,
                params=params,
                model_id=model_id,
                queue_item=queue_item,
            )
            return
        params, preview_path = self._prepare_preview(params)
        self.preview_path = preview_path
        out_path, log_path = self._generate_paths()

        def on_log(text: str, type_tag: str) -> None:
            EventBus.publish("log_message", {"text": text, "level": type_tag})

        def on_done(success: bool, result: ExecutionResult) -> None:
            self._finish(success, result, prompt, params, model_id, queue_item)

        active_runner = self._select_runner(params, 0)
        self.current_runner = active_runner
        runner_name = (
            "SERVER" if isinstance(active_runner, SDServerRunner) else "CLI"
        )
        on_log(f"--- Starting Generation (Mode: {runner_name}) ---", "INFO")
        if preview_path:
            on_log(f"Live Preview enabled: {preview_path}", "INFO")
        active_runner.run(
            model_path=model_data["path"],
            prompt=prompt,
            params=params,
            output_path=out_path,
            log_file_path=log_path,
            on_finish=on_done,
        )

    def _finish(
        self,
        success: bool,
        result: ExecutionResult,
        prompt: str,
        params: List,
        model_id: str,
        queue_item: Optional[QueueData] = None,
    ) -> None:
        """
        Logic: Handles generation completion: cleanup, updates queue
        status, publishes result events, and triggers next queue item.
        """
        gc.collect()
        self.current_runner = None
        self.preview_path = None
        if queue_item:
            new_status = "done" if success else "failed"
            self.queue_manager.update_status(queue_item["uuid"], new_status)
        if success:
            EventBus.publish(
                "generation_success",
                {
                    "result": result,
                    "prompt": prompt,
                    "params": params,
                    "model_id": model_id,
                },
            )
        else:
            EventBus.publish("generation_failure", {"result": result})
        if self.processing_queue:
            threading.Thread(
                target=self._process_queue_delayed, daemon=True
            ).start()
        else:
            EventBus.publish(
                CHANNEL_APP_EVENTS, {"type": MSG_GENERATION_FINISHED}
            )

    def stop_generation(self) -> None:
        """
        Forcefully stops any active generation, whether running via CLI
        or the background server.
        """
        logger.info("STOP requested by user.")
        if self.current_runner:
            self.current_runner.stop()
        if ServerProcessManager().is_running():
            ServerProcessManager().stop()

    def _check_unsupported_flags(self, params: List[Dict]) -> bool:
        """
        Checks if any active parameter is marked as 'unsupported'.

        Logic: Returns True if any parameter is flagged as unsupported
        for server mode.
        """
        for p in params:
            flag = p["flag"]
            config = self.flags_mapping.get(flag)
            if config and config.get("type") == "unsupported":
                return True
        return False

    def _select_runner(
        self, params: List[Dict], queue_lookahead: int = 0
    ) -> IGenerator:
        """
        Logic: Selects CLI or Server runner based on settings
        and flag support.
        """
        execution_mode = self.settings.get("execution_mode", "auto")
        if execution_mode == "cli_only":
            return self.cli_runner
        if execution_mode == "server_only":
            return self.server_runner
        if self._check_unsupported_flags(params):
            EventBus.publish(
                "log_message",
                {
                    "text": "Unsupported server flags detected."
                    " Switching to CLI mode.",
                    "level": "INFO",
                },
            )
            return self.cli_runner
        if queue_lookahead > 0:
            return self.server_runner
        return self.cli_runner

    def _generate_paths(self) -> Tuple[str, str]:
        """
        Logic: Generates output image and log file paths based on timestamp.
        """
        fname = f"img_{int(time.time())}"
        output_dir = self.settings.get_output_dir()
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f"{fname}.png")
        log_path = os.path.join(output_dir, "logs", f"{fname}.log")
        return (out_path, log_path)

    def _process_queue_delayed(self) -> None:
        """Logic: Delays queue processing slightly."""
        time.sleep(0.1)
        if self.processing_queue:
            self._process_queue()

    def _process_queue(self) -> None:
        """
        Logic: Fetches next queue item and executes it, or stops queue
        processing if empty.
        """
        if not self.processing_queue:
            return
        next_item = self.queue_manager.get_next()
        if next_item:
            self.queue_manager.update_status(next_item["uuid"], "running")
            self._execute_generation(
                model_id=next_item["model_id"],
                prompt=next_item["prompt"],
                params=next_item["compiled_params"],
                queue_item=next_item,
            )
        else:
            self.processing_queue = False
            EventBus.publish(
                CHANNEL_APP_EVENTS, {"type": MSG_QUEUE_PROCESSING_STOPPED}
            )

    def start_queue_processing(self) -> None:
        """
        Logic: Enables queue processing, optionally sorts queue,
        and starts processing loop.
        """
        if self.processing_queue:
            return
        if self.settings.get("smart_queue_sort", "True") == "True":
            try:
                self.queue_manager.sort_by_model()
            except AttributeError:
                logger.warning(
                    "QueueManager does not have 'sort_by_model' method."
                    " Skipping sort."
                )
        self.processing_queue = True
        EventBus.publish(
            CHANNEL_APP_EVENTS, {"type": MSG_QUEUE_PROCESSING_STARTED}
        )
        self._process_queue()

    def stop_queue_processing(self, clear_queue: bool = False) -> None:
        """
        Logic: Stops queue processing, stops current generation,
        and optionally clears queue.
        """
        self.processing_queue = False
        self.stop_generation()
        EventBus.publish(
            CHANNEL_APP_EVENTS, {"type": MSG_QUEUE_PROCESSING_STOPPED}
        )
        if clear_queue:
            self.queue_manager.clear()
