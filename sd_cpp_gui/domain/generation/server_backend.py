import base64
import json
import os
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional, TextIO, Tuple

import requests

from sd_cpp_gui.data.db.settings_manager import SettingsManager
from sd_cpp_gui.domain.generation.engine import ExecutionResult
from sd_cpp_gui.domain.generation.interfaces import IGenerator
from sd_cpp_gui.domain.generation.process_manager import ServerProcessManager
from sd_cpp_gui.infrastructure.event_bus import EventBus


class SDServerRunner(IGenerator):
    """
    Generator implementation that communicates with a local or remote
    stable-diffusion.cpp HTTP server.
    """

    def __init__(
        self,
        executable_path: str,
        flags_mapping: Dict[str, Any],
        settings_manager: SettingsManager,
    ) -> None:
        """Logic: Initializes runner."""
        self.manager = ServerProcessManager()
        self.executable_path = executable_path
        self.stop_event = threading.Event()
        self.mapping = flags_mapping
        self.settings = settings_manager

    def _get_base_url(self) -> str:
        """Logic: Constructs base URL from settings."""
        host = self.settings.get("server_host", "127.0.0.1")
        port = self.settings.get("server_port", "1234")
        return f"http://{host}:{port}"

    def run(
        self,
        model_path: str,
        prompt: str,
        params: List[Dict[str, Any]],
        output_path: str,
        log_file_path: Optional[str],
        on_finish: Callable[[bool, ExecutionResult], None],
    ) -> None:
        """
        Prepares the server and starts the generation worker.
        Logic: Ensures server is running and starts worker thread."""
        self.stop_event.clear()
        if not self.executable_path or not os.path.exists(self.executable_path):
            self._finish_with_error(on_finish, "Server executable not found.")
            return
        startup_args_list = ["--model", model_path]
        api_params: List[Dict[str, Any]] = []
        init_img_path: Optional[str] = None
        int_flags = [
            "--steps",
            "--batch-count",
            "--clip-skip",
            "--width",
            "--height",
        ]
        float_flags = [
            "--cfg-scale",
            "--guidance",
            "--strength",
            "--control-strength",
        ]
        for p in params:
            flag = p["flag"]
            raw_val = p.get("value")
            val = str(raw_val).strip() if raw_val is not None else ""
            if flag in ["--init-img", "-i"]:
                init_img_path = val
            config = self.mapping.get(flag)
            if not config:
                api_params.append(p)
                continue
            ptype = config.get("type")
            if ptype == "startup_arg":
                startup_args_list.append(flag)
                if val:
                    startup_args_list.append(val)
            elif ptype in ["api_standard", "api_injected"]:
                if val:
                    if flag in int_flags:
                        try:
                            p["value"] = int(float(val))
                        except ValueError:
                            pass
                    elif flag in float_flags:
                        try:
                            p["value"] = float(val)
                        except ValueError:
                            pass
                api_params.append(p)
        host = self.settings.get("server_host", None) or "127.0.0.1"
        port = int(self.settings.get("server_port", None) or 1234)
        process_mode = self.settings.get("server_process_mode", "start_local")
        if process_mode == "start_local":
            if not self.manager.ensure_running(
                self.executable_path, startup_args_list, host, port
            ):
                self._finish_with_error(
                    on_finish, "Failed starting server process."
                )
                return
        else:
            try:
                requests.get(f"{self._get_base_url()}/v1/models", timeout=2)
            except requests.RequestException:
                self._finish_with_error(
                    on_finish, "External server unreachable."
                )
                return
        threading.Thread(
            target=self._worker,
            args=(
                prompt,
                api_params,
                output_path,
                on_finish,
                self._get_base_url(),
                log_file_path,
                init_img_path,
            ),
            daemon=True,
        ).start()

    def _finish_with_error(
        self, callback: Callable[[bool, ExecutionResult], None], msg: str
    ) -> None:
        """Helper to return an error result and log the event.

        Logic: Calls finish callback with error."""
        EventBus.publish(
            "log_message", {"text": f"Error: {msg}", "level": "ERROR"}
        )
        callback(
            False,
            {
                "error": msg,
                "files": [],
                "seed": None,
                "generation_time": None,
                "command": None,
            },
        )

    def _worker(
        self,
        prompt: str,
        params: List[Dict[str, Any]],
        output_path: str,
        finish_cb: Callable[[bool, ExecutionResult], None],
        base_url: str,
        log_path: Optional[str],
        init_img_path: Optional[str],
    ) -> None:
        """
        Background thread to handle the API request and response streaming.

        Logic: Sends API request and handles response stream.
        """
        start_time = time.time()
        log_file: Optional[TextIO] = None
        EventBus.publish(
            "log_message",
            {"text": f"Sending request to {base_url}...", "level": "INFO"},
        )
        if log_path:
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                log_file = open(log_path, "w", encoding="utf-8")
                self.manager.set_current_log_file(log_file)
            except IOError:
                pass
        try:
            payload, seed_val = self._construct_payload(
                prompt, params, self.mapping
            )
            req_kwargs: Dict[str, Any] = {"stream": True, "timeout": None}
            api_url = f"{base_url}/v1/images/generations"
            if init_img_path and os.path.exists(init_img_path):
                api_url = f"{base_url}/v1/images/edits"
                with open(init_img_path, "rb") as f_img:
                    req_kwargs["files"] = {
                        "image[]": (
                            os.path.basename(init_img_path),
                            f_img,
                            "image/png",
                        )
                    }
                    req_kwargs["data"] = payload
                    resp = requests.post(api_url, **req_kwargs)
            else:
                req_kwargs["json"] = payload
                resp = requests.post(api_url, **req_kwargs)
            self._handle_stream(
                resp, output_path, seed_val, start_time, finish_cb
            )
        except Exception as e:
            self._finish_with_error(finish_cb, str(e))
        finally:
            self.manager.set_current_log_file(None)
            if log_file:
                log_file.close()

    def _construct_payload(
        self, prompt: str, params: List[Dict[str, Any]], mapping: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], int]:
        """Constructs the JSON payload for the API.

        Logic: Builds API payload dictionary from parameters."""
        std: Dict[str, Any] = {}
        inj: Dict[str, Any] = {}
        seed = -1
        for p in params:
            flag = p["flag"]
            val = p.get("value")
            if val is None:
                val = ""
            config = mapping.get(flag, {})
            key = config.get("key", flag.lstrip("-").replace("-", "_"))
            ptype = config.get("type", "api_injected")
            if flag == "--seed":
                try:
                    seed = int(str(val or 0))
                except (ValueError, TypeError):
                    seed = -1
                continue
            if ptype == "api_standard":
                std[key] = val
            elif ptype == "api_injected":
                inj[key] = val
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)
        std["seed"] = seed
        inj["seed"] = seed
        extra_json = json.dumps(inj)
        full_prompt = (
            f"{prompt} <sd_cpp_extra_args>{extra_json}</sd_cpp_extra_args>"
        )
        payload = {"prompt": full_prompt, "output_format": "png"}
        if "width" in std and "height" in std:
            payload["size"] = f"{std.pop('width')}x{std.pop('height')}"
        payload.update(std)
        return (payload, seed)

    def _handle_stream(
        self,
        resp: requests.Response,
        output_path: str,
        seed: int,
        start_time: float,
        cb: Callable[[bool, ExecutionResult], None],
    ) -> None:
        """
        Parses the Server-Sent Events (SSE) or chunked JSON response.
        Logic: Consumes stream, processes logs, saves image, and calls
        finish callback.
        """
        if resp.status_code != 200:
            self._finish_with_error(cb, f"Server Error {resp.status_code}")
            return
        final_json: Optional[str] = None
        try:
            for line in resp.iter_lines(decode_unicode=True):
                if self.stop_event.is_set():
                    resp.close()
                    self._finish_with_error(cb, "Stopped")
                    return
                if not line:
                    continue
                if line.strip().startswith("{") and '"data"' in line:
                    final_json = line
                    break
                else:
                    self.manager.process_line(line)
        except Exception as e:
            self._finish_with_error(cb, f"Stream Error: {e}")
            return
        if final_json:
            try:
                data = json.loads(final_json)
                b64 = data["data"][0]["b64_json"]
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(b64))
                EventBus.publish(
                    "log_message",
                    {"text": f"Image saved: {output_path}", "level": "SUCCESS"},
                )
                elapsed = f"{time.time() - start_time:.2f}s"
                cb(
                    True,
                    {
                        "files": [output_path],
                        "generation_time": elapsed,
                        "command": f"API (Seed: {seed})",
                        "seed": str(seed),
                        "error": None,
                    },
                )
            except (json.JSONDecodeError, KeyError, IndexError, IOError) as e:
                self._finish_with_error(cb, f"Output Processing Error: {e}")
        else:
            self._finish_with_error(cb, "No image data received from server")

    def stop(self) -> None:
        """Signals the generation to stop.

        Logic: Sets stop event."""
        self.stop_event.set()
