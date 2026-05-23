import shutil
from pathlib import Path

from helpers import source_patch, validation


def test_patch_runtime_source_applies_current_patch_without_legacy_plugin_root(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(_old_runtime_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}

    result = source_patch.patch_runtime_source(manifest)

    text = runtime.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert result["patch_version"] == source_patch.PATCH_VERSION
    assert source_patch.PATCH_MARKER in text
    assert 'find_plugin_dir("cloakbrowser")' in text
    assert "/a0/usr/plugins/cloakbrowser" not in text
    assert "launch_persistent_context(" in text
    assert "Browser context could not open a new tab; restarting." in text
    assert "_cloakbrowser_open_restart_lock" in text
    assert "_cloakbrowser_expected_context_close" in text
    assert "gc.collect()" in text
    assert manifest["runtime_source_patch"]["target_path"] == str(runtime)
    assert manifest["runtime_patches"][0]["kind"] == "source_runtime"

    second = source_patch.patch_runtime_source(manifest)
    assert second["already_patched"] is True
    assert second["backup_path"] == result["backup_path"]


def test_patch_runtime_source_rebuilds_metadata_for_existing_patch(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    original = _current_runtime_source()
    runtime.write_text(original, encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    source_patch.patch_runtime_source({})

    manifest = {}
    result = source_patch.patch_runtime_source(manifest)

    backup = result["backup_path"]
    assert result["already_patched"] is True
    assert backup
    assert source_patch.sha256_file(runtime) == result["patched_hash"]
    backup_hash = source_patch.sha256_file(tmp_path / ".cloakbrowser-backups" / Path(backup).name)
    assert backup_hash == result["original_hash"]
    assert validation.validate_runtime_patch(manifest)["ok"] is True


def test_patch_runtime_source_upgrades_old_marker_and_helper(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(
        _old_runtime_source().replace(
            'CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"\n',
            """
# CLOAKBROWSER_SOURCE_PATCH_V7: start
def _cloakbrowser_source_runtime():
    return "old-helper"
# CLOAKBROWSER_SOURCE_PATCH_V7: end
""",
        ).replace(source_patch.OPEN_ORIGINAL, source_patch.OPEN_PATCHED_V1),
        encoding="utf-8",
    )
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}

    result = source_patch.patch_runtime_source(manifest)

    text = runtime.read_text(encoding="utf-8")
    assert result["upgraded"] is True
    assert source_patch.PATCH_MARKER in text
    assert "CLOAKBROWSER_SOURCE_PATCH_V7" not in text
    assert "old-helper" not in text
    assert "_cloakbrowser_open_restart_lock" in text


def test_patch_runtime_source_upgrades_v10_without_marker_corruption(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    v10_text = source_patch.patch_runtime_source_text(_old_runtime_source()).replace(
        source_patch.PATCH_MARKER,
        "CLOAKBROWSER_SOURCE_PATCH_V10",
    )
    runtime.write_text(v10_text, encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}

    result = source_patch.patch_runtime_source(manifest)

    text = runtime.read_text(encoding="utf-8")
    assert result["upgraded"] is True
    assert source_patch.PATCH_MARKER in text
    assert "CLOAKBROWSER_SOURCE_PATCH_V110" not in text
    assert "spec_from_file_location" in text
    assert '"_cloakbrowser_plugin_imports"' in text
    assert "_cloakbrowser_dir + \"/plugin_imports.py\"" in text
    assert "_cloakbrowser_sys.path.append(_cloakbrowser_dir)" not in text
    assert "_cloakbrowser_sys.path.insert(0, _cloakbrowser_dir)" not in text


def test_source_runtime_helper_does_not_import_ambient_plugin_imports():
    helper = source_patch.SOURCE_RUNTIME_HELPER

    assert "from plugin_imports import" not in helper
    assert "spec_from_file_location" in helper
    assert '"_cloakbrowser_plugin_imports"' in helper
    assert '"/plugin_imports.py"' in helper


def test_restore_runtime_source_patch_requires_matching_hash(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    original = _old_runtime_source()
    runtime.write_text(original, encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}
    source_patch.patch_runtime_source(manifest)
    runtime.write_text(runtime.read_text(encoding="utf-8") + "# user edit\n", encoding="utf-8")

    skipped = source_patch.restore_runtime_source_patch(manifest)

    assert skipped["restored"] is False
    assert skipped["reason"] == "current_hash_mismatch"

    shutil.copy2(manifest["runtime_source_patch"]["backup_path"], runtime)
    source_patch.patch_runtime_source(manifest)
    restored = source_patch.restore_runtime_source_patch(manifest)

    assert restored["restored"] is True
    assert runtime.read_text(encoding="utf-8") == original


def test_patch_runtime_source_supports_current_agent_zero_runtime(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(_current_runtime_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}

    result = source_patch.patch_runtime_source(manifest)

    text = runtime.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert source_patch.PATCH_MARKER in text
    assert source_patch.CONTENT_HELPER_PATCHED in text
    assert "self._ensure_can_open_page()" in text
    assert "Browser context could not open a new tab; restarting." in text
    assert "_cloakbrowser_open_restart_lock" in text
    assert "_cloakbrowser_expected_context_close" in text


def test_patch_runtime_source_upgrades_v8_content_helper_guard(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    v8_source = (
        source_patch.patch_runtime_source_text(_current_runtime_source())
        .replace(source_patch.PATCH_MARKER, "CLOAKBROWSER_SOURCE_PATCH_V8")
        .replace(source_patch.CONTENT_HELPER_PATCHED, source_patch.CONTENT_HELPER_ORIGINAL)
    )
    runtime.write_text(
        v8_source,
        encoding="utf-8",
    )
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}

    result = source_patch.patch_runtime_source(manifest)

    text = runtime.read_text(encoding="utf-8")
    assert result["upgraded"] is True
    assert source_patch.PATCH_MARKER in text
    assert "CLOAKBROWSER_SOURCE_PATCH_V8" not in text
    assert source_patch.CONTENT_HELPER_PATCHED in text


def test_patch_runtime_source_repairs_markerless_partial_patch(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    markerless_partial = source_patch.patch_runtime_source_text(_current_runtime_source())
    markerless_partial = markerless_partial.replace(source_patch.SOURCE_RUNTIME_HELPER, "\n")
    runtime.write_text(markerless_partial, encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}

    result = source_patch.patch_runtime_source(manifest)

    text = runtime.read_text(encoding="utf-8")
    assert result["upgraded"] is True
    assert source_patch.PATCH_MARKER in text
    assert source_patch.LAUNCH_PATCHED in text
    assert source_patch.CONTENT_HELPER_PATCHED in text
    assert source_patch.OPEN_PATCHED_WITH_LIMIT in text


def _old_runtime_source() -> str:
    return f"""
from __future__ import annotations

import asyncio

CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"


class _BrowserRuntimeCore:
{source_patch.LAUNCH_ORIGINAL}
{source_patch.SHADOW_ORIGINAL}
{source_patch.START_PAGES_ORIGINAL}
{source_patch.OPEN_ORIGINAL}
        await self._settle(page)
        return {{"id": browser_page.id, "state": await self._state(browser_page.id)}}

{source_patch.CLOSE_BROWSER_ORIGINAL}
{source_patch.CLOSE_ALL_ORIGINAL}
{source_patch.CONTEXT_CLOSED_ORIGINAL}
{source_patch.STOP_PLAYWRIGHT_ORIGINAL}
"""


def _current_runtime_source() -> str:
    return f"""
from __future__ import annotations

import asyncio

CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"


class _BrowserRuntimeCore:
{source_patch.LAUNCH_ORIGINAL}
{source_patch.CONTENT_HELPER_ORIGINAL}
{source_patch.START_PAGES_ORIGINAL}
{source_patch.OPEN_ORIGINAL_WITH_LIMIT}
        self.last_interacted_browser_id = browser_page.id
        if url:
            await self._goto(browser_page, url)
        return {{"id": browser_page.id, "state": await self._state(browser_page.id)}}

{source_patch.CLOSE_BROWSER_ORIGINAL}
{source_patch.CLOSE_ALL_ORIGINAL}
{source_patch.CONTEXT_CLOSED_ORIGINAL}
{source_patch.STOP_PLAYWRIGHT_ORIGINAL}
"""
