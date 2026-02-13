"""
Main Application Coordinator.
Coordinates the GUI View, Business Logic, and State Management.
"""

from __future__ import annotations

import tkinter as tk
from logging import Logger
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

import ttkbootstrap as ttk

from sd_cpp_gui.constants import (
    CHANNEL_APP_EVENTS,
    EMOJI_FONT,
    MSG_DATA_IMPORTED,
    MSG_GENERATION_FINISHED,
    MSG_GENERATION_STARTED,
    MSG_MODEL_SELECTED,
    MSG_QUEUE_PROCESSING_STARTED,
    MSG_QUEUE_PROCESSING_STOPPED,
    SYSTEM_FONT,
)
from sd_cpp_gui.domain.generation import (
    ArgumentProcessor,
    GenerationState,
    StateManager,
)
from sd_cpp_gui.domain.generation.process_manager import ServerProcessManager
from sd_cpp_gui.infrastructure.event_bus import EventBus
from sd_cpp_gui.infrastructure.i18n import I18nManager, get_i18n
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.plugins.core_preview.panel import PreviewPanel
from sd_cpp_gui.ui import themes
from sd_cpp_gui.ui.app import logic_handlers, view_builder
from sd_cpp_gui.ui.components.command_controller import CommandController
from sd_cpp_gui.ui.components.nine_slices import TextureAtlas
from sd_cpp_gui.ui.components.utils import (
    CopyLabel,
    center_window,
    restore_sash,
    save_sash_position,
)
from sd_cpp_gui.ui.execution_manager import ExecutionManager
from sd_cpp_gui.ui.features.history.history_presenter import HistoryPresenter

# REMOVED: Direct import of RemoteBrowserWindow
# from sd_cpp_gui.ui.features.library.browser.window import RemoteBrowserWindow

if TYPE_CHECKING:
    from sd_cpp_gui.domain.generation.interfaces import IGenerator
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer

i18n: I18nManager = get_i18n()
logger: Logger = get_logger(__name__)


class AppCoordinator(ttk.Window):
    """
    The main application window and coordinator.
    Acts as the composition root for the UI and the Presenter for logic.
    """

    def __init__(
        self,
        container: DependencyContainer,
        cli_runner: IGenerator,
        server_runner: IGenerator,
    ) -> None:
        """
        Logic: Initializes the app, sets up managers, themes, state,
        and starts UI construction.
        """
        self.container = container
        self.runner = cli_runner
        self.server_runner = server_runner
        self.cmd_loader = container.cmd_loader
        self.settings = container.settings
        saved_lang = self.settings.get("language", None) or "en_US"
        i18n.load_locale(saved_lang)
        self.settings_dict = {}
        self.history = container.history
        self.models = container.models
        self.loras = container.loras
        self.embeddings = container.embeddings
        self.history_presenter = HistoryPresenter(
            self, self.history, self.models, self.cmd_loader
        )
        self._persistent_job = None
        self.generation_state: GenerationState = container.generation_state
        self.arg_processor: ArgumentProcessor = container.arg_processor
        self.state_manager: StateManager = container.state_manager
        self.args_manager = self.state_manager
        self.execution_manager: ExecutionManager = (
            container.init_execution_manager(cli_runner, server_runner)
        )
        self.command_controller = CommandController(self.cmd_loader)
        themes.register_themes()
        self.themes = list(themes.USER_THEMES.keys())
        saved_theme = self.settings.get("theme", default=self.themes[0])
        self.theme_id = 0

        # Initialize with a safe default to prevent TclError on fallback (double init)
        super().__init__(themename="cosmo")

        if saved_theme and saved_theme != "cosmo":
            try:
                if saved_theme in self.themes:
                    self.style.theme_use(saved_theme)
                    self.theme_id = self.themes.index(saved_theme)

                    logger.info(f"Successfully applied theme: {saved_theme}")
            except Exception as e:
                logger.warning(
                    "Failed to apply theme '%s': %s. Falling back to default.",
                    saved_theme,
                    e,
                )

        self.ui_refs: view_builder.UIReferences
        self.sidebar_expanded = False
        self.current_category: Optional[str] = None
        self.side_color = ttk.Style.get_instance().theme.type
        self.preview: PreviewPanel
        self.title(i18n.get("app.title"))
        self._init_ui()
        self._setup_subscribers()
        self._load_persistent_settings()
        self.after(100, self._load_initial_data)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_ui(self) -> None:
        """
        Constructs the UI using the functional view builder.
        Logic: Builds the layout, loads the preview plugin, creates action area,
        builds content panels via view_builder, and sets up sidebar.
        """
        view_builder.setup_window_geometry(self)
        layout: view_builder.MainLayout = view_builder.create_layout_structure(
            self, self.style.colors.bg
        )
        layout.sidebar.configure(bootstyle=self.side_color)
        preview_plugin = next(
            (
                p
                for p in self.container.plugins.get_active_plugins()
                if p.manifest.get("key") == "preview"
            ),
            None,
        )
        if preview_plugin:
            self.preview = cast(
                PreviewPanel, preview_plugin.create_ui(layout.main_pane)
            )
        else:
            self.preview = cast(PreviewPanel, ttk.Frame(layout.main_pane))
            CopyLabel(
                self.preview, text="Critical Error: Preview Plugin not found."
            ).pack()
            logger.error("Could not find and load the core 'preview' plugin.")
        layout.main_pane.add(self.preview, minsize=200)
        actions = view_builder.create_action_area(
            layout.action_bar,
            callbacks=SimpleNamespace(
                cmd_suggestions=self.command_controller.get_suggestions,
                cmd_submit=self._on_command_submit,
                on_search=self._on_search,
                open_history=self._open_history,
                queue_add=self.trigger_add_to_queue,
                stop=self.trigger_stop_generation,
                generate=self.trigger_generation,
            ),
            texts={
                "history": i18n.get("btn.history"),
                "queue": i18n.get("btn.add_to_queue"),
                "stop": i18n.get("btn.stop"),
                "generate": i18n.get("btn.generate"),
            },
        )
        self.container.on_network_param_change = self._on_network_param_change
        panels_data = view_builder.build_panels(
            layout.content_frame,
            self.container,
            self.state_manager,
            callbacks=SimpleNamespace(
                presenter_proxy=SimpleNamespace(
                    on_request_stop_queue=self.trigger_stop_queue,
                    load_parameters=self.load_parameters,
                    execution_manager=self.execution_manager,
                    models=self.models,
                    loras=self.loras,
                    embeddings=self.embeddings,
                ),
                runner=self.runner,
                execution_manager=self.execution_manager,
            ),
            execution_manager=self.execution_manager,
        )
        sb_data = view_builder.create_sidebar_buttons(
            layout.sidebar,
            list(panels_data.categories_map.keys()),
            self.cmd_loader,
            callbacks=SimpleNamespace(
                toggle_sidebar=self._toggle_sidebar,
                select_category=self.select_category,
                open_remote=self._open_remote,
                toggle_theme=self._toggle_theme,
                theme_tooltip_text=i18n.get("app.theme_tooltip"),
            ),
            side_color=self.side_color,
            plugin_manager=self.container.plugins,
        )
        self.ui_refs = view_builder.UIReferences(
            sidebar=sb_data, layout=layout, action=actions, panels=panels_data
        )
        self._setup_network_triggers()
        self.after(
            200,
            lambda: restore_sash(
                self.settings, "main", self.ui_refs.layout.main_pane
            ),
        )
        initial_cat = (
            self.settings.get("active_category", default=None) or "general"
        )
        self.select_category(initial_cat)

    def _setup_network_triggers(self) -> None:
        """
        Binds automatic trigger appending for LoRA and Embeddings.
        Logic: Adds trace listeners to 'add triggers' variables to update
        state manager.
        """
        if not self.ui_refs.panels.lora or not self.ui_refs.panels.embedding:
            return

        def add_lora_trigger(*_):
            val = self.ui_refs.panels.lora.var_add_triggers.get()
            self.state_manager.append_triggers("lora", val)

        def add_embed_trigger(*_):
            val = self.ui_refs.panels.embedding.var_add_triggers.get()
            self.state_manager.append_triggers("embedding", val)

        self.ui_refs.panels.lora.var_add_triggers.trace_add(
            "write", add_lora_trigger
        )
        self.ui_refs.panels.embedding.var_add_triggers.trace_add(
            "write", add_embed_trigger
        )

    def trigger_generation(self) -> None:
        """Initiates the generation process using the current state."""
        self.execution_manager.start_generation(self.generation_state)

    def trigger_add_to_queue(self) -> None:
        """Adds the current generation state as a new task in the queue."""
        self.execution_manager.add_to_queue(self.generation_state)

    def trigger_stop_generation(self) -> None:
        """Requests an immediate stop of the current generation process."""
        self.execution_manager.stop_generation()

    def trigger_stop_queue(self) -> None:
        """Logic: Stops queue via execution manager."""
        self.execution_manager.stop_queue_processing()

    def _on_command_submit(self, tokens: List[str]) -> None:
        """
        Delegates command submission to logic handler.
        Logic: Processes command bar input (generate, clear, model switch,
        param update).
        """
        res = logic_handlers.handle_command_submit(
            tokens,
            self.command_controller,
            self.state_manager,
            self.arg_processor,
            self.models,
            self.ui_refs.panels.general.reset,
        )
        if res == "TRIGGER_GENERATE":
            self.trigger_generation()
        elif res == "TRIGGER_CLEAR":
            pass
        elif res:
            self._on_model_selected(res)
        self.ui_refs.action.command_bar.clear()

    def _on_network_param_change(
        self, net_type: str, name: str, value: Any = None, enabled: bool = False
    ) -> None:
        """Logic: Updates state for network parameter changes."""
        logic_handlers.handle_network_change(
            net_type, name, value, enabled, self.state_manager
        )

    def _on_model_selected(self, model_id: Optional[str]) -> None:
        """
        Coordinate model change between Logic and UI.
        Logic: Updates state model_id, configures parameters for model,
        updates UI panels, and syncs network filters.
        """
        if model_id and self.generation_state.model_id != model_id:
            model_data = self.models.get_model(model_id)
            if not model_data:
                logger.error(f"Model {model_id} not found in database.")
                return

            self.generation_state.model_id = model_id
            model_data = self.models.get_model(model_id)
            base_model = model_data.get("base_model") if model_data else None
            keep_params = self.ui_refs.panels.general.var_keep_params.get()
            active_config = logic_handlers.configure_state_for_model(
                model_id, self.models, self.state_manager, keep_params
            )
            self.ui_refs.panels.general.select_model_by_id(model_id)
            self.ui_refs.panels.lora.set_base_model_filter(base_model)
            self.ui_refs.panels.embedding.set_base_model_filter(base_model)
            self._sync_network_views()
            if not keep_params:
                self.ui_refs.panels.general.clear_dynamic_params()
                for flag, value, enabled in active_config:
                    if flag not in self.ui_refs.panels.general.preset_controls:
                        self.ui_refs.panels.general.add_dynamic_param(
                            flag, value, enabled
                        )
            self.state_manager.set_overriden_controls(
                self.ui_refs.panels.general.preset_controls
            )

    def select_category(self, cat_name: str) -> None:
        """
        Switches the main content view.

        Logic: Updates UI to show selected category panel, updates
        sidebar buttons, and persists selection.
        """
        if cat_name == "remote":
            self._open_remote()
            return

        if (
            cat_name not in self.ui_refs.panels.categories_map
            or not self.ui_refs.panels.categories_map[cat_name]
        ):
            return
        self.current_category = cat_name
        self.settings.set_str("active_category", cat_name)
        self.ui_refs.action.command_bar.clear()
        for name, btn in self.ui_refs.sidebar.buttons.items():
            style = "primary" if name == cat_name else self.side_color
            btn.configure(bootstyle=style, variant="filled")
        content_frame = self.ui_refs.layout.content_frame
        for child in content_frame.winfo_children():
            if hasattr(child, "pack_forget"):
                child.pack_forget()
        label_txt = cat_name
        found = False
        if hasattr(self.container, "plugins"):
            for p in self.container.plugins.get_active_plugins():
                p_key = p.manifest.get("key", "").lower()
                if p_key == cat_name or f"{p_key}_{id(p)}" == cat_name:
                    label_txt = p.manifest.get("name", cat_name)
                    found = True
                    break
        if not found:
            label_txt = self.cmd_loader.get_category_label(cat_name)
        CopyLabel(
            content_frame,
            text=label_txt,
            font=(SYSTEM_FONT, 16, "bold"),
            bootstyle="primary",
        ).pack(fill=tk.X, pady=(0, 20))
        for w in self.ui_refs.panels.categories_map[cat_name]:
            w.pack(fill=tk.X, pady=2, padx=(5, 15), expand=False)
        content_frame.yview_moveto(0)

    def _toggle_sidebar(self) -> None:
        """
        Logic: Toggles sidebar width and button labels (Icon only
        vs Icon+Text).
        """
        self.sidebar_expanded = not self.sidebar_expanded
        width = 200 if self.sidebar_expanded else 46
        self.ui_refs.layout.sidebar.configure(width=width)
        for name, btn in self.ui_refs.sidebar.buttons.items():
            icon = "🔧"
            label = name
            found = False
            if hasattr(self.container, "plugins"):
                for p in self.container.plugins.get_active_plugins():
                    p_key = p.manifest.get("key", "").lower()
                    if p_key == name or f"{p_key}_{id(p)}" == name:
                        icon = p.manifest.get("icon", "🧩")
                        label = p.manifest.get("name", name)
                        found = True
                        break
            if not found:
                icon = self.cmd_loader.get_icon(name, "🔧")
                label = self.cmd_loader.get_category_label(name)
            if self.sidebar_expanded:
                btn.configure(
                    width=None, text=f" {icon} {label}", font=(EMOJI_FONT, 8)
                )
            else:
                btn.configure(width=32, text=icon, font=(EMOJI_FONT, 14))
        t_icon = self.cmd_loader.get_icon("theme", "🎨")
        t_label = i18n.get("app.theme_tooltip")
        t_btn = self.ui_refs.sidebar.btn_theme
        if self.sidebar_expanded:
            t_btn.configure(
                width=None, text=f" {t_icon} {t_label}", font=(EMOJI_FONT, 8)
            )
        else:
            t_btn.configure(width=32, text=t_icon, font=(EMOJI_FONT, 14))

    def _toggle_theme(self) -> None:
        """
        Logic: Cycles to next theme, clears texture cache,
        and refreshes UI style.
        """
        TextureAtlas.clear_cache()
        self.theme_id = (self.theme_id + 1) % len(self.themes)
        name = self.themes[self.theme_id]
        self.settings.set("theme", name)
        try:
            self.side_color = themes.USER_THEMES[name]["type"]
            self.style.theme_use(name)
            logger.info(f"Successfully applied theme: {name}")
        except Exception as e:
            logger.warning(
                "Failed to apply theme '%s': %s. "
                "Falling back to default theme.",
                name,
                e,
            )
            try:
                self.style.theme_use("cosmo")
                self.side_color = "light"
            except Exception as e2:
                logger.error(f"Failed to apply fallback theme: {e2}")
                self.style.theme_use("litera")
                self.side_color = "light"

        self.ui_refs.layout.sidebar.configure(bootstyle=self.side_color)
        self.ui_refs.sidebar.btn_toggle.configure(bootstyle=self.side_color)
        self.ui_refs.layout.main_pane.configure(background=self.style.colors.bg)
        self.select_category(self.current_category or "general")

    def _on_search(self, query: str) -> None:
        """Dynamic UI search filtering.

        Logic: Filters visible controls in the content frame based
        on search query.
        """
        query = query.lower()
        content = self.ui_refs.layout.content_frame
        if not query:
            if self.current_category:
                self.select_category(self.current_category)
            return
        for child in content.winfo_children():
            if hasattr(child, "pack_forget"):
                child.pack_forget()
        CopyLabel(
            content,
            text=f"{i18n.get('search.results_for')} '{query}'",
            font=(SYSTEM_FONT, 12, "italic"),
        ).pack(fill=tk.X, pady=(0, 10))
        hits = 0
        for _, controls in self.state_manager.controls.items():
            ctrl = next(iter(controls), None)
            if not ctrl:
                continue
            desc = (
                ctrl.description.lower() if hasattr(ctrl, "description") else ""
            )
            match_txt = f"{ctrl.name} {ctrl.flag} {desc}".lower()
            if query in match_txt:
                for c in controls:
                    if c.winfo_manager() != "grid":
                        c.pack(fill=tk.X, pady=2, padx=(5, 15))
                hits += 1
        if hits == 0:
            CopyLabel(
                content,
                text=i18n.get("search.no_results"),
                bootstyle="secondary",
                anchor="center",
            ).pack(pady=20)

    def _setup_subscribers(self) -> None:
        """
        Logic: Subscribes to application events (generation, logging,
        progress, model selection).
        """
        EventBus.subscribe(
            CHANNEL_APP_EVENTS, str(id(self)), self._on_app_event
        )
        EventBus.subscribe("log_message", str(id(self)), self._on_log_message)
        EventBus.subscribe(
            "execution_progress", str(id(self)), self._on_progress
        )
        EventBus.subscribe(
            "generation_failure", str(id(self)), self._on_failure
        )
        EventBus.subscribe(
            "generation_success", str(id(self)), self._on_success
        )
        EventBus.subscribe(
            MSG_MODEL_SELECTED,
            "coordinator",
            lambda d: self._on_model_selected(d),
        )
        self.state_manager.add_listener(self._on_state_changed)

    def _on_app_event(self, event_data: Dict[str, Any]) -> None:
        """Logic: Schedules handling of app events on main thread."""
        self.after(0, lambda: self._handle_app_event_safe(event_data))

    def _handle_app_event_safe(self, event_data: Dict[str, Any]) -> None:
        """Logic: Updates UI state based on app events (run/stop, import)."""
        msg_type = event_data.get("type")
        if msg_type in [MSG_GENERATION_STARTED, MSG_QUEUE_PROCESSING_STARTED]:
            self._update_run_state(True)
        elif msg_type in [
            MSG_GENERATION_FINISHED,
            MSG_QUEUE_PROCESSING_STOPPED,
        ]:
            self._update_run_state(False)
        elif msg_type == MSG_DATA_IMPORTED:
            payload = event_data.get("payload", {})
            self._refresh_lists(payload.get("data_type"))

    def _update_run_state(self, is_running: bool) -> None:
        """
        Enables/Disables buttons based on running state.
        Logic: Toggles Generate/Stop buttons. Queue button remains enabled.
        """

        self.ui_refs.action.btn_queue.config(state="normal")
        can_stop = is_running or ServerProcessManager().is_running()
        if can_stop:
            self.ui_refs.action.btn_stop.config(state="normal")
        else:
            self.ui_refs.action.btn_stop.config(state="disabled")

        if is_running:
            self.ui_refs.action.btn_run.config(state="disabled")
        else:
            self.ui_refs.action.btn_run.config(state="normal")
            is_server = (
                ServerProcessManager().is_running()
                and self.settings.get("execution_mode") != "cli_only"
            )
            text = (
                i18n.get("btn.send", "✉️ Send")
                if is_server
                else i18n.get("btn.generate", "✨ Generate")
            )
            self.ui_refs.action.btn_run.configure(text=text)

    def _on_state_changed(self, event_type: str, key: str, value: Any) -> None:
        """
        Syncs StateManager changes back to specific UI elements.
        Logic: Updates UI prompt fields from state and schedules persistent
        settings save.
        """
        if event_type == "prompt":
            with self.state_manager.programmatic_update():
                if key == "prompt":
                    self.ui_refs.panels.general.set_prompt(str(value or ""))
                elif key == "negative_prompt":
                    self.ui_refs.panels.general.set_negative_prompt(
                        str(value or "")
                    )
        if self._persistent_job:
            self.after_cancel(self._persistent_job)
        full_state = self.generation_state.get_full_state()
        self._persistent_job = self.after(
            1000,
            lambda: self._save_persistent_settings_now(
                dict(full_state.get("parameters", {}))
            ),
        )
        self.container.autocomplete.on_state_change(
            event_type=event_type, key=key, value=value
        )
        if hasattr(self.preview, "sync_with_state"):
            self.preview.sync_with_state(full_state)

    def _sync_network_views(self) -> None:
        """
        Forces the LoRA and Embedding panels to redraw based on current state.

        Logic: Syncs LoRA and Embedding panel widgets with current state.
        """
        state = self.generation_state.get_full_state()
        self.ui_refs.panels.lora.sync_with_state(state)
        self.ui_refs.panels.embedding.sync_with_state(state)

    def _on_success(self, data: Dict[str, Any]) -> None:
        """
        Logic: Saves history entry with rich metadata and displays
        generated image.
        """
        used_networks = []
        state = self.generation_state
        for name, lora in state.loras.items():
            used_networks.append(
                {
                    "type": "lora",
                    "original_name": name,
                    "content_hash": lora.content_hash,
                    "remote_version_id": lora.remote_version_id,
                    "strength": lora.strength,
                    "triggers": lora.triggers,
                }
            )
        for name, emb in state.embeddings.items():
            used_networks.append(
                {
                    "type": "embedding",
                    "original_name": name,
                    "content_hash": emb.content_hash,
                    "remote_version_id": emb.remote_version_id,
                    "strength": emb.strength,
                    "target": emb.target,
                }
            )
        self.history.add_entry(
            model_id=data["model_id"],
            prompt=data["prompt"],
            compiled_params=data["params"],
            output_path=data["result"]["files"],
            metadata={
                "seed": data["result"]["seed"],
                "time_ms": data["result"]["generation_time"],
                "used_networks": used_networks,
            },
        )
        if files := data.get("result", {}).get("files", []):
            self.show_preview_image(files[0])
            self.set_status_success()

    def show_preview_image(self, path: str) -> None:
        """Logic: Shows image in preview panel."""
        self.preview.show_image(path)

    def set_status_success(self) -> None:
        """Logic: Sets success status in preview panel."""
        self.preview.set_status(i18n.get("status.success"), "success")

    def _on_failure(self, data: Any) -> None:
        """Logic: Displays error status and log."""
        result = data.get("result", {})
        error_msg = result.get("error", i18n.get("status.error"))
        self.preview.set_status(f"Error: {error_msg}", "danger")
        self.preview.set_progress(0)
        self.preview.log(f"Generation Failed: {error_msg}", "ERROR")

    def _on_progress(self, data: dict) -> None:
        """Logic: Updates progress bar and status in preview panel."""
        current, total = (data.get("current", 0), data.get("total", 0))
        if total > 0:
            self.preview.set_progress(current / total * 100)
            msg = i18n.get("status.generating")
            self.preview.set_status(f"{msg} {current}/{total}", "info")
            if self.execution_manager.preview_path:
                self.preview.show_image(self.execution_manager.preview_path)
        else:
            self.preview.set_progress(0)

    def _on_log_message(self, data: dict) -> None:
        """
        Logic: appends log message to console and updates status bar
        based on content.
        """
        text = data.get("text", "")
        self.preview.log(text, data.get("level", "RAW"))
        lower_text = text.lower()
        if "loading model" in lower_text:
            self.preview.set_status(
                f"{i18n.get('status.loading')} Model", "info"
            )
        elif "loading lora" in lower_text:
            self.preview.set_status(
                f"{i18n.get('status.loading')} LoRA", "info"
            )
        elif "lora" in lower_text and "applied" in lower_text:
            self.preview.set_status("LoRA Applied", "success")
            self.preview.set_progress(0)
        elif "loading tensors completed" in lower_text:
            self.preview.set_status("Model Loaded", "success")
            self.preview.set_progress(0)
        elif "total params memory size" in lower_text:
            self.preview.set_status("VRAM Configured", "info")
        elif "ucache skipped" in lower_text:
            self.preview.set_status("UCache Active", "success")
        elif "seed" in data:
            self.preview.set_status(
                f"{i18n.get('status.generating')} Seed {data.get('seed')}",
                "info",
            )

    def load_parameters(self, prompt: str, item_data: Dict[str, Any]) -> None:
        """
        Restores the entire application state (model, prompts, params, networks)
        from a history or queue item.

        Args:
            prompt: The positive prompt string.
            item_data: Dictionary containing compiled_params and metadata.
        """
        model_id = item_data.get("model_id", "")
        if model_id:
            self._on_model_selected(model_id)
        restored = self.arg_processor.restore_from_args(
            model_id=model_id,
            prompt=prompt,
            compiled_params=item_data.get("compiled_params", []),
            metadata=item_data.get("metadata", {}),
        )
        self.state_manager.restore_state(restored)
        self._sync_network_views()

    def _open_history(self) -> None:
        """Logic: Opens history window."""
        self.history_presenter.open_window(self)

    def _load_history_session(self, uuid: str) -> None:
        """Logic: Loads a history session by UUID."""
        history_item = self.history.get(uuid)
        if history_item:
            self.load_parameters(history_item.get("prompt", ""), history_item)
            img_path = history_item.get("output_path")
            if isinstance(img_path, list) and img_path:
                self.preview.show_image(img_path[0])

    def _open_remote(self) -> None:
        """
        Logic: Opens remote model browser.
        Updated to use Plugin logic instead of direct instantiation.
        """

        if hasattr(self.container, "plugins"):
            for plugin in self.container.plugins.get_active_plugins():
                if plugin.manifest.get("key") == "remote":
                    if hasattr(plugin, "open_window"):
                        plugin.open_window(self)
                    break

    def on_close(self) -> None:
        """
        Cleanup and shutdown.

        Logic: Saves window state, persists settings, stops server,
        and destroys window.
        """
        try:
            if (
                hasattr(self, "ui_refs")
                and self.ui_refs.layout.main_pane.winfo_exists()
            ):
                save_sash_position(
                    self.settings, "main", self.ui_refs.layout.main_pane
                )
            if hasattr(self, "preview") and self.preview.winfo_exists():
                save_sash_position(self.settings, "preview", self.preview)
        except (tk.TclError, IndexError, KeyError, AttributeError):
            pass
        logger.info("Shutting down application...")
        self._save_persistent_settings_now(
            self.generation_state.get_full_state().get("parameters", {})
        )
        ServerProcessManager().stop()
        self.quit()

    def _save_persistent_settings_now(self, parameters: Dict[str, Any]) -> None:
        """Logic: Saves persistent parameters to settings DB."""
        settings = []
        persistent_flags = self.arg_processor.get_persistent_flags()
        for flag in persistent_flags:
            value = parameters.get(flag)
            key = f"persistent_ctrl_{flag}"
            key_value = f"{key}_value"
            if self.settings_dict.get(key_value) != value:
                self.settings_dict[key_value] = value
                settings.append({"key": key_value, "value": value})
            key_enabled = f"{key}_enabled"
            enabled = flag in parameters
            if self.settings_dict.get(key_enabled) != enabled:
                self.settings_dict[key_enabled] = enabled
                settings.append({"key": key_enabled, "value": enabled})
        if settings:
            self.settings.set_bulk(settings)

    def _load_persistent_settings(self) -> None:
        """Logic: Loads persistent parameters from settings DB into state."""
        for flag in self.cmd_loader.get_all_flags():
            key = f"persistent_ctrl_{flag}"
            val = self.settings.get(f"{key}_value", default=None)
            enabled = self.settings.get(f"{key}_enabled", default=None)
            self.settings_dict[f"{key}_value"] = val
            self.settings_dict[f"{key}_enabled"] = enabled
            if val is not None and enabled is not None:
                is_enabled = str(enabled).lower() in ("true", "1", "yes")
                self.state_manager.set_control_values(flag, val, is_enabled)
                self.state_manager.update_parameter(flag, val, is_enabled)

    def _load_initial_data(self) -> None:
        """Populates models and lists on startup.

        Logic: Refreshes lists and selects initial model."""
        names = self.ui_refs.panels.general.refresh_models_list()
        self.ui_refs.panels.lora.refresh_list()
        self.ui_refs.panels.embedding.refresh_list()
        if names:
            self.ui_refs.panels.general.combo_models.current(0)
            mid = self.ui_refs.panels.general.list_map.get(names[0])
            if mid:
                EventBus.publish(MSG_MODEL_SELECTED, mid)
                self.ui_refs.panels.general.combo_models.set(names[0])

    def _refresh_lists(self, data_type: Optional[str]) -> None:
        """Refreshes specific UI lists after import.

        Logic: Refreshes specific panels based on imported data type."""
        if data_type == "Models":
            assert self.ui_refs.panels.general is not None
            self.ui_refs.panels.general.refresh_models_list()
        elif data_type == "LoRAs":
            assert self.ui_refs.panels.lora is not None
            self.ui_refs.panels.lora.refresh_list()
        elif data_type == "Embeddings":
            assert self.ui_refs.panels.embedding is not None
            self.ui_refs.panels.embedding.refresh_list()
        else:
            self._load_initial_data()

    def place_window_center(self) -> None:
        """Logic: Centers the main window."""
        center_window(self, self, 1100, 800)
