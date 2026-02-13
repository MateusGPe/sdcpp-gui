from typing import Any, Dict

from sd_cpp_gui.domain.generation.log_parser import SDLogParser
from sd_cpp_gui.infrastructure.event_bus import EventBus


class SDLogEventHandler:
    """
    Centralizes the logic of converting raw log lines into EventBus events.
    Used by both CLI Runners and Server Process Managers to ensure consistent
    UI feedback.
    """

    def __init__(self) -> None:
        """Logic: Initializes handler with parser."""
        self.parser = SDLogParser()

    def handle_line(self, line: str) -> Dict[str, Any]:
        """
        Parses a line and automatically publishes the appropriate
        EventBus events.
        Returns the parsed dictionary for further internal processing
        by the caller.


        Logic: Parses log line and emits corresponding events (
        progress, log, error).
        """
        parsed = self.parser.parse(line)
        p_type = parsed.get("type")
        raw_text = parsed.get("raw", "").strip()
        if not p_type or p_type == "empty":
            return parsed
        if p_type in ("progress", "batch_progress"):
            EventBus.publish("execution_progress", parsed)
            if p_type == "batch_progress":
                self._emit_log(raw_text, "INFO")
            return parsed
        if p_type == "error":
            self._emit_log(parsed.get("message", raw_text), "ERROR")
        elif p_type == "warning":
            self._emit_log(raw_text, "WARN")
        elif p_type == "file_saved":
            path = parsed.get("path", "Unknown")
            self._emit_log(f"Image saved: {path}", "SUCCESS")
        elif p_type == "seed":
            EventBus.publish(
                "log_message",
                {"text": raw_text, "level": "INFO", "seed": parsed.get("seed")},
            )
        elif p_type in ("success", "lora_applied", "model_load_time"):
            self._emit_log(raw_text, "SUCCESS")
        elif p_type in ("vram_usage", "ucache_stats", "info", "system"):
            self._emit_log(raw_text, "INFO")
        else:
            self._emit_log(raw_text, "RAW")
        return parsed

    def _emit_log(self, text: str, level: str) -> None:
        """Logic: Emits log event."""
        EventBus.publish("log_message", {"text": text, "level": level})
