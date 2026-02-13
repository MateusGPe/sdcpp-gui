from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class LoraData:
    """Data structure for a single LoRA configuration."""

    strength: float
    dir_path: str
    triggers: Optional[str] = None
    content_hash: Optional[str] = None
    remote_version_id: Optional[str] = None
    original_name: Optional[str] = None


@dataclass
class EmbeddingData:
    """Data structure for a single Embedding configuration."""

    target: str
    strength: float
    dir_path: str
    triggers: Optional[str] = None
    content_hash: Optional[str] = None
    remote_version_id: Optional[str] = None
    original_name: Optional[str] = None


@dataclass
class GenerationState:
    """
    A pure data structure holding the configuration for a generation task.
    Logic for manipulating this state is handled by the UnifiedStateManager.
    """

    model_id: Optional[str] = None
    prompt: str = ""
    negative_prompt: str = ""
    add_triggers: Dict[str, bool] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    loras: Dict[str, LoraData] = field(default_factory=dict)
    embeddings: Dict[str, EmbeddingData] = field(default_factory=dict)

    def get_full_state(self) -> Dict[str, Any]:
        """Returns a dictionary representation for legacy compatibility.

        Logic: Serializes state to dictionary."""
        return {
            "model_id": self.model_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "add_triggers": self.add_triggers,
            "parameters": self.parameters.copy(),
            "loras": {
                k: (v.strength, v.dir_path, v.triggers)
                for k, v in self.loras.items()
            },
            "embeddings": {
                k: (v.target, v.strength, v.dir_path, v.triggers)
                for k, v in self.embeddings.items()
            },
        }
