"""
Configures the global logging system.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger instance for the module.

    Logic: Returns a namespaced logger."""
    return logging.getLogger(f"sd_cpp_gui.{name}")


def setup_logging(
    log_file: Path = Path("./app.log"), level: int = logging.INFO
) -> None:
    """
    Configures the global logging system.

    Logic: Sets up rotating file and console handlers
    for logging.
    """
    from sd_cpp_gui.infrastructure.i18n import I18nManager, get_i18n

    i18n: I18nManager = get_i18n()
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d]"
        " %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger = logging.getLogger("sd_cpp_gui")
    root_logger.setLevel(level)
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
    root_logger.info(i18n.get("log.init", "Logger initialized."))
