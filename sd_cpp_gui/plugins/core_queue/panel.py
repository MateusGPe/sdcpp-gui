"""
Queue Panel - Plugin Version
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any, Callable, Dict

import ttkbootstrap as tb

from sd_cpp_gui.constants import CORNER_RADIUS, EMOJI_FONT, SYSTEM_FONT
from sd_cpp_gui.data.db.models import QueueData
from sd_cpp_gui.infrastructure.i18n import I18nManager, get_i18n
from sd_cpp_gui.ui.components import flat
from sd_cpp_gui.ui.components.utils import CopyLabel

i18n: I18nManager = get_i18n()


class QueueItem(ttk.Frame):
    """
    A single item slot in the queue list.
    Designed for View Recycling: The widget instance remains, but data changes.
    """

    def __init__(
        self,
        master: ttk.Frame,
        execution_manager,
        model_manager,
        on_load_params: Callable[[str, Dict[str, Any]], None],
        queue_item: QueueData,
        is_first: bool,
        is_last: bool,
        on_delete: Callable[[str], None],
        on_move_up: Callable[[str], None],
        on_move_down: Callable[[str], None],
        **kwargs: Any,
    ) -> None:
        """Logic: Initializes queue item widget."""
        super().__init__(master, padding=5, **kwargs)
        self.execution_manager = execution_manager
        self.model_manager = model_manager
        self.on_load_params = on_load_params
        self.item_data = queue_item
        self.on_delete = on_delete
        self.on_move_up = on_move_up
        self.on_move_down = on_move_down
        self.columnconfigure(2, weight=1)
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.grid(row=0, column=0, padx=(0, 5), sticky="ns")
        self.btn_up = flat.RoundedButton(
            ctrl_frame,
            text="▲",
            width=20,
            height=20,
            elevation=0,
            corner_radius=CORNER_RADIUS,
            font=(EMOJI_FONT, 8),
            bootstyle="secondary",
            command=lambda: self.on_move_up(self.item_data["uuid"]),
            state="disabled" if is_first else "normal",
        )
        self.btn_up.pack(side="top", pady=(1, 2))
        self.btn_down = flat.RoundedButton(
            ctrl_frame,
            text="▼",
            width=20,
            height=20,
            elevation=0,
            corner_radius=CORNER_RADIUS,
            font=(EMOJI_FONT, 8),
            bootstyle="secondary",
            command=lambda: self.on_move_down(self.item_data["uuid"]),
            state="disabled" if is_last else "normal",
        )
        self.btn_down.pack(side="bottom", pady=1)
        self.lbl_status = CopyLabel(
            self, text="", font=(SYSTEM_FONT, 8, "bold"), padding=(5, 2)
        )
        self.lbl_status.grid(row=0, column=1, padx=5, sticky="w")
        info_frame = ttk.Frame(self)
        info_frame.grid(row=0, column=2, sticky="ew", padx=5)
        self.lbl_model = CopyLabel(
            info_frame, text="", font=(SYSTEM_FONT, 10, "bold")
        )
        self.lbl_model.pack(anchor="w")
        self.lbl_prompt = CopyLabel(
            info_frame,
            text="",
            font=(SYSTEM_FONT, 9),
            foreground="#888",
            wraplength=400,
        )
        self.lbl_prompt.pack(anchor="w", fill="x")
        self.delete_btn = flat.RoundedButton(
            self,
            text="🗑️",
            width=32,
            height=32,
            corner_radius=CORNER_RADIUS,
            font=(EMOJI_FONT, 12),
            bootstyle="danger",
            command=lambda: self.on_delete(self.item_data["uuid"]),
            elevation=0,
        )
        self.delete_btn.grid(row=0, column=3, padx=5, sticky="e")
        self.bind("<Double-1>", self._on_double_click)
        for child in info_frame.winfo_children():
            child.bind("<Double-1>", self._on_double_click)
        self.update_item(queue_item, is_first, is_last)

    def _change_color(self, pcolor: str, mcolor: str) -> None:
        """Logic: Changes color."""
        if not self.winfo_exists():
            return
        self.lbl_prompt.configure(foreground=pcolor)
        self.lbl_model.configure(foreground=mcolor)

    def _on_double_click(self, _event: Any = None) -> None:
        """Logic: Handles double click."""
        self.on_load_params(self.item_data["prompt"], self.item_data)
        if not self.winfo_exists():
            return
        original_colors = {
            "pcolor": self.lbl_prompt.cget("foreground"),
            "mcolor": self.lbl_model.cget("foreground"),
        }
        try:
            colors = tb.Style.get_instance().colors
            new_color = {"pcolor": colors.selectfg, "mcolor": colors.active}
        except Exception:
            new_color = {"pcolor": "gray", "mcolor": "lightblue"}
        self._change_color(**new_color)
        self.after(200, lambda: self._change_color(**original_colors))

    def update_item(
        self, queue_item: QueueData, is_first: bool, is_last: bool
    ) -> None:
        """Updates the widget slot with new data (View Recycling).

        Logic: Updates item data."""
        self.item_data = queue_item
        state_up = "disabled" if is_first else "normal"
        self.btn_up.configure(state=state_up)

        state_down = "disabled" if is_last else "normal"
        self.btn_down.configure(state=state_down)

        s = self.item_data["status"]
        status_color = "secondary"
        if s == "running":
            status_color = "warning"
        elif s == "done":
            status_color = "success"
        elif s == "failed":
            status_color = "danger"
        new_status_text = i18n.get(f"queue.status.{s}", s.upper())
        if self.lbl_status.cget("text") != new_status_text:
            self.lbl_status.configure(
                text=new_status_text, bootstyle=f"{status_color}-inverse"
            )
        else:
            self.lbl_status.configure(bootstyle=f"{status_color}-inverse")
        model = self.model_manager.get_model(self.item_data["model_id"])
        model_name = model["name"] if model else "Unknown Model"
        if self.lbl_model.cget("text") != model_name:
            self.lbl_model.configure(text=model_name)
        prompt_preview = self.item_data["prompt"].replace("\n", " ")
        if len(prompt_preview) > 100:
            prompt_preview = prompt_preview[:100] + "..."
        if self.lbl_prompt.cget("text") != prompt_preview:
            self.lbl_prompt.configure(text=prompt_preview)


class QueuePanel(ttk.Frame):
    """Panel for managing the generation queue."""

    def __init__(
        self,
        master: ttk.Frame,
        execution_manager,
        model_manager,
        on_load_params: Callable[[str, Dict[str, Any]], None],
    ) -> None:
        """Logic: Initializes queue panel."""
        super().__init__(master)
        self.execution_manager = execution_manager
        self.model_manager = model_manager
        self.on_load_params = on_load_params
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        controls_frame = ttk.Frame(self)
        controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        controls_frame.columnconfigure((0, 1, 2), weight=1)
        self.btn_start = flat.RoundedButton(
            controls_frame,
            text=i18n.get("queue.start", "Start Queue"),
            command=self.start_queue,
            bootstyle="success",
            height=40,
            corner_radius=CORNER_RADIUS,
        )
        self.btn_start.grid(row=0, column=0, padx=5, sticky="ew")
        self.btn_stop = flat.RoundedButton(
            controls_frame,
            text=i18n.get("queue.stop", "Stop Queue"),
            command=self.stop_queue,
            state="disabled",
            bootstyle="danger",
            height=40,
            corner_radius=CORNER_RADIUS,
        )
        self.btn_stop.grid(row=0, column=1, padx=5, sticky="ew")
        self.btn_clear = flat.RoundedButton(
            controls_frame,
            text=i18n.get("queue.clear", "Clear Queue"),
            command=self.clear_queue,
            bootstyle="warning",
            height=40,
            corner_radius=CORNER_RADIUS,
        )
        self.btn_clear.grid(row=0, column=2, padx=5, sticky="ew")
        self.queue_list_frame = ttk.Frame(self)
        self.queue_list_frame.grid(
            row=1, column=0, padx=10, pady=(0, 10), sticky="nsew"
        )
        self.execution_manager.queue_manager.subscribe(self.on_queue_update)
        self.after(100, self.refresh_queue_list)

    def destroy(self) -> None:
        """Unsubscribe from queue updates when the widget is destroyed.

        Logic: Cleans up."""
        if hasattr(self.execution_manager, "queue_manager"):
            self.execution_manager.queue_manager.unsubscribe(
                self.on_queue_update
            )
        super().destroy()

    def on_queue_update(self) -> None:
        """
        Callback from QueueManager. Schedules a refresh on the main thread
        to ensure thread safety.

        Logic: Handles queue update.
        """
        if self.winfo_exists():
            self.after(0, self.refresh_queue_list)

    def start_queue(self) -> None:
        """Logic: Starts queue."""
        self.execution_manager.start_queue_processing()

    def stop_queue(self) -> None:
        """Logic: Stops queue."""
        self.execution_manager.stop_queue_processing(clear_queue=False)

    def clear_queue(self) -> None:
        """Logic: Clears queue."""
        self.execution_manager.stop_queue_processing(clear_queue=True)

    def _delete_item(self, uuid: str) -> None:
        """Logic: Deletes item."""
        self.execution_manager.queue_manager.remove(uuid)

    def _move_item(self, uuid: str, direction: int) -> None:
        """Logic: Moves item."""
        items = self.execution_manager.queue_manager.get_all()
        idx = next((i for i, x in enumerate(items) if x["uuid"] == uuid), -1)
        if idx == -1:
            return

        new_idx = idx + direction
        if 0 <= new_idx < len(items):
            if direction < 0:
                target_priority = items[new_idx]["priority"]
                self.execution_manager.queue_manager.reorder(
                    uuid, target_priority
                )
            else:
                neighbor_uuid = items[new_idx]["uuid"]
                target_priority = items[idx]["priority"]
                self.execution_manager.queue_manager.reorder(
                    neighbor_uuid, target_priority
                )

    def refresh_queue_list(self) -> None:
        """
        Refresh using View Recycling (Slot Pattern).
        Widgets are reused and only their content is updated to match
        the queue order.

        Logic: Refreshes list.
        """
        queue_items = self.execution_manager.queue_manager.get_all()
        is_processing = self.execution_manager.processing_queue
        self.btn_start.configure(
            state="disabled" if is_processing else "normal"
        )
        self.btn_stop.configure(state="normal" if is_processing else "disabled")
        self.btn_clear.configure(
            state="normal"
            if queue_items and (not is_processing)
            else "disabled"
        )
        current_slots = [
            w
            for w in self.queue_list_frame.winfo_children()
            if isinstance(w, QueueItem)
        ]
        num_items = len(queue_items)
        num_slots = len(current_slots)
        if num_slots < num_items:
            for i in range(num_slots, num_items):
                new_slot = QueueItem(
                    self.queue_list_frame,
                    self.execution_manager,
                    self.model_manager,
                    self.on_load_params,
                    queue_items[i],
                    is_first=i == 0,
                    is_last=i == num_items - 1,
                    on_delete=self._delete_item,
                    on_move_up=lambda u: self._move_item(u, -1),
                    on_move_down=lambda u: self._move_item(u, 1),
                )
                new_slot.pack(fill="x", expand=True, padx=5, pady=2)
                current_slots.append(new_slot)
        elif num_slots > num_items:
            for i in range(num_slots - 1, num_items - 1, -1):
                slot_to_remove = current_slots.pop()
                slot_to_remove.destroy()
        for index, item_data in enumerate(queue_items):
            slot = current_slots[index]
            slot.update_item(
                item_data, is_first=index == 0, is_last=index == num_items - 1
            )
