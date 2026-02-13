"""
Functional UI Construction.
Handles the creation of widgets, layout configuration, and initial styling.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from tkinter import messagebox
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.widgets import ToolTip
from ttkbootstrap.widgets.scrolled import ScrolledFrame

from sd_cpp_gui.constants import CORNER_RADIUS, EMOJI_FONT
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.command_bar import CommandBar
from sd_cpp_gui.ui.features.settings.system_panel import SystemPanel

logger = get_logger(__name__)


@dataclass
class MainLayout:
    """Type-safe return for layout structure."""

    sidebar: ttk.Frame
    main_pane: tk.PanedWindow
    content_frame: ScrolledFrame
    action_bar: ttk.Frame


@dataclass
class ActionArea:
    """Type-safe return for action bar widgets."""

    command_bar: CommandBar
    btn_run: flat.RoundedButton
    btn_stop: flat.RoundedButton
    btn_queue: flat.RoundedButton


@dataclass
class SidebarElements:
    """Type-safe return for sidebar widgets."""

    buttons: Dict[str, flat.RoundedButton]
    btn_theme: flat.RoundedButton
    btn_toggle: flat.RoundedButton


@dataclass
class PanelCollection:
    """Type-safe return for panel construction."""

    general: Optional[Any] = None
    lora: Optional[Any] = None
    embedding: Optional[Any] = None
    i2i: Optional[Any] = None
    system: Optional[SystemPanel] = None
    categories_map: Dict[str, List[tk.Widget]] = field(default_factory=dict)


@dataclass
class UIReferences:
    sidebar: SidebarElements
    layout: MainLayout
    action: ActionArea
    panels: PanelCollection


def setup_window_geometry(window: ttk.Window) -> None:
    """
    Configures the root window geometry and unbinds scroll events.

    Logic: Configures initial window size and unbinds default scroll
    events from comboboxes"""
    window.minsize(640, 640)
    window.geometry("1100x800")
    window.unbind_class("TCombobox", "<MouseWheel>")
    window.unbind_class("TCombobox", "<Button-4>")
    window.unbind_class("TCombobox", "<Button-5>")


def create_layout_structure(parent: tk.Widget, bg_color: str) -> MainLayout:
    """
    Creates the main PanedWindow and containers.
    Returns references to the structural frames.

    Logic: Builds the high-level container structure (sidebar, paned window,
    content area, action bar)
    """
    sidebar = ttk.Frame(parent, width=46, padding=0)
    sidebar.pack(side=tk.LEFT, fill=tk.Y)
    sidebar.pack_propagate(False)
    main_pane = tk.PanedWindow(parent, orient=tk.HORIZONTAL)
    main_pane.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
    main_pane.configure(borderwidth=0, background=bg_color)
    left_wrapper = ttk.Frame(main_pane, padding=(2, 10, 0, 0))
    main_pane.add(left_wrapper, minsize=384)
    content_frame = ScrolledFrame(left_wrapper, autohide=True)
    content_frame.pack(fill=tk.BOTH, expand=True)
    action_bar = ttk.Frame(left_wrapper, padding=(5, 10))
    action_bar.pack(side=tk.BOTTOM, fill=tk.X)
    action_bar.columnconfigure((0, 1, 2, 3), weight=1)
    return MainLayout(
        sidebar=sidebar,
        main_pane=main_pane,
        content_frame=content_frame,
        action_bar=action_bar,
    )


def build_panels(
    parent: ScrolledFrame,
    container: Any,
    state_manager: Any,
    callbacks: SimpleNamespace,
    execution_manager: Any,
) -> PanelCollection:
    """
    Instantiates all content panels by iterating through registered plugins
    and falling back to hardcoded panels for core functionality.
    Logic: Instantiates UI panels from plugins, the system panel, and dynamic
    command categories
    """
    panels = PanelCollection()
    categories: Dict[str, List[tk.Widget]] = {}
    if hasattr(container, "plugins"):
        for plugin in container.plugins.get_active_plugins():
            try:
                key = plugin.manifest.get("key", "").lower()
                if key == "preview":
                    continue
                widget = plugin.create_ui(parent)
                # if not widget:
                #     continue
                if not key:
                    key = f"plugin_{id(plugin)}"
                if key in ["general", "lora", "embedding", "i2i"]:
                    setattr(panels, key, widget)
                if key in categories:
                    key = f"{key}_{id(plugin)}"
                categories[key] = [widget] if widget else []
            except Exception as e:
                logger.error(
                    "Failed to load UI for plugin "
                    f"'{plugin.manifest.get('name')}': {e}"
                )
    system = SystemPanel(
        parent,
        container.settings,
        callbacks.runner,
        container.models,
        container.history,
        container.loras,
        container.embeddings,
        execution_manager,
    )
    categories["system"] = [system]
    panels.system = system
    raw_data = container.cmd_loader.get_categorized_commands()
    for cat_name, cmds_list in raw_data.items():
        if not cmds_list:
            continue
        widgets = []
        for cmd in cmds_list:
            ctrl = state_manager.new_argument_control(parent, cmd["flag"])
            if ctrl:
                widgets.append(ctrl)
        if widgets:
            categories[cat_name] = widgets
    panels.categories_map = categories
    return panels


def create_sidebar_buttons(
    sidebar: ttk.Frame,
    categories: List[str],
    cmd_loader: Any,
    callbacks: SimpleNamespace,
    side_color: str,
    plugin_manager: Any = None,
) -> SidebarElements:
    """
    Creates the sidebar navigation buttons.
    Returns references to buttons for updating text/style later.

    Logic: Generates navigation buttons for the sidebar based on categories
    and plugins, including theme and toggle controls
    """
    btn_toggle = flat.RoundedButton(
        sidebar,
        text="☰",
        width=32,
        height=32,
        corner_radius=CORNER_RADIUS,
        elevation=0,
        font=(EMOJI_FONT, 14),
        bootstyle=side_color,
        command=callbacks.toggle_sidebar,
    )
    btn_toggle.pack(pady=(5, 2), padx=0)
    ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5, padx=5)
    buttons = {}

    def _add_btn(cat_name: str, icon_default: str) -> bool:
        if cat_name not in categories:
            return False
        icon = icon_default
        label = cat_name
        is_plugin = False
        if plugin_manager:
            for p in plugin_manager.get_active_plugins():
                p_key = p.manifest.get("key", "").lower()
                if p_key == cat_name or f"{p_key}_{id(p)}" == cat_name:
                    icon = p.manifest.get("icon", icon_default)
                    label = p.manifest.get("name", cat_name)
                    is_plugin = True
                    break
        if not is_plugin:
            icon = cmd_loader.get_icon(cat_name, icon_default)
            label = cmd_loader.get_category_label(cat_name)
        btn = flat.RoundedButton(
            sidebar,
            text=icon,
            width=32,
            height=32,
            elevation=0,
            corner_radius=CORNER_RADIUS,
            font=(EMOJI_FONT, 14),
            bootstyle=side_color,
            command=lambda c=cat_name: callbacks.select_category(c),  # type: ignore
        )
        btn.pack(pady=2, padx=0)
        ToolTip(btn, text=label, bootstyle="dark")
        buttons[cat_name] = btn
        return True

    if _add_btn("general", "🏠"):
        ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=5, padx=5
        )

    if (
        _add_btn("img2img", "🖼️")
        | _add_btn("lora", "🔗")
        | _add_btn("embedding", "🧩")
    ):
        ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=5, padx=5
        )
    reserved = {"system"}
    reserved_list = {
        "general",
        "img2img",
        "lora",
        "embedding",
        "queue",
        "preview",
    }
    if plugin_manager:
        for p in plugin_manager.plugins_map.keys():
            if p in reserved_list:
                reserved.add(p)

    for cat in categories:
        if cat not in reserved:
            _add_btn(cat, "🔧")

    not_registered = reserved_list.difference(reserved)

    if not_registered:
        msg_text = ""
        for nr in not_registered:
            logger.warning("Core panel missing: %s", nr)
            msg_text += f"  • {nr}\n"

        msg_text = msg_text.strip()
        messagebox.showwarning(
            "Missing Panels",
            "The following core panels are missing and "
            "will not be available in the UI:\n"
            f"  {msg_text}",
        )

    ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5, padx=5)
    _add_btn("queue", "🕒")
    _add_btn("system", "⚙️")
    ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5, padx=5)
    btn_theme = flat.RoundedButton(
        sidebar,
        text=cmd_loader.get_icon("theme", "🎨"),
        width=32,
        height=32,
        corner_radius=CORNER_RADIUS,
        elevation=0,
        font=(EMOJI_FONT, 14),
        bootstyle=side_color,
        command=callbacks.toggle_theme,
    )
    btn_theme.pack(pady=1, padx=0, side="bottom")
    ToolTip(btn_theme, text=callbacks.theme_tooltip_text, bootstyle="dark")
    return SidebarElements(
        buttons=buttons, btn_theme=btn_theme, btn_toggle=btn_toggle
    )


def create_action_area(
    parent: ttk.Frame, callbacks: SimpleNamespace, texts: Dict[str, str]
) -> ActionArea:
    """Creates the Command Bar and Main Action Buttons (Run, Stop, Queue).
    Logic: Creates the command bar and main action buttons (Run, Stop, Queue,
    History)"""
    cmd_bar = CommandBar(
        parent,
        suggestion_callback=callbacks.cmd_suggestions,
        on_command=callbacks.cmd_submit,
        on_search_change=callbacks.on_search,
        height=40,
    )
    cmd_bar.grid(
        row=0, column=0, columnspan=4, sticky="ew", padx=2, pady=(0, 5)
    )
    btn_hist = flat.RoundedButton(
        parent,
        text=texts["history"],
        bootstyle="warning",
        command=callbacks.open_history,
        height=50,
        corner_radius=CORNER_RADIUS,
    )
    btn_hist.grid(row=1, column=0, sticky="ew", padx=2)
    btn_queue = flat.RoundedButton(
        parent,
        text=texts["queue"],
        bootstyle="primary",
        command=callbacks.queue_add,
        height=50,
        corner_radius=CORNER_RADIUS,
    )
    btn_queue.grid(row=1, column=1, sticky="ew", padx=2)
    btn_stop = flat.RoundedButton(
        parent,
        text=texts["stop"],
        bootstyle="danger",
        command=callbacks.stop,
        height=50,
        corner_radius=CORNER_RADIUS,
    )
    btn_stop.config(state="disabled")
    btn_stop.grid(row=1, column=2, sticky="ew", padx=2)
    btn_run = flat.RoundedButton(
        parent,
        text=texts["generate"],
        bootstyle="success",
        command=callbacks.generate,
        height=50,
        corner_radius=CORNER_RADIUS,
    )
    btn_run.grid(row=1, column=3, sticky="ew", padx=2)
    return ActionArea(
        command_bar=cmd_bar,
        btn_run=btn_run,
        btn_stop=btn_stop,
        btn_queue=btn_queue,
    )
