"""
Main Application Package.
"""

from .coordinator import AppCoordinator

# Alias for backward compatibility with existing main.py entry points
App = AppCoordinator

__all__ = ["App", "AppCoordinator"]
