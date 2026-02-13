from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, List

from sd_cpp_gui.domain.plugins.interface import IPlugin
from sd_cpp_gui.infrastructure.logger import get_logger

if TYPE_CHECKING:
    from sd_cpp_gui.infrastructure.di_container import DependencyContainer
logger = get_logger(__name__)


class PluginManager:
    """
    Manages the lifecycle and registry of plugins.
    """

    def __init__(self, container: DependencyContainer) -> None:
        """Logic: Initializes manager."""
        self.container = container
        self._plugins: List[IPlugin] = []
        self.plugins_map: dict[str, IPlugin] = {}

    def register(self, plugin: IPlugin) -> None:
        """
        Registers and initializes a plugin.

        Logic: Initializes plugin and adds to list.
        """
        try:
            manifest = plugin.manifest
            name = manifest.get("name", "Unknown Plugin")
            key = manifest.get("key")

            if key in self.plugins_map:
                return

            logger.info("Registering plugin: %s", name)
            plugin.initialize(self.container)
            self._plugins.append(plugin)
            self.plugins_map[key] = plugin
        except Exception as e:
            logger.error(
                "Failed to register plugin '%s': %s",
                plugin.manifest.get("name"),
                e,
                exc_info=True,
            )

    def get_active_plugins(self) -> List[IPlugin]:
        """Returns list of successfully registered plugins.

        Logic: Returns active plugins."""
        return self._plugins

    def discover_and_register(self, package_path: str) -> None:
        """
        Automatically discovers and registers plugins from a given package path.

        Logic: Iterates through modules in the package, finds classes
        implementing IPlugin, and registers them.
        """
        try:
            package = importlib.import_module(package_path)

            # Fix for PyInstaller: Ensure __path__ is iterable
            if not hasattr(package, "__path__"):
                logger.warning(
                    f"Plugin package {package_path} has no __path__."
                    " Skipping discovery."
                )
                return

            for _, module_name, _ in pkgutil.iter_modules(package.__path__):
                full_module_name = f"{package_path}.{module_name}"
                module = importlib.import_module(full_module_name)

                for _, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, IPlugin)
                        and obj is not IPlugin
                        and not inspect.isabstract(obj)
                        and obj.__module__ == module.__name__
                    ):
                        logger.info("Discovered plugin class: %s", obj.__name__)
                        self.register(obj())
        except Exception as e:
            logger.error(
                "Error during plugin discovery in %s: %s",
                package_path,
                e,
                exc_info=True,
            )
