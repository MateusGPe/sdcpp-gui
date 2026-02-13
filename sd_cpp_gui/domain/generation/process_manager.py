import atexit
import os
import socket
import subprocess
import threading
import time
from typing import List, Optional, Self, TextIO

import requests

from sd_cpp_gui.domain.generation.log_handler import SDLogEventHandler
from sd_cpp_gui.infrastructure.event_bus import EventBus
from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.infrastructure.paths import LOGS_DIR

logger = get_logger(__name__)


class ServerProcessManager:
    """
    Singleton responsible for the sd-server process lifecycle.
    """

    _instance: Optional[Self] = None
    _process: Optional[subprocess.Popen] = None
    _current_startup_args: List[str] = []
    _current_host: str = "127.0.0.1"
    _current_port: int = 1234
    _current_log_file: Optional[TextIO] = None
    _lock = threading.RLock()
    _log_thread: Optional[threading.Thread] = None
    _session_log_file: Optional[TextIO] = None
    _log_handler: SDLogEventHandler = SDLogEventHandler()

    def __new__(cls):
        """Logic: Singleton instantiation."""
        if cls._instance is None:
            cls._instance = super(ServerProcessManager, cls).__new__(cls)
            atexit.register(cls._instance.stop)
        return cls._instance

    def set_current_log_file(self, file_obj: Optional[TextIO]) -> None:
        """Logic: Sets current log file."""
        with self._lock:
            self._current_log_file = file_obj

    def _open_session_log(self) -> None:
        """Logic: Opens session log file."""
        if self._session_log_file is None:
            try:
                log_path = os.path.join(LOGS_DIR, "server_session.log")
                self._session_log_file = open(log_path, "a", encoding="utf-8")
                str_time: str = time.strftime("%Y-%m-%d %H:%M:%S")
                self._session_log_file.write(
                    f"\n--- NEW SESSION: {str_time} ---\n"
                )
            except IOError as e:
                logger.error("Failed to open server session log: %s", e)

    def _close_session_log(self) -> None:
        """Logic: Closes session log file."""
        if self._session_log_file:
            try:
                self._session_log_file.close()
            except IOError:
                pass
            self._session_log_file = None

    def process_line(self, line: str) -> None:
        """Delegates processing to the standardized handler.

        Logic: Processes log line."""
        self._log_handler.handle_line(line)

    def write_log(self, message: str, level: str = "INFO") -> None:
        """Logic: Writes log to file."""
        target_log = (
            self._current_log_file
            if self._current_log_file
            else self._session_log_file
        )
        if target_log:
            try:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                target_log.write(f"[{timestamp}] [{level}] {message}\n")
                target_log.flush()
            except (IOError, ValueError):
                pass

    def _log_reader(self, stream: TextIO) -> None:
        """Logic: Reads stdout logs in background thread."""
        try:
            for line in iter(stream.readline, ""):
                if self._process is None:
                    break
                clean_line = line.strip()
                if not clean_line:
                    continue
                self.write_log(clean_line)
                self.process_line(clean_line)
        except (IOError, ValueError):
            pass

    def get_base_url(self) -> str:
        """Logic: Returns base URL."""
        with self._lock:
            return f"http://{self._current_host}:{self._current_port}"

    def is_running(self) -> bool:
        """Logic: Checks if process is running."""
        with self._lock:
            if self._process is None:
                return False
            if self._process.poll() is not None:
                return False
            return True

    def ensure_running(
        self,
        executable_path: str,
        startup_args_list: List[str],
        host: str,
        port: int,
    ) -> bool:
        """Logic: Ensures server process is running with correct args."""
        normalized_new_args = sorted(startup_args_list)
        with self._lock:
            if self.is_running():
                config_changed = (
                    self._current_startup_args != normalized_new_args
                    or self._current_host != host
                    or self._current_port != port
                )
                if not config_changed:
                    if self._check_health():
                        return True
                    self.stop()
                else:
                    self.stop()
            return self._start(
                executable_path,
                startup_args_list,
                normalized_new_args,
                host,
                port,
            )

    def _check_health(self) -> bool:
        """Logic: Checks server health endpoint."""
        try:
            url = self.get_base_url()
            resp = requests.get(f"{url}/", timeout=2)
            return resp.status_code in [200, 404]
        except requests.RequestException:
            return False

    def _wait_for_port_release(
        self, host: str, port: int, timeout: int = 5
    ) -> bool:
        """Logic: Waits for port to be free."""
        start = time.time()
        while time.time() - start < timeout:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex((host, port)) != 0:
                    return False
            time.sleep(0.5)
        return True

    def _start(
        self,
        executable_path: str,
        args: List[str],
        signature: List[str],
        host: str,
        port: int,
    ) -> bool:
        """Logic: Starts server process."""
        if self._wait_for_port_release(host, port, timeout=5):
            EventBus.publish(
                "log_message",
                {"text": f"Port {port} in use.", "level": "ERROR"},
            )
            return False
        self._current_host = host
        self._current_port = port
        self._open_session_log()
        cmd = [
            executable_path,
            "--listen-ip",
            host,
            "--listen-port",
            str(port),
        ] + args

        # FIX: Hide console window on Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()  # type: ignore
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,  # Apply fix
            )
            self._current_startup_args = signature
            self._log_thread = threading.Thread(
                target=self._log_reader,
                args=(self._process.stdout,),
                daemon=True,
            )
            self._log_thread.start()
            start_wait = time.time()
            while time.time() - start_wait < 30:
                if self._check_health():
                    EventBus.publish(
                        "log_message",
                        {"text": "Server Online.", "level": "SUCCESS"},
                    )
                    return True
                if self._process.poll() is not None:
                    self.stop()
                    return False
                time.sleep(0.5)
            self.stop()
            return False
        except Exception:
            self.stop()
            return False

    def stop(self) -> None:
        """Logic: Stops server process and cleans up."""
        with self._lock:
            proc = self._process
            self._process = None
            if proc:
                try:
                    if os.name == "nt":
                        subprocess.call(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)]
                        )
                    else:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                if proc.stdout:
                    try:
                        proc.stdout.close()
                    except Exception:
                        pass
            if self._log_thread and self._log_thread.is_alive():
                self._log_thread.join(timeout=1.0)
            self._current_startup_args = []
            self._close_session_log()
