"""
Service to orchestrate Library Sanitization and History Migration.
"""

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

from sd_cpp_gui.data.db.data_manager import (
    EmbeddingManager,
    HistoryManager,
    LoraManager,
)
from sd_cpp_gui.domain.utils.sanitization import (
    get_unique_filename,
    make_filename_portable,
)


class LibraryCleanerService:
    # Regex to capture <lora:NAME:STRENGTH>
    _LORA_PATTERN = re.compile(r"<lora:([^:]+):([+-]?\d*\.?\d+)>")

    def __init__(self) -> None:
        """Logic: Initializes managers."""
        self.loras = LoraManager()
        self.embeddings = EmbeddingManager()
        self.history = HistoryManager()

    def scan_for_changes(self) -> List[Dict[str, Any]]:
        """
        Scans all networks and identifies ones needing renaming.
        Returns a list of proposed changes.

        Logic: Iterates over files and checks if filename matches
        sanitized version.
        """
        changes: List[Dict[str, Any]] = []

        def _process(manager: Any, type_label: str) -> None:
            for item in manager.get_all():
                current_path = item.get("path", "")
                if not current_path or not os.path.exists(current_path):
                    continue
                real_fname = os.path.basename(current_path)
                new_fname = make_filename_portable(real_fname)
                if real_fname != new_fname:
                    changes.append(
                        {
                            "type": type_label,
                            "id": item["id"],
                            "current_path": current_path,
                            "current_name": item["name"],
                            "original_filename": real_fname,
                            "new_filename": new_fname,
                            "status": "Pending",
                        }
                    )

        _process(self.loras, "LoRA")
        _process(self.embeddings, "Embedding")
        return changes

    def execute_renames(
        self, changes: List[Dict[str, Any]], callback: Optional[Any] = None
    ) -> Dict[str, str]:
        """
        Executes file renames and DB updates.
        Returns a map of {OldInternalName: NewInternalName}
        for history patching.

        Logic: Renames files, sidecars, and updates DB records.
        """
        name_map: Dict[str, str] = {}
        total = len(changes)
        for i, change in enumerate(changes):
            if callback:
                callback(i, total, f"Renaming {change['original_filename']}...")
            try:
                old_path = change["current_path"]
                if not os.path.exists(old_path):
                    change["status"] = "File Missing"
                    continue
                dir_path = os.path.dirname(os.path.abspath(old_path))
                target_filename = change["new_filename"]
                final_filename = get_unique_filename(dir_path, target_filename)
                new_path = os.path.join(dir_path, final_filename)
                if (
                    old_path.lower() == new_path.lower()
                    and old_path != new_path
                ):
                    temp_path = old_path + ".tmp"
                    os.rename(old_path, temp_path)
                    os.rename(temp_path, new_path)
                else:
                    os.rename(old_path, new_path)
                self._handle_sidecars(old_path, new_path, final_filename)
                new_stem = os.path.splitext(final_filename)[0]
                manager = (
                    self.loras if change["type"] == "LoRA" else self.embeddings
                )
                with manager.model_class._meta.database.atomic():
                    manager.model_class.update(
                        path=new_path,
                        filename=final_filename,
                        name=new_stem,
                        dir_path=dir_path,
                    ).where(manager.model_class.id == change["id"]).execute()
                if (
                    change["current_name"]
                    and change["current_name"] != new_stem
                ):
                    name_map[change["current_name"]] = new_stem
                change["status"] = "Success"
            except Exception as e:
                change["status"] = f"Error: {e}"
                import traceback

                traceback.print_exc()
        return name_map

    def _handle_sidecars(
        self, old_path_base: str, new_path_base: str, new_filename: str
    ) -> None:
        """Renames associated files like .json, .png, etc.

        Logic: Renames existing sidecar files."""
        base_old = os.path.splitext(old_path_base)[0]
        base_new = os.path.splitext(new_path_base)[0]
        extensions = [
            ".json",
            ".preview.png",
            ".png",
            ".jpg",
            ".jpeg",
            ".txt",
            ".yaml",
            ".model.json",
            ".civitai.info",
        ]
        for ext in extensions:
            old_sidecar = f"{base_old}{ext}"
            new_sidecar = f"{base_new}{ext}"
            if os.path.exists(old_sidecar):
                if not os.path.exists(new_sidecar):
                    try:
                        os.rename(old_sidecar, new_sidecar)
                    except OSError:
                        pass

    def _patch_json_content(self, json_path: str, new_filename: str) -> None:
        """Updates 'files' list in metadata JSON to match new filename.

        Logic: Patches filename in metadata JSON."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            updated = False
            if "files" in data and isinstance(data["files"], list):
                for file_node in data["files"]:
                    if (
                        file_node.get("type") == "Model"
                        or file_node.get("primary") is True
                    ):
                        file_node["name"] = new_filename
                        updated = True
            if updated:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
        except (json.JSONDecodeError, IOError):
            pass

    def patch_history(
        self, name_mapping: Dict[str, str], callback: Optional[Any] = None
    ) -> int:
        """
        Iterates through history and updates prompts to use new filenames.

        Logic: Replaces old names with new names in history prompts.
        """
        if not name_mapping:
            return 0
        history_items = self.history.get_all()
        total = len(history_items)
        updated_count = 0
        for i, entry in enumerate(history_items):
            if callback and i % 10 == 0:
                callback(i, total, "Patching History...")
            prompt = entry["prompt"] or ""
            original_prompt = prompt
            for old_name, new_name in name_mapping.items():
                if old_name not in prompt:
                    continue
                esc_old = re.escape(old_name)
                lora_pattern = re.compile(f"<lora:{esc_old}:", re.IGNORECASE)
                prompt = lora_pattern.sub(f"<lora:{new_name}:", prompt)
                emb_pattern = re.compile(
                    "(?<!\\w)" + esc_old + "(?!\\w)", re.IGNORECASE
                )
                prompt = emb_pattern.sub(new_name, prompt)
            if prompt != original_prompt:
                self.history.model_class.update(prompt=prompt).where(
                    self.history.model_class.uuid == entry["uuid"]
                ).execute()
                updated_count += 1
        return updated_count

    def fix_absent_loras(
        self,
        resolver_callback: Callable[[str, List[str]], Optional[str]],
        progress_callback: Optional[Any] = None,
    ) -> int:
        """
        Scans history for <lora:Name:1.0> tags.
        If 'Name' is not in the library, calls 'resolver_callback'.
        If resolved, updates the prompt text AND backfills metadata.

        Logic: Identifies missing LoRAs in history, prompts user
        to resolve, and updates history.
        """
        lora_cache = {}
        for item in self.loras.get_all():
            lora_cache[item["name"]] = item
            if item.get("alias"):
                lora_cache[item["alias"]] = item
        available_names_list = sorted(
            list(set((item["name"] for item in lora_cache.values())))
        )
        decision_cache: Dict[str, Optional[str]] = {}
        history_items = self.history.get_all()
        total = len(history_items)
        updated_count = 0
        for i, entry in enumerate(history_items):
            if progress_callback and i % 10 == 0:
                progress_callback(
                    i, total, "Scanning History for missing LoRAs..."
                )
            original_prompt = entry.get("prompt", "")
            if not original_prompt:
                continue
            current_prompt = original_prompt
            metadata = entry.get("metadata", {}) or {}
            used_networks = metadata.get("used_networks", [])
            existing_meta_names = {
                n["original_name"]
                for n in used_networks
                if n.get("type") == "lora"
            }
            prompt_changed = False
            meta_changed = False
            matches = list(self._LORA_PATTERN.finditer(current_prompt))
            for match in matches:
                full_tag = match.group(0)
                name_in_prompt = match.group(1)
                strength_str = match.group(2)
                try:
                    strength = float(strength_str)
                except ValueError:
                    strength = 1.0
                net_info = lora_cache.get(name_in_prompt)
                if not net_info:
                    if name_in_prompt in decision_cache:
                        resolved_name = decision_cache[name_in_prompt]
                    else:
                        resolved_name = resolver_callback(
                            name_in_prompt, available_names_list
                        )
                        decision_cache[name_in_prompt] = resolved_name
                    if resolved_name:
                        net_info = lora_cache.get(resolved_name)
                        new_tag = f"<lora:{resolved_name}:{strength_str}>"
                        current_prompt = current_prompt.replace(
                            full_tag, new_tag
                        )
                        prompt_changed = True
                        name_in_prompt = resolved_name
                if net_info and name_in_prompt not in existing_meta_names:
                    network_data = {
                        "type": "lora",
                        "original_name": name_in_prompt,
                        "strength": strength,
                        "content_hash": net_info["content_hash"],
                        "remote_version_id": net_info["remote_version_id"],
                        "triggers": net_info["trigger_words"],
                    }
                    used_networks.append(network_data)
                    existing_meta_names.add(name_in_prompt)
                    meta_changed = True
            updates = {}
            if prompt_changed:
                updates["prompt"] = current_prompt
            if meta_changed:
                metadata["used_networks"] = used_networks
                updates["metadata"] = json.dumps(metadata)
            if updates:
                self.history.model_class.update(**updates).where(
                    self.history.model_class.uuid == entry["uuid"]
                ).execute()
                updated_count += 1
        return updated_count
