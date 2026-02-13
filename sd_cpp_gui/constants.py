"""
Constantes globais e configurações de ambiente para o projeto.
"""

import platform
from typing import Final

_OS_NAME = platform.system()

SYSTEM_FONT: Final[str] = (
    "Segoe UI"
    if _OS_NAME == "Windows"
    else ".AppleSystemUIFont"
    if _OS_NAME == "Darwin"
    else "Helvetica"
)

EMOJI_FONT: Final[str] = (
    "Segoe UI Emoji"
    if _OS_NAME == "Windows"
    else (
        "Apple Color Emoji" if _OS_NAME == "Darwin" else "Noto Color Emoji Bold"
    )
)
CORNER_RADIUS: Final[int] = 8
CHANNEL_APP_EVENTS: Final[str] = "app_global_events"
STATE_CHANGED_CHANNEL: Final[str] = "state_changed"

MSG_MODEL_SELECTED: Final[str] = "model_selected"
MSG_DATA_IMPORTED: Final[str] = "data_imported"
MSG_GENERATION_STARTED: Final[str] = "generation_started"
MSG_GENERATION_FINISHED: Final[str] = "generation_finished"
MSG_QUEUE_PROCESSING_STARTED: Final[str] = "queue_started"
MSG_QUEUE_PROCESSING_STOPPED: Final[str] = "queue_stopped"

__all__ = [
    "SYSTEM_FONT",
    "EMOJI_FONT",
    "CHANNEL_APP_EVENTS",
    "MSG_MODEL_SELECTED",
    "MSG_DATA_IMPORTED",
    "MSG_GENERATION_STARTED",
    "MSG_GENERATION_FINISHED",
    "MSG_QUEUE_PROCESSING_STARTED",
    "MSG_QUEUE_PROCESSING_STOPPED",
    "STATE_CHANGED_CHANNEL",
    "CORNER_RADIUS",
]
