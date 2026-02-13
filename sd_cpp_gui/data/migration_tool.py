"""
Interactive Migration Tool: Backfill 'used_networks' and Fix Broken Links.

Features:
1. Scans History for LoRA/Embedding tags.
2. Matches them against the local library.
3. If a network is MISSING, opens a GUI to ask the user to map it to a new file.
4. Updates 'metadata.used_networks' (for UI display).
5. Updates 'prompt' text (renaming the tag <lora:old:1> to <lora:new:1>).
"""

import json
import re
import tkinter as tk
from typing import Any, Dict, List, Optional

import ttkbootstrap as ttk

from sd_cpp_gui.data.db.data_manager import (
    EmbeddingManager,
    HistoryManager,
    LoraManager,
)
from sd_cpp_gui.data.db.models import HistoryEntry
from sd_cpp_gui.infrastructure.logger import setup_logging
from sd_cpp_gui.ui.components.entry import MEntry
from sd_cpp_gui.ui.components.utils import CopyLabel

# Regex for LoRAs: <lora:NAME:STRENGTH>
LORA_PATTERN = re.compile(r"<lora:([^:]+):([+-]?\d*\.?\d+)>")


class NetworkResolverDialog(ttk.Toplevel):
    """
    Modal dialog to help the user resolve a missing network.
    """

    def __init__(
        self,
        parent,
        missing_name: str,
        network_type: str,
        available_items: List[str],
    ):
        """
        Initializes the dialog with missing network info and library items.
        """
        super().__init__(parent)
        self.title(f"Resolve Missing {network_type}")
        self.geometry("600x500")
        self.result: Optional[str] = None

        self.missing_name = missing_name
        self.available_items = available_items
        self.filtered_items = available_items

        self._init_ui()
        self._center_window(parent)

        self.transient(parent)
        self.grab_set()

        self.lift()
        self.focus_force()

    def _init_ui(self):
        """Builds the dialog UI components."""

        CopyLabel(
            self,
            text=f"Missing: '{self.missing_name}'",
            bootstyle="danger",
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=10)

        CopyLabel(
            self,
            text="Select the correct file from your library to map it:",
            bootstyle="secondary",
        ).pack(pady=(0, 5))

        self.var_search = tk.StringVar()
        self.var_search.trace("w", self._on_search)
        entry_search = MEntry(
            self, textvariable=self.var_search, bootstyle="info"
        )
        entry_search.pack(fill=tk.X, padx=10, pady=5)
        entry_search.bind("<Return>", lambda e: self._confirm())

        frame_list = ttk.Frame(self)
        frame_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.listbox = tk.Listbox(
            frame_list, height=15, selectmode=tk.SINGLE, font=("Consolas", 10)
        )
        sb = ttk.Scrollbar(
            frame_list, orient=tk.VERTICAL, command=self.listbox.yview
        )
        self.listbox.config(yscrollcommand=sb.set)

        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._refresh_list()

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(
            btn_frame,
            text="Skip (Leave as Ghost)",
            bootstyle="secondary",
            command=self._skip,
        ).pack(side=tk.LEFT)

        ttk.Button(
            btn_frame,
            text="Confirm Mapping",
            bootstyle="success",
            command=self._confirm,
        ).pack(side=tk.RIGHT)

    def _center_window(self, parent):
        """Centers the dialog relative to the parent window."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()

        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)

        if x < 0:
            x = (self.winfo_screenwidth() // 2) - (width // 2)
        if y < 0:
            y = (self.winfo_screenheight() // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def _on_search(self, *args):
        """Filters the listbox based on search query."""
        query = self.var_search.get().lower()
        if not query:
            self.filtered_items = self.available_items
        else:
            self.filtered_items = [
                item for item in self.available_items if query in item.lower()
            ]
        self._refresh_list()

    def _refresh_list(self):
        """Refreshes the listbox with filtered items."""
        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            self.listbox.insert(tk.END, item)

    def _confirm(self):
        """Confirms the selected mapping and closes the dialog."""
        sel = self.listbox.curselection()
        if sel:
            self.result = self.listbox.get(sel[0])
            self.destroy()

    def _skip(self):
        """Skips mapping for the current network."""
        self.result = None
        self.destroy()


class MigrationTool:
    def __init__(self, root):
        """Initializes the migration tool with UI and managers."""
        self.root = root
        self.root.title("History DB Migration")
        self.root.geometry("500x250")

        self.lbl_status = CopyLabel(
            root, text="Initializing...", font=("Segoe UI", 10)
        )
        self.lbl_status.pack(pady=(30, 10))

        self.pb = ttk.Progressbar(root, mode="determinate")
        self.pb.pack(fill=tk.X, padx=30, pady=10)

        self.lbl_details = CopyLabel(
            root, text="", font=("Consolas", 9), bootstyle="secondary"
        )
        self.lbl_details.pack(pady=5)

        self.history_mgr = HistoryManager()
        self.lora_mgr = LoraManager()
        self.emb_mgr = EmbeddingManager()

        self.lora_cache = self._build_cache(self.lora_mgr)
        self.emb_cache = self._build_cache(self.emb_mgr)

        self.decision_cache: Dict[str, Optional[str]] = {}

        self.lbl_status.config(
            text=f"Loaded Library: {len(self.lora_cache)} LoRAs,"
            f" {len(self.emb_cache)} Embeddings"
        )

    def _build_cache(self, manager) -> Dict[str, Dict[str, Any]]:
        """Maps Name -> Data and Alias -> Data."""
        cache = {}
        for item in manager.get_all():
            cache[item["name"]] = item
            if item.get("alias"):
                cache[item["alias"]] = item
        return cache

    def resolve_missing(
        self, name: str, net_type: str, cache: Dict
    ) -> Optional[Dict[str, Any]]:
        """
        Logic to handle missing item:
        1. Check if we already decided on this name.
        2. If not, open GUI.
        """
        cache_key = f"{net_type}:{name}"

        if cache_key in self.decision_cache:
            mapped_name = self.decision_cache[cache_key]
            return cache.get(mapped_name) if mapped_name else None

        available_names = sorted(
            list(set(item["name"] for item in cache.values()))
        )

        dialog = NetworkResolverDialog(
            self.root, name, net_type, available_names
        )
        self.root.wait_window(dialog)

        result_name = dialog.result

        self.decision_cache[cache_key] = result_name

        if result_name:
            print(f"Mapped '{name}' -> '{result_name}'")
            return cache[result_name]

        print(f"Skipped '{name}'")
        return None

    def process_entry(self, entry: Dict[str, Any]):
        """
        Processes a single history entry to backfill used
        networks and fix links.
        """
        original_prompt = entry.get("prompt", "")
        if not original_prompt:
            return 0

        current_prompt = original_prompt
        metadata = entry.get("metadata", {})
        used_networks = []
        prompt_changed = False

        matches = list(LORA_PATTERN.finditer(current_prompt))

        for match in matches:
            full_tag = match.group(0)
            name_in_prompt = match.group(1)
            strength_str = match.group(2)

            try:
                strength = float(strength_str)
            except ValueError:
                strength = 1.0

            net_info = self.lora_cache.get(name_in_prompt)

            if not net_info:
                self.lbl_details.config(text=f"Missing LoRA: {name_in_prompt}")
                self.root.update()

                net_info = self.resolve_missing(
                    name_in_prompt, "LoRA", self.lora_cache
                )

                if net_info:
                    new_name = net_info["name"]

                    new_tag = f"<lora:{new_name}:{strength_str}>"
                    current_prompt = current_prompt.replace(full_tag, new_tag)
                    prompt_changed = True

            network_data = {
                "type": "lora",
                "original_name": name_in_prompt,
                "strength": strength,
                "content_hash": net_info["content_hash"] if net_info else None,
                "remote_version_id": net_info["remote_version_id"]
                if net_info
                else None,
                "triggers": net_info["trigger_words"] if net_info else None,
            }
            used_networks.append(network_data)

        sorted_embs = sorted(
            self.emb_cache.values(), key=lambda x: len(x["name"]), reverse=True
        )
        found_emb_names = set()

        for emb in sorted_embs:
            if self._find_word(current_prompt, emb["name"]):
                if emb["name"] not in found_emb_names:
                    self._add_emb_meta(used_networks, emb, emb["name"])
                    found_emb_names.add(emb["name"])
            elif emb.get("alias") and self._find_word(
                current_prompt, emb["alias"]
            ):
                if emb["alias"] not in found_emb_names:
                    self._add_emb_meta(used_networks, emb, emb["alias"])
                    found_emb_names.add(emb["alias"])

        changes_made = 0
        updates = {}

        if used_networks:
            metadata["used_networks"] = used_networks
            updates["metadata"] = json.dumps(metadata)
            changes_made = len(used_networks)

        if prompt_changed:
            updates["prompt"] = current_prompt

        if updates:
            (
                HistoryEntry.update(**updates)
                .where(HistoryEntry.uuid == entry["uuid"])
                .execute()
            )

        return changes_made

    def _find_word(self, text, word):
        """Checks if a word exists in text using word boundaries."""
        pattern = r"(?<!\w)" + re.escape(word) + r"(?!\w)"
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _add_emb_meta(self, target_list, info, matched_name):
        """Adds embedding metadata to the used networks list."""
        target_list.append(
            {
                "type": "embedding",
                "original_name": matched_name,
                "strength": 1.0,
                "content_hash": info["content_hash"],
                "remote_version_id": info["remote_version_id"],
                "triggers": info["trigger_words"],
                "target": "positive",
            }
        )

    def run(self):
        """Executes the migration process over all history entries."""
        all_history = self.history_mgr.get_all()
        total = len(all_history)
        print(f"Scanning {total} history entries...")

        updated_count = 0
        self.pb["maximum"] = total

        for i, entry in enumerate(all_history):
            if self.process_entry(entry) > 0:
                updated_count += 1

            if i % 5 == 0:
                self.pb["value"] = i
                self.lbl_status.config(text=f"Scanning entry {i}/{total}...")
                self.root.update()

        self.lbl_status.config(text="Migration Complete!", bootstyle="success")
        self.lbl_details.config(text=f"Updated {updated_count} entries.")
        self.pb["value"] = total

        ttk.Button(self.root, text="Close", command=self.root.destroy).pack(
            pady=10
        )


if __name__ == "__main__":
    setup_logging()

    root = tk.Tk()

    style = ttk.Style(theme="darkly")

    w, h = 500, 250
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = (ws / 2) - (w / 2)
    y = (hs / 2) - (h / 2)
    root.geometry("%dx%d+%d+%d" % (w, h, x, y))

    try:
        tool = MigrationTool(root)

        root.after(500, tool.run)
        root.mainloop()
    except Exception as e:
        print(f"Migration Failed: {e}")
        import traceback

        traceback.print_exc()
