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
    assert 'candidate_url == "about:blank"' in text
    assert "_cloakbrowser_expected_context_close" in text
    assert "gc.collect()" in text
    assert manifest["runtime_source_patch"]["target_path"] == str(runtime)
    assert manifest["runtime_patches"][0]["kind"] == "source_runtime"

    second = source_patch.patch_runtime_source(manifest)
    assert second["already_patched"] is True
    assert second["backup_path"] == result["backup_path"]


def test_patch_runtime_source_rebuilds_metadata_for_existing_patch(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    ws_browser = tmp_path / "ws_browser.py"
    browser_store = tmp_path / "browser-store.js"
    original = _current_runtime_source()
    runtime.write_text(original, encoding="utf-8")
    ws_browser.write_text(_ws_browser_source(), encoding="utf-8")
    browser_store.write_text(_browser_store_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    monkeypatch.setattr(source_patch, "browser_ws_source_path", lambda: ws_browser)
    monkeypatch.setattr(source_patch, "browser_store_source_path", lambda: browser_store)
    source_patch.patch_runtime_source({})

    manifest = {}
    result = source_patch.patch_runtime_source(manifest)
    source_patch.patch_ws_browser_source(manifest)
    source_patch.patch_browser_store_source(manifest)

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


def test_patch_runtime_source_upgrades_v16_helper(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    v16_text = source_patch.patch_runtime_source_text(_old_runtime_source()).replace(
        source_patch.PATCH_MARKER,
        "CLOAKBROWSER_SOURCE_PATCH_V16",
    )
    runtime.write_text(v16_text, encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)

    result = source_patch.patch_runtime_source({})

    text = runtime.read_text(encoding="utf-8")
    assert result["upgraded"] is True
    assert source_patch.PATCH_MARKER in text
    assert "CLOAKBROWSER_SOURCE_PATCH_V16" not in text
    assert "get_enabled_plugins(None)" in text
    assert "return None" in text


def test_source_runtime_helper_does_not_import_ambient_plugin_imports():
    helper = source_patch.SOURCE_RUNTIME_HELPER

    assert "from plugin_imports import" not in helper
    assert "spec_from_file_location" in helper
    assert '"_cloakbrowser_plugin_imports"' in helper
    assert '"/plugin_imports.py"' in helper


def test_source_runtime_helper_bypasses_when_plugin_is_disabled():
    helper = source_patch.SOURCE_RUNTIME_HELPER

    assert "get_enabled_plugins(None)" in helper
    assert "return None" in helper
    assert '"cloakbrowser"' in helper


def test_patch_ws_browser_source_dedupes_duplicate_keyboard_events(monkeypatch, tmp_path):
    ws_browser = tmp_path / "ws_browser.py"
    ws_browser.write_text(_ws_browser_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_ws_source_path", lambda: ws_browser)
    manifest = {}

    result = source_patch.patch_ws_browser_source(manifest)

    text = ws_browser.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert result["patch_version"] == source_patch.WS_PATCH_VERSION
    assert source_patch.WS_PATCH_MARKER in text
    assert "_last_keyboard_inputs" in text
    assert "viewer_id = str(data.get(\"viewer_id\") or sid or \"\")" in text
    assert "viewer_id," in text
    assert "keyboard_now - float(previous_keyboard.get(\"t\") or 0) < 0.025" in text
    assert manifest["ws_browser_source_patch"]["target_path"] == str(ws_browser)
    assert manifest["runtime_patches"][0]["kind"] == "source_ws_browser"

    second = source_patch.patch_ws_browser_source(manifest)
    assert second["already_patched"] is True
    assert second["backup_path"] == result["backup_path"]


def test_patch_ws_browser_source_rebuilds_metadata_for_existing_patch(monkeypatch, tmp_path):
    ws_browser = tmp_path / "ws_browser.py"
    ws_browser.write_text(_ws_browser_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_ws_source_path", lambda: ws_browser)
    source_patch.patch_ws_browser_source({})

    manifest = {}
    result = source_patch.patch_ws_browser_source(manifest)

    assert result["already_patched"] is True
    assert result["backup_path"]
    assert result["original_hash"]
    assert source_patch.sha256_file(Path(result["backup_path"])) == result["original_hash"]
    assert Path(result["backup_path"]).read_text(encoding="utf-8") == _ws_browser_source()


def test_patch_ws_browser_source_upgrades_v1_keyboard_signature(monkeypatch, tmp_path):
    ws_browser = tmp_path / "ws_browser.py"
    v1_text = source_patch.patch_ws_browser_source_text(_ws_browser_source()).replace(
        source_patch.WS_CLASS_PATCHED,
        source_patch.WS_CLASS_PATCHED_V1,
    ).replace(
        source_patch.WS_INPUT_PATCHED,
        source_patch.WS_INPUT_PATCHED_V1,
    )
    ws_browser.write_text(v1_text, encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_ws_source_path", lambda: ws_browser)

    result = source_patch.patch_ws_browser_source({})

    text = ws_browser.read_text(encoding="utf-8")
    assert result["upgraded"] is True
    assert source_patch.WS_PATCH_MARKER in text
    assert "CLOAKBROWSER_WS_SOURCE_PATCH_V1" not in text
    assert "viewer_id = str(data.get(\"viewer_id\") or sid or \"\")" in text
    assert "viewer_id," in text


def test_restore_ws_browser_source_patch_requires_matching_hash(monkeypatch, tmp_path):
    ws_browser = tmp_path / "ws_browser.py"
    original = _ws_browser_source()
    ws_browser.write_text(original, encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_ws_source_path", lambda: ws_browser)
    manifest = {}
    source_patch.patch_ws_browser_source(manifest)
    ws_browser.write_text(ws_browser.read_text(encoding="utf-8") + "# user edit\n", encoding="utf-8")

    skipped = source_patch.restore_ws_browser_source_patch(manifest)

    assert skipped["restored"] is False
    assert skipped["reason"] == "current_hash_mismatch"

    shutil.copy2(manifest["ws_browser_source_patch"]["backup_path"], ws_browser)
    source_patch.patch_ws_browser_source(manifest)
    restored = source_patch.restore_ws_browser_source_patch(manifest)

    assert restored["restored"] is True
    assert ws_browser.read_text(encoding="utf-8") == original


def test_patch_browser_store_source_marks_handled_keyboard_events(monkeypatch, tmp_path):
    browser_store = tmp_path / "browser-store.js"
    browser_store.write_text(_browser_store_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_store_source_path", lambda: browser_store)
    manifest = {}

    result = source_patch.patch_browser_store_source(manifest)

    text = browser_store.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert result["patch_version"] == source_patch.BROWSER_STORE_PATCH_VERSION
    assert source_patch.BROWSER_STORE_PATCH_MARKER in text
    assert "__cloakbrowserBrowserKeydownHandled" in text
    assert "viewer_id: this._viewerToken" in text
    assert manifest["browser_store_source_patch"]["target_path"] == str(browser_store)
    assert manifest["runtime_patches"][0]["kind"] == "source_browser_store"

    second = source_patch.patch_browser_store_source(manifest)
    assert second["already_patched"] is True
    assert second["backup_path"] == result["backup_path"]


def test_patch_browser_store_source_rebuilds_metadata_for_existing_patch(monkeypatch, tmp_path):
    browser_store = tmp_path / "browser-store.js"
    browser_store.write_text(_browser_store_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_store_source_path", lambda: browser_store)
    source_patch.patch_browser_store_source({})

    manifest = {}
    result = source_patch.patch_browser_store_source(manifest)

    assert result["already_patched"] is True
    assert result["backup_path"]
    assert result["original_hash"]
    assert source_patch.sha256_file(Path(result["backup_path"])) == result["original_hash"]
    assert Path(result["backup_path"]).read_text(encoding="utf-8") == _browser_store_source()


def test_restore_browser_store_source_patch_requires_matching_hash(monkeypatch, tmp_path):
    browser_store = tmp_path / "browser-store.js"
    original = _browser_store_source()
    browser_store.write_text(original, encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_store_source_path", lambda: browser_store)
    manifest = {}
    source_patch.patch_browser_store_source(manifest)
    browser_store.write_text(browser_store.read_text(encoding="utf-8") + "// user edit\n", encoding="utf-8")

    skipped = source_patch.restore_browser_store_source_patch(manifest)

    assert skipped["restored"] is False
    assert skipped["reason"] == "current_hash_mismatch"

    shutil.copy2(manifest["browser_store_source_patch"]["backup_path"], browser_store)
    source_patch.patch_browser_store_source(manifest)
    restored = source_patch.restore_browser_store_source_patch(manifest)

    assert restored["restored"] is True
    assert browser_store.read_text(encoding="utf-8") == original


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
    assert 'candidate_url == "about:blank"' in text
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


def _ws_browser_source() -> str:
    return f"""
from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any, ClassVar

from helpers.ws import WsHandler


{source_patch.WS_CLASS_ORIGINAL}
    async def _input(self, data: dict[str, Any], sid: str) -> dict[str, Any]:
        context_id = self._context_id(data)
        runtime = await get_runtime(context_id, create=False)

{source_patch.WS_INPUT_ORIGINAL}            if input_type == "keyboard":
                result = await runtime.call(
                    "keyboard",
                    browser_id,
                    key=str(data.get("key") or ""),
                    text=str(data.get("text") or ""),
                )
            else:
                result = {{}}
        except Exception as exc:
            return self._error("INPUT_FAILED", str(exc), data)

        return {{"state": result, "snapshot": None}}
"""


def _browser_store_source() -> str:
    return f"""
const model = {{
{source_patch.BROWSER_STORE_HANDLE_KEYDOWN_ORIGINAL}    void this.sendKey(event);
  }},

  async sendKey(event) {{
    const contextId = this.contextId;
    const printable = event.key && event.key.length === 1;
{source_patch.BROWSER_STORE_SEND_KEY_ORIGINAL}      key: printable ? "" : event.key,
      text: printable ? event.key : "",
    }});
  }},
}};
"""
