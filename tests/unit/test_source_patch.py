import shutil

from helpers import source_patch


def test_patch_runtime_source_applies_and_records(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(_runtime_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}
    cfg = {"advanced": {"patch_runtime_file_if_needed": True}}

    result = source_patch.patch_runtime_source(manifest, cfg)

    assert result["applied"] is True
    assert result["already_patched"] is False
    assert result["original_hash"] != result["patched_hash"]
    patched_text = runtime.read_text(encoding="utf-8")
    assert source_patch.PATCH_MARKER in patched_text
    assert "preserve_headed_placeholder" not in patched_text
    assert "close_all_preserving_placeholder" not in patched_text
    assert "if len(self.context.pages) == 1:" in patched_text
    assert "for candidate in list(self.context.pages):" in patched_text
    assert "Browser context could not open a new tab; restarting." in patched_text
    assert manifest["runtime_source_patch"]["target_path"] == str(runtime)
    assert manifest["runtime_patches"][0]["kind"] == "source_runtime"

    second = source_patch.patch_runtime_source(manifest, cfg)
    assert second["already_patched"] is True
    assert second["backup_path"] == result["backup_path"]
    assert second["original_hash"] == result["original_hash"]


def test_restore_runtime_source_patch_requires_matching_hash(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(_runtime_source(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}
    cfg = {"advanced": {"patch_runtime_file_if_needed": True}}
    source_patch.patch_runtime_source(manifest, cfg)
    backup_text = (tmp_path / "runtime.py").read_text(encoding="utf-8")
    runtime.write_text(backup_text + "# user edit\n", encoding="utf-8")

    skipped = source_patch.restore_runtime_source_patch(manifest)

    assert skipped["restored"] is False
    assert skipped["reason"] == "current_hash_mismatch"

    shutil.copy2(manifest["runtime_source_patch"]["backup_path"], runtime)
    source_patch.patch_runtime_source(manifest, cfg)
    restored = source_patch.restore_runtime_source_patch(manifest)

    assert restored["restored"] is True
    assert source_patch.PATCH_MARKER not in runtime.read_text(encoding="utf-8")


def _runtime_source():
    return """from pathlib import Path
from typing import Any

from helpers.print_style import PrintStyle

PLUGIN_DIR = Path(__file__).resolve().parents[1]
CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"


class _BrowserRuntimeCore:
    async def _start(self) -> None:
        launch_kwargs = {}
        self.playwright = None
        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                **launch_kwargs
            )
        except Exception:
            raise
        await self.context.add_init_script(self._shadow_dom_script())
        await self.context.add_init_script(path=str(CONTENT_HELPER_PATH))

        for page in list(self.context.pages):
            if page.url == "about:blank":
                try:
                    await page.close()
                except Exception:
                    pass
                continue
            await self._register_page(page)

    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        page = await self.context.new_page()
        browser_page = await self._register_page(page)
        self.last_interacted_browser_id = browser_page.id
        target_url = self._initial_url(url)
        if target_url and target_url != "about:blank":
            await self._goto(page, normalize_url(target_url))
        else:
            await self._settle(page)
        return {"id": browser_page.id, "state": await self._state(browser_page.id)}

    async def close_all_browsers(self) -> dict[str, Any]:
        await self.ensure_started()
        await self._stop_all_screencasts()
        for browser_id in list(self.pages):
            try:
                await self.pages[browser_id].page.close()
            except Exception:
                pass
        self.pages.clear()
        self.last_interacted_browser_id = None
        return {"browsers": [], "last_interacted_browser_id": None}
"""
