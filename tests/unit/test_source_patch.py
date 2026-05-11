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
    assert result["patch_version"] == "7"
    assert result["upgraded"] is False
    assert result["original_hash"] != result["patched_hash"]
    patched_text = runtime.read_text(encoding="utf-8")
    assert source_patch.PATCH_MARKER in patched_text
    assert "preserve_headed_placeholder" not in patched_text
    assert "close_all_preserving_placeholder" not in patched_text
    assert 'if page.url == "about:blank" and len(self.context.pages) == 1:' in patched_text
    assert 'if candidate.url == "about:blank":' not in patched_text
    assert "if page.url == \"about:blank\":" in patched_text
    assert "Browser context could not open a new tab; restarting." in patched_text
    assert "_cloakbrowser_open_restart_lock" in patched_text
    assert 'Path as _cloakbrowser_path' in patched_text
    assert '"/a0/usr/plugins/cloakbrowser"' in patched_text
    assert "gc.collect()" in patched_text
    assert "await asyncio.sleep(0.25)" in patched_text
    assert "playwright = self.playwright" in patched_text
    assert manifest["runtime_source_patch"]["target_path"] == str(runtime)
    assert manifest["runtime_patches"][0]["kind"] == "source_runtime"

    second = source_patch.patch_runtime_source(manifest, cfg)
    assert second["already_patched"] is True
    assert second["backup_path"] == result["backup_path"]
    assert second["original_hash"] == result["original_hash"]


def test_patch_runtime_source_upgrades_v1_source_patch(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(_runtime_source_patch_v1(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}
    cfg = {"advanced": {"patch_runtime_file_if_needed": True}}

    result = source_patch.patch_runtime_source(manifest, cfg)

    patched_text = runtime.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert result["upgraded"] is True
    assert result["patch_version"] == "7"
    assert source_patch.PATCH_MARKER in patched_text
    assert "CLOAKBROWSER_SOURCE_PATCH_V1" not in patched_text
    assert 'if page.url == "about:blank" and len(self.context.pages) == 1:' in patched_text
    assert 'if candidate.url == "about:blank":' not in patched_text
    assert "_cloakbrowser_open_restart_lock" in patched_text


def test_patch_runtime_source_upgrades_v2_source_patch(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(_runtime_source_patch_v2(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}
    cfg = {"advanced": {"patch_runtime_file_if_needed": True}}

    result = source_patch.patch_runtime_source(manifest, cfg)

    patched_text = runtime.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert result["upgraded"] is True
    assert result["patch_version"] == "7"
    assert source_patch.PATCH_MARKER in patched_text
    assert "CLOAKBROWSER_SOURCE_PATCH_V2" not in patched_text
    assert 'if page.url == "about:blank" and len(self.context.pages) == 1:' in patched_text
    assert "_cloakbrowser_open_restart_lock" in patched_text
    assert "_cloakbrowser_expected_context_close" in patched_text


def test_patch_runtime_source_upgrades_v3_source_patch(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(_runtime_source_patch_v3(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}
    cfg = {"advanced": {"patch_runtime_file_if_needed": True}}

    result = source_patch.patch_runtime_source(manifest, cfg)

    patched_text = runtime.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert result["upgraded"] is True
    assert result["patch_version"] == "7"
    assert source_patch.PATCH_MARKER in patched_text
    assert "CLOAKBROWSER_SOURCE_PATCH_V3" not in patched_text
    assert "_cloakbrowser_expected_context_close" in patched_text
    assert "Playwright stop after CloakBrowser context loss failed" in patched_text
    assert "gc.collect()" in patched_text
    assert "await asyncio.sleep(0.25)" in patched_text


def test_patch_runtime_source_upgrades_v4_source_patch(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.py"
    runtime.write_text(_runtime_source_patch_v4(), encoding="utf-8")
    monkeypatch.setattr(source_patch, "browser_runtime_source_path", lambda: runtime)
    manifest = {}
    cfg = {"advanced": {"patch_runtime_file_if_needed": True}}

    result = source_patch.patch_runtime_source(manifest, cfg)

    patched_text = runtime.read_text(encoding="utf-8")
    assert result["applied"] is True
    assert result["upgraded"] is True
    assert result["patch_version"] == "7"
    assert source_patch.PATCH_MARKER in patched_text
    assert "CLOAKBROWSER_SOURCE_PATCH_V4" not in patched_text
    assert "_cloakbrowser_expected_context_close" in patched_text
    assert "gc.collect()" in patched_text
    assert "await asyncio.sleep(0.25)" in patched_text


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


def test_patched_open_restarts_once_after_empty_context_new_page_failure():
    namespace = _patched_runtime_namespace()
    core = namespace["_BrowserRuntimeCore"]()
    calls = []

    class BrokenContext:
        async def new_page(self):
            calls.append("broken_new_page")
            raise RuntimeError("Target.createTarget: Failed to open a new tab")

    class LiveContext:
        async def new_page(self):
            calls.append("live_new_page")
            return "page"

    async def ensure_started():
        calls.append("ensure_started")

    async def discard_stale_context(message):
        calls.append(message)
        core.context = LiveContext()

    async def register_page(page):
        calls.append(("register", page))
        core.last_interacted_browser_id = 7
        return type("BrowserPage", (), {"id": 7})()

    core.context = BrokenContext()
    core.pages = {}
    core.ensure_started = ensure_started
    core._discard_stale_context = discard_stale_context
    core._register_page = register_page
    core._initial_url = lambda url="": url or "about:blank"
    core._settle = lambda page: _async_result(calls, ("settle", page))
    core._goto = lambda page, url: _async_result(calls, ("goto", page, url))
    core._state = lambda browser_id: _async_value({"id": browser_id})

    result = namespace["asyncio"].run(core.open("about:blank"))

    assert result == {"id": 7, "state": {"id": 7}}
    assert calls == [
        "ensure_started",
        "broken_new_page",
        "ensure_started",
        "broken_new_page",
        "Browser context could not open a new tab; restarting.",
        "ensure_started",
        "live_new_page",
        ("register", "page"),
        ("settle", "page"),
    ]


def test_patched_open_reuses_unregistered_startup_page_as_first_visible_page():
    namespace = _patched_runtime_namespace()
    core = namespace["_BrowserRuntimeCore"]()
    calls = []

    class StartupPage:
        def is_closed(self):
            return False

    class Context:
        pages = [StartupPage()]

        async def new_page(self):
            raise AssertionError("startup page should be used before opening another tab")

    async def register_page(page):
        calls.append(("register", page))
        core.last_interacted_browser_id = 9
        return type("BrowserPage", (), {"id": 9})()

    core.context = Context()
    core.pages = {}
    core.ensure_started = lambda: _async_value(None)
    core._register_page = register_page
    core._initial_url = lambda url="": url or "about:blank"
    core._settle = lambda page: _async_result(calls, ("settle", page))
    core._goto = lambda page, url: _async_result(calls, ("goto", page, url))
    core._state = lambda browser_id: _async_value({"id": browser_id})

    result = namespace["asyncio"].run(core.open("https://example.test/"))

    assert result == {"id": 9, "state": {"id": 9}}
    assert calls == [
        ("register", core.context.pages[0]),
        ("goto", core.context.pages[0], "https://example.test/"),
    ]


def test_patched_open_does_not_restart_when_visible_pages_exist():
    namespace = _patched_runtime_namespace()
    core = namespace["_BrowserRuntimeCore"]()

    class BrokenContext:
        async def new_page(self):
            raise RuntimeError("boom")

    async def discard_stale_context(message):
        raise AssertionError("visible pages should not be discarded")

    core.context = BrokenContext()
    core.pages = {1: object()}
    core.ensure_started = lambda: _async_value(None)
    core._discard_stale_context = discard_stale_context

    try:
        namespace["asyncio"].run(core.open("https://example.test/"))
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("open should surface new_page failure when pages are visible")


def test_patched_close_browser_suppresses_expected_async_context_close():
    namespace = _patched_runtime_namespace()
    core = namespace["_BrowserRuntimeCore"]()
    calls = []

    class Page:
        async def close(self):
            calls.append("page.close")
            namespace["asyncio"].get_running_loop().call_soon(core._on_context_closed)

    core.pages = {1: type("BrowserPage", (), {"page": Page()})()}
    core.context = object()
    core.playwright = object()
    core._closing = False
    core.last_interacted_browser_id = 1
    core.ensure_started = lambda: _async_value(None)
    core._resolve_browser_id = lambda browser_id: 1
    core._stop_screencasts_for_browser = lambda browser_id: _async_result(
        calls, ("stop_screencast", browser_id)
    )
    core._page = lambda browser_id: core.pages[browser_id].page
    core._discard_context_state = lambda: (calls.append("discard_context"), setattr(core, "context", None))
    core._stop_playwright = lambda warning: _async_result(calls, ("stop_playwright", warning))
    core.list = lambda: _async_result(calls, ("list", dict(core.pages)))

    namespace["asyncio"].run(core.close_browser())

    assert calls == [
        ("stop_screencast", 1),
        "page.close",
        "discard_context",
        (
            "stop_playwright",
            "Playwright stop after CloakBrowser context loss failed",
        ),
        ("list", {}),
    ]
    assert core.context is None


def _runtime_source():
    return """import asyncio
from pathlib import Path
from typing import Any

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

    async def close_browser(self, browser_id: int | str | None = None) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        await self._stop_screencasts_for_browser(resolved_id)
        page = self._page(resolved_id)
        await page.close()
        self.pages.pop(resolved_id, None)
        if self.last_interacted_browser_id == resolved_id:
            self.last_interacted_browser_id = next(iter(sorted(self.pages)), None)
        return await self.list()

    def _on_context_closed(self) -> None:
        if self._closing or self.context is None:
            return
        PrintStyle.warning("Browser context closed unexpectedly; will restart on next use.")
        self._discard_context_state()

    async def _stop_playwright(self, warning: str) -> None:
        if not self.playwright:
            return
        try:
            await self.playwright.stop()
        except Exception as exc:
            PrintStyle.warning(f"{warning}: {exc}")
        finally:
            self.playwright = None
"""


def _patched_runtime_namespace():
    namespace = {"__file__": "/tmp/plugins/_browser/helpers/runtime.py", "normalize_url": lambda value: value}
    exec(source_patch.patch_runtime_source_text(_runtime_source()), namespace)
    return namespace


def _runtime_source_patch_v1():
    anchor = 'CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"\n'
    helper = source_patch.SOURCE_RUNTIME_HELPER.replace(
        source_patch.PATCH_MARKER,
        source_patch.OLD_PATCH_MARKERS[0],
    )
    text = _runtime_source().replace(anchor, anchor + helper, 1)
    text = text.replace(source_patch.LAUNCH_ORIGINAL, source_patch.LAUNCH_PATCHED, 1)
    text = text.replace(source_patch.SHADOW_ORIGINAL, source_patch.SHADOW_PATCHED, 1)
    text = text.replace(source_patch.START_PAGES_ORIGINAL, source_patch.START_PAGES_PATCHED_V1, 1)
    text = text.replace(source_patch.OPEN_ORIGINAL, source_patch.OPEN_PATCHED_V1, 1)
    return text


def _runtime_source_patch_v2():
    anchor = 'CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"\n'
    helper = source_patch.SOURCE_RUNTIME_HELPER.replace(
        source_patch.PATCH_MARKER,
        "CLOAKBROWSER_SOURCE_PATCH_V2",
    )
    text = _runtime_source().replace(anchor, anchor + helper, 1)
    text = text.replace(source_patch.LAUNCH_ORIGINAL, source_patch.LAUNCH_PATCHED, 1)
    text = text.replace(source_patch.SHADOW_ORIGINAL, source_patch.SHADOW_PATCHED, 1)
    text = text.replace(source_patch.OPEN_ORIGINAL, source_patch.OPEN_PATCHED_V2, 1)
    return text


def _runtime_source_patch_v3():
    anchor = 'CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"\n'
    helper = source_patch.SOURCE_RUNTIME_HELPER.replace(
        source_patch.PATCH_MARKER,
        "CLOAKBROWSER_SOURCE_PATCH_V3",
    )
    text = _runtime_source().replace(anchor, anchor + helper, 1)
    text = text.replace(source_patch.LAUNCH_ORIGINAL, source_patch.LAUNCH_PATCHED, 1)
    text = text.replace(source_patch.SHADOW_ORIGINAL, source_patch.SHADOW_PATCHED, 1)
    text = text.replace(source_patch.START_PAGES_ORIGINAL, source_patch.START_PAGES_PATCHED, 1)
    text = text.replace(source_patch.OPEN_ORIGINAL, source_patch.OPEN_PATCHED, 1)
    return text


def _runtime_source_patch_v4():
    anchor = 'CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"\n'
    helper = source_patch.SOURCE_RUNTIME_HELPER.replace(
        source_patch.PATCH_MARKER,
        "CLOAKBROWSER_SOURCE_PATCH_V4",
    )
    text = _runtime_source().replace(anchor, anchor + helper, 1)
    text = text.replace(source_patch.LAUNCH_ORIGINAL, source_patch.LAUNCH_PATCHED, 1)
    text = text.replace(source_patch.SHADOW_ORIGINAL, source_patch.SHADOW_PATCHED, 1)
    text = text.replace(source_patch.START_PAGES_ORIGINAL, source_patch.START_PAGES_PATCHED, 1)
    text = text.replace(source_patch.OPEN_ORIGINAL, source_patch.OPEN_PATCHED, 1)
    text = text.replace(source_patch.CLOSE_BROWSER_ORIGINAL, source_patch.CLOSE_BROWSER_PATCHED, 1)
    text = text.replace(source_patch.CLOSE_ALL_ORIGINAL, source_patch.CLOSE_ALL_PATCHED, 1)
    text = text.replace(source_patch.CONTEXT_CLOSED_ORIGINAL, source_patch.CONTEXT_CLOSED_PATCHED, 1)
    return text


async def _async_value(value):
    return value


async def _async_result(calls, value):
    calls.append(value)
