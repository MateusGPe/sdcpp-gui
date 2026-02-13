"""
Peewee ORM models with deduplicated Mixins.
"""

from typing import Any, Dict, List, Optional, TypedDict, Union

import peewee

db = peewee.Proxy()


class RemoteFields(TypedDict):
    remote_source: Optional[str]
    remote_id: Optional[str]
    remote_version_id: Optional[str]
    base_model: Optional[str]
    description: Optional[str]
    content_hash: Optional[str]  # <--- NEW


class ModelData(RemoteFields):
    """Data structure for a Model/Preset."""

    id: str
    name: str
    path: str
    params: List[Dict[str, Any]]


class NetworkData(RemoteFields):
    """Generic data structure for LoRA and Embedding."""

    id: str
    path: str
    dir_path: str
    filename: str
    name: str
    alias: str  # type: ignore
    trigger_words: str
    preferred_strength: float


LoraData = NetworkData
EmbeddingData = NetworkData


class HistoryData(TypedDict):
    """Data structure for a History entry."""

    uuid: str
    model_id: str
    timestamp: str
    prompt: str
    compiled_params: List[Dict[str, Any]]
    output_path: Union[str, List[str]]
    metadata: Dict[str, Any]


class QueueData(TypedDict):
    """Data structure for a Queue entry."""

    uuid: str
    model_id: str
    timestamp: str
    prompt: str
    compiled_params: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    status: str
    priority: int


class BaseModel(peewee.Model):
    """Base class for Peewee models."""

    class Meta:
        """Peewee metadata."""

        database = db


class RemoteMixin(peewee.Model):
    """Mixin for fields related to remote repositories (Civitai/HF)."""

    remote_source = peewee.TextField(null=True)
    remote_id = peewee.TextField(null=True)
    remote_version_id = peewee.TextField(null=True)
    base_model = peewee.TextField(null=True)
    description = peewee.TextField(null=True)
    content_hash = peewee.TextField(null=True, index=True)  # <--- NEW


class FileMixin(peewee.Model):
    """Mixin for file system paths."""

    path = peewee.TextField(unique=True, null=True)
    dir_path = peewee.TextField(index=True, default="")
    filename = peewee.TextField(default="")


class SettingModel(BaseModel):
    """ORM model for settings (Key-Value)."""

    key = peewee.TextField(primary_key=True)
    value = peewee.TextField(null=True)

    class Meta:
        """Configuration for the settings table."""

        table_name = "settings"


class ModelEntry(BaseModel, RemoteMixin):
    """ORM model for presets/checkpoints."""

    id = peewee.TextField(primary_key=True)
    name = peewee.TextField(null=True)
    path = peewee.TextField(null=True)
    params = peewee.TextField(null=True)  # JSON string

    class Meta:
        """Configuration for the models table."""

        table_name = "models"


class NetworkBaseEntry(BaseModel, RemoteMixin, FileMixin):
    """Base for Lora and Embedding to avoid duplication."""

    id = peewee.TextField(primary_key=True)
    alias = peewee.TextField(null=True)  # type: ignore
    trigger_words = peewee.TextField(default="")
    preferred_strength = peewee.FloatField(default=1.0)
    name = peewee.TextField(null=True)


class LoraEntry(NetworkBaseEntry):
    """Stores LoRA definitions."""

    class Meta:
        table_name = "loras"


class EmbeddingEntry(NetworkBaseEntry):
    """Stores Embedding definitions."""

    class Meta:
        """Configuration for the embeddings table."""

        table_name = "embeddings"


class HistoryEntry(BaseModel):
    """Stores generation history."""

    uuid = peewee.TextField(primary_key=True)
    model_id = peewee.TextField(null=True)
    timestamp = peewee.TextField(null=True)
    prompt = peewee.TextField(null=True)
    compiled_params = peewee.TextField(null=True)
    output_path = peewee.TextField(null=True)
    metadata = peewee.TextField(null=True)

    class Meta:
        """Configuration for the history table."""

        table_name = "history"


class QueueEntry(BaseModel):
    """Stores the generation queue."""

    uuid = peewee.TextField(primary_key=True)
    model_id = peewee.TextField(null=True)
    timestamp = peewee.TextField(null=True)
    prompt = peewee.TextField(null=True)
    compiled_params = peewee.TextField(null=True)
    metadata = peewee.TextField(null=True)
    status = peewee.TextField(default="pending")
    priority = peewee.IntegerField(default=0)

    class Meta:
        """Configuration for the queue table."""

        table_name = "queue"
