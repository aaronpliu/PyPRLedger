"""
I18n Manager for Backend
Supports multi-language error messages based on Accept-Language header
"""

import json
import logging
from pathlib import Path

from fastapi import Request


logger = logging.getLogger(__name__)


class I18nManager:
    """Backend i18n manager for translating error messages"""

    def __init__(self):
        self.translations: dict[str, dict] = {}
        self.supported_locales = ["en", "zh-CN", "zh-TW"]
        self.fallback_locale = "en"
        self._load_all_translations()

    def _load_all_translations(self) -> None:
        """Load all translation files"""
        locales_dir = Path(__file__).parent.parent / "locales"

        if not locales_dir.exists():
            logger.warning(f"Locales directory not found: {locales_dir}")
            return

        for lang_file in locales_dir.glob("*.json"):
            lang_code = lang_file.stem
            if lang_code in self.supported_locales:
                try:
                    with lang_file.open(encoding="utf-8") as f:
                        self.translations[lang_code] = json.load(f)
                    logger.info(f"Loaded translations for: {lang_code}")
                except Exception as e:
                    logger.error(f"Failed to load translations for {lang_code}: {e}")

    def get_language_from_request(self, request: Request) -> str:
        """
        Extract language preference from Accept-Language header
        Priority: zh-TW > zh-CN > en
        """
        accept_lang = request.headers.get("accept-language", "").lower()

        if not accept_lang:
            return self.fallback_locale

        # Check for Traditional Chinese
        if "zh-tw" in accept_lang or "zh-hk" in accept_lang or "zh-hant" in accept_lang:
            return "zh-TW"

        # Check for Simplified Chinese
        if (
            "zh-cn" in accept_lang
            or "zh-hans" in accept_lang
            or ("zh" in accept_lang and "tw" not in accept_lang and "hk" not in accept_lang)
        ):
            return "zh-CN"

        # Default to English
        return "en"

    def t(self, key: str, lang: str | None = None, **params) -> str:
        """
        Translate a key to the specified language

        Args:
            key: Translation key (dot-separated, e.g., "errors.user_not_found")
            lang: Language code (auto-detected if None)
            **params: Parameters for string interpolation

        Returns:
            Translated string
        """
        if not lang:
            lang = self.fallback_locale

        keys = key.split(".")

        # Try current language first
        value = self._get_nested_value(self.translations.get(lang, {}), keys)

        # Fallback to English if translation not found
        if not value and lang != self.fallback_locale:
            value = self._get_nested_value(self.translations.get(self.fallback_locale, {}), keys)

        # If still not found, return the key itself
        if not value:
            logger.warning(f"Missing translation for key: {key} in {lang}")
            return key

        # Replace parameters {param} with actual values
        if params and isinstance(value, str):
            for param_key, param_value in params.items():
                value = value.replace(f"{{{param_key}}}", str(param_value))

        return value

    @staticmethod
    def _get_nested_value(obj: dict, keys: list[str]) -> str | None:
        """Get nested value from dict using list of keys"""
        if not obj or not keys:
            return None

        value = obj
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]

        return value if isinstance(value, str) else None


# Global instance
i18n = I18nManager()
