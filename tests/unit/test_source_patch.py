import shutil

from helpers import source_patch


def test_patch_runtime_source_applies_v8_without_legacy_plugin_root(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(_runtime_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}

    result = source_patch.patch_runtime_source(manifest)

    text = runtime.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert result["patch_version"] == "8"
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


def test_patch_runtime_source_upgrades_old_marker_and_helper(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(
        _runtime_source().replace(
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


def test_restore_runtime_source_patch_requires_matching_hash(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    original = _runtime_source()
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


def _runtime_source() -> str:
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
