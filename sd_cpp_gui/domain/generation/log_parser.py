"""
Parser for stable-diffusion.cpp stdout logs.
"""

import re
from typing import Any, Callable, Dict, List, Match, Tuple


class SDLogParser:
    """Advanced parser supporting C++ structures and log levels."""

    _ANSI_ESCAPE = re.compile(r"(?:\x1b|\033)[\[\d;]*[a-zA-Z]")

    _RE_BAR = re.compile(r"\|\s*(?P<current>\d+)/(?P<total>\d+)")
    _RE_SEED = re.compile(r"seed\s+(?P<seed>\d+)", re.IGNORECASE)
    _RE_SAVE = re.compile(r"save.*to\s+['\"](?P<path>.*?)['\"]", re.IGNORECASE)
    _RE_BATCH = re.compile(
        r"generating image:\s*(?P<current>\d+)/(?P<total>\d+)", re.IGNORECASE
    )
    _RE_VRAM = re.compile(
        r"total params memory size = (?P<total>[\d\.]+)MB \("
        r"VRAM (?P<vram>[\d\.]+)MB, RAM (?P<ram>[\d\.]+)MB\)",
        re.IGNORECASE,
    )
    _RE_LOAD_TIME = re.compile(
        r"loading tensors completed, taking (?P<time>[\d\.]+)s", re.IGNORECASE
    )
    _RE_LORA_APPLIED = re.compile(
        r"lora '(?P<path>.*?)' applied, taking (?P<time>[\d\.]+)s",
        re.IGNORECASE,
    )
    _RE_UCACHE = re.compile(
        r"UCache skipped (?P<skipped>\d+)/(?P<total>\d+) steps \("
        r"(?P<speedup>[\d\.]+)x estimated speedup\)",
        re.IGNORECASE,
    )

    _RE_LOG_TAG = re.compile(r"^\s*\[(?P<tag>INFO|DEBUG|WARN|ERROR)\s*\]")
    _RE_PARAM_KV = re.compile(r"^\s*(?P<key>[\w\.]+):\s*(?P<value>.*?),?$")

    def __init__(self) -> None:
        """Logic: Initializes parser rules."""
        self.parsing_rules: List[
            Tuple[Callable[[str], Any], Callable[[Any, str], Dict[str, Any]]]
        ] = [
            (self._RE_BAR.search, self._parse_progress),
            (self._RE_SAVE.search, self._parse_file_saved),
            (self._RE_BATCH.search, self._parse_batch),
            (self._RE_SEED.search, self._parse_seed),
            (self._RE_VRAM.search, self._parse_vram),
            (self._RE_LOAD_TIME.search, self._parse_load_time),
            (self._RE_LORA_APPLIED.search, self._parse_lora_applied),
            (self._RE_UCACHE.search, self._parse_ucache),
            (self._RE_LOG_TAG.match, self._parse_log_tag),
            (
                lambda line: "SYSTEM INFO" in line.upper()
                or "AVX =" in line.upper()
                or "VULKAN DEVICES" in line.upper(),
                self._parse_system_info,
            ),
            (
                lambda line: any(
                    kw in line.upper()
                    for kw in ["COMPLETED", "DONE IN", "TAKING"]
                ),
                self._parse_success,
            ),
            (
                lambda line: any(
                    kw in line.upper()
                    for kw in [
                        "USING",
                        "LOAD",
                        "INIT",
                        "BACKEND",
                        "VRAM",
                        "INFO",
                    ]
                ),
                self._parse_info,
            ),
            (
                lambda line: line.endswith("{") or line == "}",
                self._parse_param_structure,
            ),
            (self._RE_PARAM_KV.match, self._parse_param_kv),
        ]

    def clean_line(self, line: str) -> str:
        """Removes ANSI escape codes from a line.

        Logic: Removes ANSI codes."""
        return self._ANSI_ESCAPE.sub("", line)

    def _parse_progress(self, match: Match[str], line: str) -> Dict[str, Any]:
        """Logic: Parses progress bar."""
        return {
            "type": "progress",
            "current": int(match.group("current")),
            "total": int(match.group("total")),
            "raw": line,
        }

    def _parse_batch(self, match: Match[str], line: str) -> Dict[str, Any]:
        """Logic: Parses batch progress."""
        data = {
            "type": "batch_progress",
            "current": int(match.group("current")),
            "total": int(match.group("total")),
            "raw": line,
        }
        seed_match = self._RE_SEED.search(line)
        if seed_match:
            data["type"] = "seed"
            data["seed"] = seed_match.group("seed")
        return data

    def _parse_vram(self, match: Match[str], line: str) -> Dict[str, Any]:
        """Logic: Parses VRAM usage."""
        return {
            "type": "vram_usage",
            "total_mb": float(match.group("total")),
            "vram_mb": float(match.group("vram")),
            "ram_mb": float(match.group("ram")),
            "raw": line,
        }

    def _parse_load_time(self, match: Match[str], line: str) -> Dict[str, Any]:
        """Logic: Parses load time."""
        return {
            "type": "model_load_time",
            "time_s": float(match.group("time")),
            "raw": line,
        }

    def _parse_lora_applied(
        self, match: Match[str], line: str
    ) -> Dict[str, Any]:
        """Logic: Parses LoRA application."""
        return {
            "type": "lora_applied",
            "path": match.group("path"),
            "time_s": float(match.group("time")),
            "raw": line,
        }

    def _parse_ucache(self, match: Match[str], line: str) -> Dict[str, Any]:
        """Logic: Parses UCache stats."""
        return {
            "type": "ucache_stats",
            "skipped": int(match.group("skipped")),
            "total": int(match.group("total")),
            "speedup": float(match.group("speedup")),
            "raw": line,
        }

    def _parse_param_structure(self, _match: Any, line: str) -> Dict[str, str]:
        """Logic: Parses param structure line."""
        return {"type": "params", "raw": line}

    def _parse_param_kv(self, match: Match[str], line: str) -> Dict[str, Any]:
        """Logic: Parses param key-value pair."""
        return {
            "type": "params",
            "key": match.group("key"),
            "value": match.group("value"),
            "raw": line,
        }

    def _parse_log_tag(self, match: Match[str], line: str) -> Dict[str, Any]:
        """Logic: Parses log tag."""
        tag = match.group("tag")
        if tag == "DEBUG":
            return {"type": "debug", "raw": line}
        if tag == "WARN":
            return {"type": "warning", "raw": line}
        if tag == "ERROR":
            content = line[match.end() :].strip()
            return {"type": "error", "message": content, "raw": line}
        if tag == "INFO":
            upper_line = line.upper()
            if "COMPLETED" in upper_line or "DONE IN" in upper_line:
                return {"type": "success", "raw": line}
        return {"type": "info", "raw": line}

    def _parse_system_info(self, _match: Any, line: str) -> Dict[str, str]:
        """Logic: Parses system info."""
        return {"type": "system", "raw": line}

    def _parse_seed(self, match: Match[str], line: str) -> Dict[str, str]:
        """Logic: Parses seed."""
        return {"type": "seed", "seed": match.group("seed"), "raw": line}

    def _parse_file_saved(self, match: Match[str], line: str) -> Dict[str, str]:
        """Logic: Parses file saved."""
        return {"type": "file_saved", "path": match.group("path"), "raw": line}

    def _parse_success(self, _match: Any, line: str) -> Dict[str, str]:
        """Logic: Parses success message."""
        return {"type": "success", "raw": line}

    def _parse_info(self, _match: Any, line: str) -> Dict[str, str]:
        """Logic: Parses general info."""
        return {"type": "info", "raw": line}

    def parse(self, line: str) -> Dict[str, Any]:
        """Parses a log line and returns a categorized dictionary.

        Logic: Applies regex rules to parse line."""
        if not line:
            return {"type": "empty"}
        clean_line = self.clean_line(line).strip()
        if not clean_line:
            return {"type": "empty"}
        for condition, handler in self.parsing_rules:
            match = condition(clean_line)
            if match:
                result = handler(match, clean_line)
                if result:
                    return result
        return {"type": "raw", "raw": clean_line}
