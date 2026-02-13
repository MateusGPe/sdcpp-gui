from __future__ import annotations

import re
import unicodedata
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Final,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    cast,
)

if TYPE_CHECKING:
    from sd_cpp_gui.data.db.data_manager import EmbeddingManager, LoraManager
    from sd_cpp_gui.domain.generation.commands_loader import CommandLoader
from sd_cpp_gui.domain.generation.types import (
    EmbeddingData,
    GenerationState,
    LoraData,
)


class ArgumentProcessor:
    """
    Central Logic for Argument Management.

    Pre-compiled patterns for performance
    Matches <lora:Name:1.0> allowing for optional spaces
    """

    _LORA_PATTERN: Pattern[str] = re.compile(
        r"<lora:([^:]+?):\s*([+-]?\d*\.?\d+)\s*>"
    )
    _WHITESPACE_PATTERN: Pattern[str] = re.compile(r"\s+")
    _EMBEDDING_TRIGGER_PATTERN: str = (
        r"(\({}:(?P<str>[\d\.]+)\)|\({}\)|(?<!\w){}(?!\w))"
    )

    def __init__(
        self,
        cmd_loader: CommandLoader,
        embedding_manager: Optional[EmbeddingManager] = None,
        lora_manager: Optional[LoraManager] = None,
    ) -> None:
        """Logic: Initializes processor."""
        self.cmd_loader = cmd_loader
        self.embedding_manager = embedding_manager
        self.lora_manager = lora_manager
        self._embeddings_cache: Optional[List[Dict[str, Any]]] = None
        self.persistent_categories: Set[str] = {"performance", "output"}
        self._prompt_flags: Set[str] = set()
        self._neg_prompt_flags: Set[str] = set()
        self._excluded_flags: Set[str] = set()
        self._persistent_flags: Final[Set[str]] = self._init_persistent_flags()
        self._init_special_flags()

    def _init_special_flags(self) -> None:
        """Pre-calculates sets of special flags.

        Logic: Identifies prompt and excluded flags."""
        prompt_cmd = self.cmd_loader.get_by_internal_name("Prompt")
        if prompt_cmd:
            self._prompt_flags.update(
                (f.strip() for f in prompt_cmd["flag"].split(","))
            )
        neg_cmd = self.cmd_loader.get_by_internal_name("Negative Prompt")
        if neg_cmd:
            self._neg_prompt_flags.update(
                (f.strip() for f in neg_cmd["flag"].split(","))
            )
        self._excluded_flags.update(self.cmd_loader.ignored_flags)
        self._excluded_flags.update(self._prompt_flags)
        self._excluded_flags.update(self._neg_prompt_flags)
        for name in ["LoRA Model Dir", "Embedding Dir"]:
            cmd = self.cmd_loader.get_by_internal_name(name)
            if cmd:
                self._excluded_flags.add(cmd["flag"])

    def is_prompt_flag(self, flag: str) -> bool:
        """Returns True if the flag corresponds to the positive prompt."""
        return flag in self._prompt_flags

    def is_negative_prompt_flag(self, flag: str) -> bool:
        """Returns True if the flag corresponds to the negative prompt."""
        return flag in self._neg_prompt_flags

    def is_excluded(self, flag: str) -> bool:
        """Returns True if the flag should be hidden from the dynamic UI."""
        return flag in self._excluded_flags

    def _init_persistent_flags(self) -> Set[str]:
        """
        Identifies flags that should persist across sessions based on category.

        Logic: Identifies persistent flags."""
        persistent_flags: Set[str] = set()
        categorized_cmds = self.cmd_loader.get_categorized_commands()
        for cat_name, cmds_list in categorized_cmds.items():
            if cat_name in self.persistent_categories:
                for cmd in cmds_list:
                    for f in cmd["flag"].split(","):
                        persistent_flags.add(f.strip())
        return persistent_flags

    def get_persistent_flags(self) -> Set[str]:
        """
        Identifies flags that should persist across sessions based on category.

        Logic: Returns persistent flags.
        """
        return self._persistent_flags

    def get_model_defaults(
        self, model_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Retrieves parameter defaults from model data.
        Returns a list of dicts: {'flag': str, 'value': Any, 'enabled': bool}

        Logic: Returns model defaults.
        """
        return model_data.get("params", [])

    def convert_to_cli(
        self, state: GenerationState
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Converts state object into execution arguments.

        Logic: Processes state into CLI arguments and prompt string."""
        prompt = state.prompt
        params = self._process_generic_params(state)
        prompt, neg_suffix, emb_dirs = self._process_embeddings(state, prompt)
        prompt, lora_dirs = self._process_loras(state, prompt)
        self._append_directory_params(params, lora_dirs, emb_dirs)
        self._process_negative_prompt(state, params, neg_suffix)
        return (prompt.strip(), params)

    def _process_generic_params(
        self, state: GenerationState
    ) -> List[Dict[str, Any]]:
        """
        Converts the state's parameter map into a list of CLI-ready
        dictionaries. Handles type casting based on command definitions.

        Args:
                state: The current generation state.

        Returns:
                List of {'flag': str, 'value': Any}
        """
        params: List[Dict[str, Any]] = []
        source_params = state.parameters
        for flag, value in source_params.items():
            cmd_def = self.cmd_loader.raw_by_flag(flag)
            arg_type = cmd_def["type"] if cmd_def else "string"
            sanitized_value: Any = value
            if arg_type in {"flag", "boolean", "bool"}:
                sanitized_value = None
            elif arg_type in {"integer", "int"}:
                try:
                    sanitized_value = int(float(value))
                except (ValueError, TypeError):
                    sanitized_value = 0
            elif arg_type == "float":
                try:
                    sanitized_value = float(value)
                except (ValueError, TypeError):
                    sanitized_value = 0.0
            elif arg_type in {"string", "str", "enum", "list"}:
                sanitized_value = str(value) if value is not None else ""
            params.append({"flag": flag, "value": sanitized_value})
        return params

    def _process_loras(
        self, state: GenerationState, prompt: str
    ) -> Tuple[str, Set[str]]:
        """
        Processes LoRAs in the state, appending tags to the prompt and
        collecting required directory paths.

        Args:
                state: The current generation state.
                prompt: The base prompt string.

        Returns:
                A tuple of (updated_prompt, set_of_directory_paths).
        """
        lora_dirs: Set[str] = set()
        triggers_list: List[str] = []
        lora_tags_list: List[str] = []
        should_add_trigger = state.add_triggers.get("lora", False)
        for name, data in state.loras.items():
            if data.triggers and should_add_trigger:
                triggers_list.append(data.triggers)
            lora_tags_list.append(f"<lora:{name}:{data.strength}>")
            if data.dir_path:
                lora_dirs.add(data.dir_path)
        parts = []
        if prompt:
            parts.append(prompt)
        parts.extend(triggers_list)
        parts.extend(lora_tags_list)
        return (" ".join(parts), lora_dirs)

    def _process_embeddings(
        self, state: GenerationState, prompt: str
    ) -> Tuple[str, str, Set[str]]:
        """
        Processes Embeddings in the state, injecting tokens into
        positive/negative prompts and collecting directory paths.

        Args:
                state: The current generation state.
                prompt: The base positive prompt.

        Returns:
                A tuple of (updated_positive_prompt, negative_prompt_suffix,
                set_of_directory_paths).
        """
        emb_dirs: Set[str] = set()
        prompt_parts = [prompt] if prompt else []
        neg_parts: List[str] = []
        should_add_trigger = state.add_triggers.get("embedding", False)
        for name, data in state.embeddings.items():
            token = name
            trigger_token = data.triggers if data.triggers else ""
            if data.strength != 1.0:
                token = f"({name}:{data.strength})"
                if data.triggers:
                    trigger_token = f"({data.triggers}:{data.strength})"
            target_list = (
                prompt_parts if data.target == "positive" else neg_parts
            )
            if data.triggers and should_add_trigger:
                target_list.append(trigger_token)
            target_list.append(token)
            if data.dir_path:
                emb_dirs.add(data.dir_path)
        return (" ".join(prompt_parts), " ".join(neg_parts), emb_dirs)

    def _append_directory_params(
        self,
        params: List[Dict[str, Any]],
        lora_dirs: Set[str],
        emb_dirs: Set[str],
    ) -> None:
        """Logic: Appends directory paths to parameters."""
        if lora_dirs:
            if cmd := self.cmd_loader.get_by_internal_name("LoRA Model Dir"):
                params.append(
                    {"flag": cmd["flag"], "value": next(iter(lora_dirs))}
                )
        if emb_dirs:
            if cmd := self.cmd_loader.get_by_internal_name("Embedding Dir"):
                params.append(
                    {"flag": cmd["flag"], "value": next(iter(emb_dirs))}
                )

    def _process_negative_prompt(
        self,
        state: GenerationState,
        params: List[Dict[str, Any]],
        extra_neg: str,
    ) -> None:
        """Logic: Processes negative prompt."""
        base = state.negative_prompt
        full = f"{base} {extra_neg}".strip()
        if full:
            if cmd := self.cmd_loader.get_by_internal_name("Negative Prompt"):
                params.append({"flag": cmd["flag"], "value": full})

    def restore_from_args(
        self,
        model_id: str,
        prompt: str,
        compiled_params: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GenerationState:
        """
        Restores state from history using Metadata for robust
        linking if available.

        Logic: Reconstructs state from arguments, parsing prompt
        for networks and using metadata for reconciliation.
        """
        new_state = GenerationState(
            model_id=model_id,
            prompt="",
            negative_prompt="",
            parameters={},
            loras={},
            embeddings={},
        )
        raw_neg_prompt = ""
        ignore_flags = self._excluded_flags.union(self.get_persistent_flags())
        for param in compiled_params:
            flag = str(param.get("flag", ""))
            value = param.get("value")
            if flag in self._neg_prompt_flags:
                raw_neg_prompt = str(value or "")
                continue
            if flag in ignore_flags:
                continue
            if flag:
                new_state.parameters[flag] = value
        clean_pos, pos_emb_hints = self._extract_embeddings(prompt, "positive")
        clean_neg, neg_emb_hints = self._extract_embeddings(
            raw_neg_prompt, "negative"
        )
        lora_hints: Dict[str, float] = {}
        clean_pos_no_lora = clean_pos
        for match in self._LORA_PATTERN.finditer(clean_pos):
            name, strength = match.groups()
            clean_name = unicodedata.normalize("NFC", name.strip())
            lora_hints[clean_name] = float(strength)
            clean_pos_no_lora = clean_pos_no_lora.replace(match.group(0), "")
        clean_pos = clean_pos_no_lora.strip()
        used_networks = metadata.get("used_networks", []) if metadata else []
        self._reconcile_loras(new_state, lora_hints, used_networks)
        self._reconcile_embeddings(
            new_state, pos_emb_hints, neg_emb_hints, used_networks
        )
        new_state.prompt = clean_pos
        new_state.negative_prompt = clean_neg
        return new_state

    def _reconcile_loras(
        self,
        state: GenerationState,
        hints: Dict[str, float],
        used_networks: List[Dict[str, Any]],
    ) -> None:
        """
        Matches prompt hints (Name, Strength) with Rich Metadata (Hash, ID).

        Logic: Reconciles prompt LoRA tags with metadata/DB.
        """
        meta_map = {
            net["original_name"]: net
            for net in used_networks
            if net.get("type") == "lora" and "original_name" in net
        }
        from sd_cpp_gui.data.db.data_manager import LoraManager

        manager = LoraManager()
        for name, strength in hints.items():
            meta = meta_map.get(name)
            content_hash = meta.get("content_hash") if meta else None
            remote_id = meta.get("remote_version_id") if meta else None
            match = manager.find_best_match(content_hash, remote_id, name)
            if match:
                current_name = match["name"] or match["alias"]
                state.loras[current_name] = LoraData(
                    strength=strength,
                    dir_path=match["dir_path"],
                    triggers=match["trigger_words"],
                    content_hash=match["content_hash"],
                    remote_version_id=match["remote_version_id"],
                    original_name=name,
                )
            else:
                state.loras[name] = LoraData(
                    strength=strength,
                    dir_path="",
                    triggers=meta.get("triggers") if meta else None,
                    content_hash=content_hash,
                    remote_version_id=remote_id,
                    original_name=name,
                )

    def _reconcile_embeddings(
        self,
        state: GenerationState,
        pos_hints: Dict[str, EmbeddingData],
        neg_hints: Dict[str, EmbeddingData],
        used_networks: List[Dict[str, Any]],
    ) -> None:
        """Logic: Reconciles prompt Embedding tokens with metadata/DB."""
        meta_map = {
            net["original_name"]: net
            for net in used_networks
            if net.get("type") == "embedding" and "original_name" in net
        }
        from sd_cpp_gui.data.db.data_manager import EmbeddingManager

        manager = EmbeddingManager()

        def process_hints(hints: Dict[str, EmbeddingData]):
            for name, data in hints.items():
                meta = meta_map.get(name)
                content_hash = meta.get("content_hash") if meta else None
                remote_id = meta.get("remote_version_id") if meta else None
                match = manager.find_best_match(content_hash, remote_id, name)
                if match:
                    current_name = match["name"] or match["alias"]
                    data.dir_path = match["dir_path"]
                    data.triggers = match["trigger_words"]
                    data.content_hash = match["content_hash"]
                    data.remote_version_id = match["remote_version_id"]
                    data.original_name = name
                    state.embeddings[current_name] = data
                else:
                    data.content_hash = content_hash
                    data.remote_version_id = remote_id
                    data.original_name = name
                    state.embeddings[name] = data

        process_hints(pos_hints)
        process_hints(neg_hints)

    def _extract_embeddings(
        self, text: str, target_type: str
    ) -> Tuple[str, Dict[str, EmbeddingData]]:
        """Logic: Extracts known embeddings from text regex."""
        if self.embedding_manager is None:
            return text, {}

        if self._embeddings_cache is None:
            self._embeddings_cache = cast(
                List[Dict[str, Any]], self.embedding_manager.get_all()
            )
        found: Dict[str, EmbeddingData] = {}
        clean = text
        relevant_embeddings = [
            e
            for e in self._embeddings_cache or []
            if e.get("name")
            and e["name"] in text
            or (e.get("alias") and e["alias"] in text)
        ]
        for entry in relevant_embeddings:
            candidates = [entry.get("alias"), entry.get("name")]
            candidates = [c for c in candidates if c]
            sorted_triggers = sorted(candidates, key=len, reverse=True)
            for trig in sorted_triggers:
                escaped = re.escape(trig)
                pattern = self._EMBEDDING_TRIGGER_PATTERN.format(
                    escaped, escaped, escaped
                )
                cp = re.compile(pattern, re.IGNORECASE)
                match = cp.search(clean)
                if match:
                    clean = cp.sub("", clean)
                    strength = (
                        float(match.group("str")) if match.group("str") else 1.0
                    )
                    name = entry.get("name") or entry.get("alias") or "Unknown"
                    found[name] = EmbeddingData(
                        target=target_type,
                        strength=strength,
                        dir_path=entry.get("dir_path", ""),
                        content_hash=entry.get("content_hash"),
                        remote_version_id=entry.get("remote_version_id"),
                    )
                    break
        return (self._WHITESPACE_PATTERN.sub(" ", clean).strip(), found)
