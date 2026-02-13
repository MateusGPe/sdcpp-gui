"""
Internationalization (i18n) manager.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, cast

from sd_cpp_gui.infrastructure.logger import get_logger
from sd_cpp_gui.infrastructure.paths import LOCALES_DIR

logger = get_logger(__name__)


class I18nManager:
    """Manages application languages and translations."""

    def __init__(
        self, locales_dir: Path, default_locale: str = "en_US"
    ) -> None:
        """Logic: Initializes manager and loads default locale."""
        self.translations: Dict[str, str] = {}
        self.locales_dir = locales_dir
        # Note: Do not try to create locales_dir here, as it might
        # be read-only in _MEIPASS
        self.current_locale: str = default_locale
        self.load_locale(self.current_locale)

    def load_locale(self, locale_code: str) -> None:
        """Loads a JSON translation file.

        Logic: Loads translation dict from JSON file."""
        path = self.locales_dir / f"{locale_code}.json"

        # Fallback logic
        if not path.exists():
            logger.warning("Language file not found: %s", path)
            path = self.locales_dir / f"{self.current_locale}.json"
            if not path.exists():
                # Try default en_US if current fallback failed
                path = self.locales_dir / "en_US.json"
                if not path.exists():
                    logger.error("Default language file not found: %s", path)
                    return

        try:
            with open(path, "r", encoding="utf-8") as f:
                self.translations = cast(Dict[str, str], json.load(f))
            self.current_locale = locale_code
            logger.info("Language loaded: %s", locale_code)
        except (IOError, json.JSONDecodeError) as e:
            logger.error(
                "Loading error for locale %s: %s", locale_code, e, exc_info=True
            )

    def get(self, key: str, default: Optional[str] = None) -> str:
        """
        Returns the translation for the key.

        Logic: Returns translated string or default/key if missing.
        """
        if key not in self.translations:
            # logger.warning('Translation key not found: "%s"', key)
            pass
        return self.translations.get(
            key, default if default is not None else key
        )

    def get_locales(self) -> List[str]:
        """Returns a list of available locales based on file existence.

        Logic: Lists available json locale files."""
        if not self.locales_dir.exists():
            return ["en_US"]

        return [
            path.stem
            for path in self.locales_dir.glob("*.json")
            if path.is_file()
        ]


I18N_MANAGER = I18nManager(LOCALES_DIR)


def get_i18n() -> I18nManager:
    """Returns the global I18nManager instance.

    Logic: Returns singleton instance."""
    return I18N_MANAGER
