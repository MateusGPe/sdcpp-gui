"""
Engine de Execução CLI.
"""

import os
import shlex
import subprocess
import threading
from typing import Any, Callable, Dict, List, Optional, TextIO, TypedDict

from sd_cpp_gui.domain.generation.interfaces import IGenerator
from sd_cpp_gui.domain.generation.log_handler import SDLogEventHandler
from sd_cpp_gui.infrastructure.event_bus import EventBus


class ExecutionResult(TypedDict):
    """Estrutura contendo o resultado da execução."""

    files: List[str]
    seed: Optional[str]
    generation_time: Optional[str]
    error: Optional[str]
    command: Optional[str]


class SDRunner(IGenerator):
    """
    Controlador do processo de geração via CLI (não-servidor).
    """

    def __init__(self, executable_path: str) -> None:
        """Logic: Initializes runner."""
        self.executable_path: str = executable_path
        self.process: Optional[subprocess.Popen[str]] = None
        self.stop_event: threading.Event = threading.Event()
        self.log_handler = SDLogEventHandler()
        self._times: List[str] = []

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def run(
        self,
        model_path: str,
        prompt: str,
        params: List[Dict[str, str]],
        output_path: str,
        log_file_path: Optional[str],
        on_finish: Callable[[bool, ExecutionResult], None],
    ) -> None:
        """
        Executa o processo de geração de imagem em uma thread separada.

        Logic: Constructs command and starts worker thread."""
        self.stop_event.clear()
        cmd = [
            self.executable_path,
            "-m",
            model_path,
            "-p",
            prompt,
            "-o",
            output_path,
        ]
        for p in params:
            val = p.get("value")
            if val is not None:
                cmd.extend([p["flag"], str(val)])
            else:
                cmd.append(p["flag"])
        thread = threading.Thread(
            target=self._worker,
            args=(cmd, log_file_path, on_finish),
            daemon=True,
        )
        self._times.clear()
        thread.start()

    def stop(self) -> None:
        """Encerra o processo de forma segura.

        Logic: Stops process."""
        self.stop_event.set()
        if self.process:
            try:
                self.process.terminate()
            except OSError:
                pass

    def _worker(
        self,
        cmd: List[str],
        log_path: Optional[str],
        finish_cb: Callable[[bool, ExecutionResult], None],
    ) -> None:
        """
        Lógica do thread de trabalho.
        Logic: Executes subprocess, reads stdout, handles logs, and calls
        finish callback.
        """
        result: ExecutionResult = {
            "files": [],
            "seed": None,
            "generation_time": None,
            "error": None,
            "command": shlex.join(cmd),
        }
        log_file: Optional[TextIO] = None
        if log_path:
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                log_file = open(log_path, "w", encoding="utf-8")
                log_file.write(f"CMD: {result['command']}\n{'=' * 40}\n")
            except IOError:
                EventBus.publish(
                    "log_message",
                    {"text": "Error opening local log file.", "level": "ERROR"},
                )

        # FIX: Hide console window on Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()  # type: ignore
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,  # Apply fix
            )
            if self.process.stdout:
                while True:
                    if self.stop_event.is_set():
                        break
                    line = self.process.stdout.readline()
                    if not line and self.process.poll() is not None:
                        break
                    if line:
                        clean_line = self.log_handler.parser.clean_line(line)
                        if log_file:
                            log_file.write(clean_line)
                            log_file.flush()
                        parsed = self.log_handler.handle_line(line)
                        self._update_result_from_log(parsed, result)
            rc = self.process.poll()
            success = rc == 0 and (not self.stop_event.is_set())
            if self._times:
                result["generation_time"] = self._times[-1]
            finish_cb(success, result)
        except (OSError, RuntimeError) as err:
            EventBus.publish(
                "log_message", {"text": f"FATAL ERROR: {err}", "level": "ERROR"}
            )
            result["error"] = str(err)
            finish_cb(False, result)
        finally:
            if log_file:
                log_file.close()

    def _update_result_from_log(
        self, parsed: Dict[str, Any], result: ExecutionResult
    ) -> None:
        """Updates the local result object based on the parsed log data.

        Logic: Updates result dict from parsed logs."""
        p_type = parsed.get("type")
        if p_type == "file_saved":
            result["files"].append(str(parsed["path"]))
        elif p_type == "seed":
            result["seed"] = str(parsed["seed"])
        elif p_type == "error":
            result["error"] = str(parsed.get("message", "Unknown Error"))
        elif p_type == "success":
            self._times.append(str(parsed.get("raw", "")))
