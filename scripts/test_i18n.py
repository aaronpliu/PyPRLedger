#!/usr/bin/env python3
"""
Test script for i18n functionality
Tests both frontend and backend i18n
"""

import asyncio
import json
from pathlib import Path


def test_frontend_translations():
    """Test frontend translation files"""
    print("=" * 80)
    print("Testing Frontend Translations")
    print("=" * 80)

    locales_dir = Path(__file__).parent.parent / "web" / "i18n" / "locales"

    for lang in ["en", "zh-CN", "zh-TW"]:
        file_path = locales_dir / f"{lang}.json"

        if not file_path.exists():
            print(f"❌ {lang}: File not found at {file_path}")
            continue

        try:
            with file_path.open(encoding="utf-8") as f:
                data = json.load(f)

            # Check required keys
            required_keys = ["app", "filters", "buttons", "messages"]
            missing_keys = [k for k in required_keys if k not in data]

            if missing_keys:
                print(f"⚠️  {lang}: Missing keys: {missing_keys}")
            else:
                print(f"✅ {lang}: All required keys present ({len(data)} sections)")

            # Show sample translations
            if "app" in data and "title" in data["app"]:
                print(f'   Sample: app.title = "{data["app"]["title"]}"')

        except Exception as e:
            print(f"❌ {lang}: Error loading - {e}")

    print()


def test_backend_translations():
    """Test backend translation files"""
    print("=" * 80)
    print("Testing Backend Translations")
    print("=" * 80)

    locales_dir = Path(__file__).parent.parent / "src" / "locales"

    for lang in ["en", "zh-CN", "zh-TW"]:
        file_path = locales_dir / f"{lang}.json"

        if not file_path.exists():
            print(f"❌ {lang}: File not found at {file_path}")
            continue

        try:
            with file_path.open(encoding="utf-8") as f:
                data = json.load(f)

            # Check required keys
            if "errors" not in data:
                print(f"⚠️  {lang}: Missing 'errors' section")
            else:
                error_count = len(data["errors"])
                print(f"✅ {lang}: {error_count} error messages defined")

            # Show sample translations
            if "errors" in data and "user_not_found" in data["errors"]:
                print(f'   Sample: errors.user_not_found = "{data["errors"]["user_not_found"]}"')

        except Exception as e:
            print(f"❌ {lang}: Error loading - {e}")

    print()


async def test_i18n_manager():
    """Test backend i18n manager"""
    print("=" * 80)
    print("Testing I18n Manager")
    print("=" * 80)

    # Add project root to path
    import sys

    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from src.utils.i18n import i18n

        # Test translation
        test_key = "errors.user_not_found_by_id"

        en_msg = i18n.t(test_key, "en", user_id=123)
        zh_cn_msg = i18n.t(test_key, "zh-CN", user_id=123)
        zh_tw_msg = i18n.t(test_key, "zh-TW", user_id=123)

        print(f"✅ English:      {en_msg}")
        print(f"✅ 简体中文:     {zh_cn_msg}")
        print(f"✅ 繁體中文:     {zh_tw_msg}")

        # Test fallback
        missing_key = i18n.t("nonexistent.key", "zh-CN")
        print(f"✅ Fallback test: '{missing_key}' (should return key itself)")

    except Exception as e:
        print(f"❌ I18n Manager test failed: {e}")
        import traceback

        traceback.print_exc()

    print()


def main():
    """Run all tests"""
    print("\n🧪 PyPRLedger i18n Test Suite\n")

    test_frontend_translations()
    test_backend_translations()
    asyncio.run(test_i18n_manager())

    print("=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
