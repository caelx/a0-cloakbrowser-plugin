from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .patcher import backup_file, sha256_file

PATCH_VERSION = "16"
PATCH_MARKER = "CLOAKBROWSER_SOURCE_PATCH_V16"
OLD_PATCH_MARKERS = (
    "CLOAKBROWSER_SOURCE_PATCH_V15",
    "CLOAKBROWSER_SOURCE_PATCH_V14",
    "CLOAKBROWSER_SOURCE_PATCH_V13",
    "CLOAKBROWSER_SOURCE_PATCH_V12",
    "CLOAKBROWSER_SOURCE_PATCH_V11",
    "CLOAKBROWSER_SOURCE_PATCH_V10",
    "CLOAKBROWSER_SOURCE_PATCH_V9",
    "CLOAKBROWSER_SOURCE_PATCH_V8",
    "CLOAKBROWSER_SOURCE_PATCH_V7",
    "CLOAKBROWSER_SOURCE_PATCH_V6",
    "CLOAKBROWSER_SOURCE_PATCH_V5",
    "CLOAKBROWSER_SOURCE_PATCH_V4",
    "CLOAKBROWSER_SOURCE_PATCH_V3",
    "CLOAKBROWSER_SOURCE_PATCH_V2",
    "CLOAKBROWSER_SOURCE_PATCH_V1",
)
WS_PATCH_VERSION = "1"
WS_PATCH_MARKER = "CLOAKBROWSER_WS_SOURCE_PATCH_V1"

WS_CLASS_ORIGINAL = """class WsBrowser(WsHandler):
    _streams: ClassVar[dict[tuple[str, str], asyncio.Task[None]]] = {}
"""

WS_CLASS_PATCHED = f"""class WsBrowser(WsHandler):
    # {WS_PATCH_MARKER}: start
    _streams: ClassVar[dict[tuple[str, str], asyncio.Task[None]]] = {{}}
    _last_keyboard_inputs: ClassVar[dict[tuple[str, str, str, str], dict[str, Any]]] = {{}}
    # {WS_PATCH_MARKER}: end
"""

WS_INPUT_ORIGINAL = """        input_type = str(data.get("input_type") or "").strip().lower()
        browser_id = data.get("browser_id")
        try:
"""

WS_INPUT_PATCHED = """        input_type = str(data.get("input_type") or "").strip().lower()
        browser_id = data.get("browser_id")
        if input_type == "keyboard":
            keyboard_signature = (
                context_id,
                str(browser_id),
                str(data.get("key") or ""),
                str(data.get("text") or ""),
            )
            keyboard_now = time.monotonic()
            previous_keyboard = self._last_keyboard_inputs.get(keyboard_signature)
            self._last_keyboard_inputs[keyboard_signature] = {"t": keyboard_now, "sid": sid}
            if previous_keyboard and keyboard_now - float(previous_keyboard.get("t") or 0) < 0.025:
                return {"state": None, "snapshot": None}
        try:
"""

SOURCE_RUNTIME_HELPER = f"""

# {PATCH_MARKER}: start
def _cloakbrowser_source_runtime():
    try:
        import importlib.util as _cloakbrowser_importlib_util
        from helpers import plugins as _cloakbrowser_plugins

        _cloakbrowser_dir = _cloakbrowser_plugins.find_plugin_dir("cloakbrowser")
        if not _cloakbrowser_dir:
            raise RuntimeError(
                "CloakBrowser is enabled, but the plugin directory was not found. "
                "Run: python execute.py repair --noninteractive"
            )
        _cloakbrowser_import_path = _cloakbrowser_dir + "/plugin_imports.py"
        _cloakbrowser_spec = _cloakbrowser_importlib_util.spec_from_file_location(
            "_cloakbrowser_plugin_imports",
            _cloakbrowser_import_path,
        )
        if not _cloakbrowser_spec or not _cloakbrowser_spec.loader:
            raise RuntimeError("CloakBrowser plugin_imports.py could not be loaded")
        _cloakbrowser_imports = _cloakbrowser_importlib_util.module_from_spec(_cloakbrowser_spec)
        _cloakbrowser_spec.loader.exec_module(_cloakbrowser_imports)
        _cloakbrowser_plugin_import = _cloakbrowser_imports.plugin_import

        return _cloakbrowser_plugin_import("helpers.source_runtime")
    except Exception as exc:
        raise RuntimeError(
            "CloakBrowser is enabled, but the launch hook is unavailable. "
            "Run: python execute.py repair --noninteractive"
        ) from exc
# {PATCH_MARKER}: end
"""

LAUNCH_ORIGINAL = """        try:
            self.context = await self.playwright.chromium.launch_persistent_context(
                **launch_kwargs
            )
"""

LAUNCH_PATCHED = """        _cloakbrowser_runtime = _cloakbrowser_source_runtime()
        try:
            if _cloakbrowser_runtime:
                self.context = await _cloakbrowser_runtime.launch_persistent_context(
                    self.playwright.chromium,
                    launch_kwargs,
                )
            else:
                self.context = await self.playwright.chromium.launch_persistent_context(
                    **launch_kwargs
                )
"""

SHADOW_ORIGINAL = """        await self.context.add_init_script(self._shadow_dom_script())
"""

SHADOW_PATCHED = """        if not (_cloakbrowser_runtime and _cloakbrowser_runtime.disable_shadow_dom_init()):
            await self.context.add_init_script(self._shadow_dom_script())
"""

CONTENT_HELPER_ORIGINAL = """        await self.context.add_init_script(path=str(CONTENT_HELPER_PATH))
"""

CONTENT_HELPER_PATCHED = """        if not (_cloakbrowser_runtime and _cloakbrowser_runtime.disable_shadow_dom_init()):
            await self.context.add_init_script(path=str(CONTENT_HELPER_PATH))
"""

START_PAGES_ORIGINAL = """        for page in list(self.context.pages):
            if page.url == "about:blank":
                try:
                    await page.close()
                except Exception:
                    pass
                continue
            await self._register_page(page)
"""

START_PAGES_PATCHED = """        for page in list(self.context.pages):
            if page.url == "about:blank" and len(self.context.pages) == 1:
                continue
            if page.url == "about:blank":
                try:
                    await page.close()
                except Exception:
                    pass
                continue
            await self._register_page(page)
"""

OPEN_ORIGINAL = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

OPEN_ORIGINAL_WITH_LIMIT = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        self._ensure_can_open_page()
        page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

OPEN_PATCHED = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        page = None
        if not self.pages:
            for candidate in list(getattr(self.context, "pages", [])):
                candidate_url = str(getattr(candidate, "url", "") or "")
                if candidate_url == "about:blank" and not getattr(candidate, "is_closed", lambda: False)():
                    page = candidate
                    break
        if page is None:
            try:
                page = await self.context.new_page()
            except Exception:
                if self.pages:
                    raise
                lock = getattr(self, "_cloakbrowser_open_restart_lock", None)
                if lock is None:
                    lock = asyncio.Lock()
                    self._cloakbrowser_open_restart_lock = lock
                async with lock:
                    await self.ensure_started()
                    if not self.pages:
                        for candidate in list(getattr(self.context, "pages", [])):
                            candidate_url = str(getattr(candidate, "url", "") or "")
                            if candidate_url == "about:blank" and not getattr(candidate, "is_closed", lambda: False)():
                                page = candidate
                                break
                    if page is None:
                        try:
                            page = await self.context.new_page()
                        except Exception:
                            if self.pages:
                                raise
                            await self._discard_stale_context("Browser context could not open a new tab; restarting.")
                            await self.ensure_started()
                            for candidate in list(getattr(self.context, "pages", [])):
                                candidate_url = str(getattr(candidate, "url", "") or "")
                                if candidate_url == "about:blank" and not getattr(candidate, "is_closed", lambda: False)():
                                    page = candidate
                                    break
                            if page is None:
                                page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

OPEN_PATCHED_WITH_LIMIT = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        self._ensure_can_open_page()
        page = None
        if not self.pages:
            for candidate in list(getattr(self.context, "pages", [])):
                candidate_url = str(getattr(candidate, "url", "") or "")
                if candidate_url == "about:blank" and not getattr(candidate, "is_closed", lambda: False)():
                    page = candidate
                    break
        if page is None:
            try:
                page = await self.context.new_page()
            except Exception:
                if self.pages:
                    raise
                lock = getattr(self, "_cloakbrowser_open_restart_lock", None)
                if lock is None:
                    lock = asyncio.Lock()
                    self._cloakbrowser_open_restart_lock = lock
                async with lock:
                    await self.ensure_started()
                    self._ensure_can_open_page()
                    if not self.pages:
                        for candidate in list(getattr(self.context, "pages", [])):
                            candidate_url = str(getattr(candidate, "url", "") or "")
                            if candidate_url == "about:blank" and not getattr(candidate, "is_closed", lambda: False)():
                                page = candidate
                                break
                    if page is None:
                        try:
                            page = await self.context.new_page()
                        except Exception:
                            if self.pages:
                                raise
                            await self._discard_stale_context("Browser context could not open a new tab; restarting.")
                            await self.ensure_started()
                            self._ensure_can_open_page()
                            for candidate in list(getattr(self.context, "pages", [])):
                                candidate_url = str(getattr(candidate, "url", "") or "")
                                if candidate_url == "about:blank" and not getattr(candidate, "is_closed", lambda: False)():
                                    page = candidate
                                    break
                            if page is None:
                                page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

START_PAGES_PATCHED_V1 = """        for page in list(self.context.pages):
            if page.url == "about:blank":
                if len(self.context.pages) == 1:
                    continue
                try:
                    await page.close()
                except Exception:
                    pass
                continue
            await self._register_page(page)
"""

OPEN_PATCHED_V1 = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        page = None
        if not self.pages:
            for candidate in list(self.context.pages):
                if candidate.url == "about:blank":
                    page = candidate
                    break
        if page is None:
            try:
                page = await self.context.new_page()
            except Exception:
                if self.pages:
                    raise
                await self._discard_stale_context("Browser context could not open a new tab; restarting.")
                await self.ensure_started()
                for candidate in list(self.context.pages):
                    if candidate.url == "about:blank":
                        page = candidate
                        break
                if page is None:
                    page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

OPEN_PATCHED_V2 = """    async def open(self, url: str = "") -> dict[str, Any]:
        await self.ensure_started()
        try:
            page = await self.context.new_page()
        except Exception:
            if self.pages:
                raise
            lock = getattr(self, "_cloakbrowser_open_restart_lock", None)
            if lock is None:
                lock = asyncio.Lock()
                self._cloakbrowser_open_restart_lock = lock
            async with lock:
                await self.ensure_started()
                try:
                    page = await self.context.new_page()
                except Exception:
                    if self.pages:
                        raise
                    await self._discard_stale_context("Browser context could not open a new tab; restarting.")
                    await self.ensure_started()
                    page = await self.context.new_page()
        browser_page = await self._register_page(page)
"""

CLOSE_BROWSER_ORIGINAL = """    async def close_browser(self, browser_id: int | str | None = None) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        await self._stop_screencasts_for_browser(resolved_id)
        page = self._page(resolved_id)
        await page.close()
        self.pages.pop(resolved_id, None)
        if self.last_interacted_browser_id == resolved_id:
            self.last_interacted_browser_id = next(iter(sorted(self.pages)), None)
        return await self.list()
"""

CLOSE_BROWSER_PATCHED = """    async def close_browser(self, browser_id: int | str | None = None) -> dict[str, Any]:
        await self.ensure_started()
        resolved_id = self._resolve_browser_id(browser_id)
        await self._stop_screencasts_for_browser(resolved_id)
        page = self._page(resolved_id)
        expecting_context_close = len(self.pages) <= 1
        context_closed_future = None
        if expecting_context_close:
            context_closed_future = asyncio.get_running_loop().create_future()
            self._cloakbrowser_expected_context_close = True
            self._cloakbrowser_expected_context_close_future = context_closed_future
        try:
            await page.close()
        finally:
            if expecting_context_close and context_closed_future:
                try:
                    await asyncio.wait_for(asyncio.shield(context_closed_future), timeout=1)
                except asyncio.TimeoutError:
                    pass
                finally:
                    self._cloakbrowser_expected_context_close = False
                    self._cloakbrowser_expected_context_close_future = None
        self.pages.pop(resolved_id, None)
        if self.last_interacted_browser_id == resolved_id:
            self.last_interacted_browser_id = next(iter(sorted(self.pages)), None)
        if self.context is None and self.playwright:
            await self._stop_playwright("Playwright stop after CloakBrowser context loss failed")
        return await self.list()
"""

CLOSE_ALL_ORIGINAL = """    async def close_all_browsers(self) -> dict[str, Any]:
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

CLOSE_ALL_PATCHED = """    async def close_all_browsers(self) -> dict[str, Any]:
        await self.ensure_started()
        await self._stop_all_screencasts()
        expecting_context_close = bool(self.pages)
        context_closed_future = None
        if expecting_context_close:
            context_closed_future = asyncio.get_running_loop().create_future()
            self._cloakbrowser_expected_context_close = True
            self._cloakbrowser_expected_context_close_future = context_closed_future
        try:
            for browser_id in list(self.pages):
                try:
                    await self.pages[browser_id].page.close()
                except Exception:
                    pass
        finally:
            if expecting_context_close and context_closed_future:
                try:
                    await asyncio.wait_for(asyncio.shield(context_closed_future), timeout=1)
                except asyncio.TimeoutError:
                    pass
                finally:
                    self._cloakbrowser_expected_context_close = False
                    self._cloakbrowser_expected_context_close_future = None
        self.pages.clear()
        self.last_interacted_browser_id = None
        if self.context is None and self.playwright:
            await self._stop_playwright("Playwright stop after CloakBrowser context loss failed")
        return {"browsers": [], "last_interacted_browser_id": None}
"""

CONTEXT_CLOSED_ORIGINAL = """    def _on_context_closed(self) -> None:
        if self._closing or self.context is None:
            return
        PrintStyle.warning("Browser context closed unexpectedly; will restart on next use.")
        self._discard_context_state()
"""

CONTEXT_CLOSED_PATCHED = """    def _on_context_closed(self) -> None:
        if self._closing or self.context is None:
            return
        if getattr(self, "_cloakbrowser_expected_context_close", False):
            future = getattr(self, "_cloakbrowser_expected_context_close_future", None)
            self._discard_context_state()
            if future and not future.done():
                future.set_result(None)
            return
        PrintStyle.warning("Browser context closed unexpectedly; will restart on next use.")
        self._discard_context_state()
"""

STOP_PLAYWRIGHT_ORIGINAL = """    async def _stop_playwright(self, warning: str) -> None:
        if not self.playwright:
            return
        try:
            await self.playwright.stop()
        except Exception as exc:
            PrintStyle.warning(f"{warning}: {exc}")
        finally:
            self.playwright = None
"""

STOP_PLAYWRIGHT_PATCHED = """    async def _stop_playwright(self, warning: str) -> None:
        if not self.playwright:
            return
        playwright = self.playwright
        self.playwright = None
        try:
            await playwright.stop()
        except Exception as exc:
            PrintStyle.warning(f"{warning}: {exc}")
        finally:
            import gc

            gc.collect()
            await asyncio.sleep(0.25)
"""


def patch_runtime_source(manifest: dict[str, Any]) -> dict[str, Any]:
    target = browser_runtime_source_path()
    original_text = target.read_text(encoding="utf-8")
    if PATCH_MARKER in original_text:
        previous = manifest.get("runtime_source_patch") or {}
        original_hash = previous.get("original_hash", "")
        backup_path = previous.get("backup_path", "")
        if backup_path and not original_hash and Path(str(backup_path)).is_file():
            original_hash = sha256_file(Path(str(backup_path)))
        if not backup_path or not Path(str(backup_path)).is_file():
            backup_path = str(_write_reconstructed_backup(target, original_text))
            original_hash = sha256_file(Path(backup_path))
        result = {
            "applied": True,
            "already_patched": True,
            "target_path": str(target),
            "backup_path": backup_path,
            "original_hash": original_hash,
            "patched_hash": sha256_file(target),
            "patch_version": PATCH_VERSION,
            "timestamp": _utc_now(),
        }
        manifest["runtime_source_patch"] = result
        _record_runtime_patch(manifest, result)
        return result

    is_old_patch = _has_old_or_partial_patch(original_text)
    original_hash = sha256_file(target)
    patched_text = (
        upgrade_runtime_source_text(original_text)
        if is_old_patch
        else patch_runtime_source_text(original_text)
    )
    backup = backup_file(target, target.parent / ".cloakbrowser-backups")
    target.write_text(patched_text, encoding="utf-8")
    patched_hash = sha256_file(target)
    result = {
        "applied": True,
        "already_patched": False,
        "target_path": str(target),
        "backup_path": str(backup),
        "original_hash": original_hash,
        "patched_hash": patched_hash,
        "patch_version": PATCH_VERSION,
        "timestamp": _utc_now(),
        "upgraded": is_old_patch,
    }
    manifest["runtime_source_patch"] = result
    _record_runtime_patch(manifest, result)
    return result


def patch_ws_browser_source(manifest: dict[str, Any]) -> dict[str, Any]:
    target = browser_ws_source_path()
    original_text = target.read_text(encoding="utf-8")
    if WS_PATCH_MARKER in original_text:
        previous = manifest.get("ws_browser_source_patch") or {}
        original_hash = previous.get("original_hash", "")
        backup_path = previous.get("backup_path", "")
        if backup_path and not original_hash and Path(str(backup_path)).is_file():
            original_hash = sha256_file(Path(str(backup_path)))
        result = {
            "applied": True,
            "already_patched": True,
            "target_path": str(target),
            "backup_path": backup_path,
            "original_hash": original_hash,
            "patched_hash": sha256_file(target),
            "patch_version": WS_PATCH_VERSION,
            "timestamp": _utc_now(),
        }
        manifest["ws_browser_source_patch"] = result
        _record_ws_patch(manifest, result)
        return result

    original_hash = sha256_file(target)
    patched_text = patch_ws_browser_source_text(original_text)
    backup = backup_file(target, target.parent / ".cloakbrowser-backups")
    target.write_text(patched_text, encoding="utf-8")
    patched_hash = sha256_file(target)
    result = {
        "applied": True,
        "already_patched": False,
        "target_path": str(target),
        "backup_path": str(backup),
        "original_hash": original_hash,
        "patched_hash": patched_hash,
        "patch_version": WS_PATCH_VERSION,
        "timestamp": _utc_now(),
    }
    manifest["ws_browser_source_patch"] = result
    _record_ws_patch(manifest, result)
    return result


def restore_runtime_source_patch(manifest: dict[str, Any]) -> dict[str, Any]:
    patch = manifest.get("runtime_source_patch") or {}
    target_path = patch.get("target_path")
    backup_path = patch.get("backup_path")
    patched_hash = patch.get("patched_hash")
    if not target_path or not backup_path or not patched_hash:
        return {"restored": False, "reason": "not_patched"}

    target = Path(str(target_path))
    backup = Path(str(backup_path))
    if not target.is_file() or not backup.is_file():
        return {"restored": False, "reason": "missing_file", "target_path": str(target)}
    current_hash = sha256_file(target)
    if current_hash != patched_hash:
        return {
            "restored": False,
            "reason": "current_hash_mismatch",
            "target_path": str(target),
            "current_hash": current_hash,
            "expected_hash": patched_hash,
        }
    shutil.copy2(backup, target)
    return {"restored": True, "target_path": str(target), "restored_hash": sha256_file(target)}


def restore_ws_browser_source_patch(manifest: dict[str, Any]) -> dict[str, Any]:
    patch = manifest.get("ws_browser_source_patch") or {}
    target_path = patch.get("target_path")
    backup_path = patch.get("backup_path")
    patched_hash = patch.get("patched_hash")
    if not target_path or not backup_path or not patched_hash:
        return {"restored": False, "reason": "not_patched"}

    target = Path(str(target_path))
    backup = Path(str(backup_path))
    if not target.is_file() or not backup.is_file():
        return {"restored": False, "reason": "missing_file", "target_path": str(target)}
    current_hash = sha256_file(target)
    if current_hash != patched_hash:
        return {
            "restored": False,
            "reason": "current_hash_mismatch",
            "target_path": str(target),
            "current_hash": current_hash,
            "expected_hash": patched_hash,
        }
    shutil.copy2(backup, target)
    return {"restored": True, "target_path": str(target), "restored_hash": sha256_file(target)}


def browser_runtime_source_path() -> Path:
    from .runtime_patch import _agent_zero_import_context

    with _agent_zero_import_context():
        from plugins._browser.helpers import runtime

        return Path(runtime.__file__).resolve()


def browser_ws_source_path() -> Path:
    from .runtime_patch import _agent_zero_import_context

    with _agent_zero_import_context():
        from plugins._browser.api import ws_browser

        return Path(ws_browser.__file__).resolve()


def patch_runtime_source_text(text: str) -> str:
    patched = _ensure_helper_block(text)
    patched = _replace_once(patched, LAUNCH_ORIGINAL, LAUNCH_PATCHED)
    patched = _replace_first_matching_pair_once(
        patched,
        (
            (SHADOW_ORIGINAL, SHADOW_PATCHED),
            (CONTENT_HELPER_ORIGINAL, CONTENT_HELPER_PATCHED),
        ),
    )
    patched = _replace_once(patched, START_PAGES_ORIGINAL, START_PAGES_PATCHED)
    patched = _replace_first_matching_pair_once(
        patched,
        (
            (OPEN_ORIGINAL_WITH_LIMIT, OPEN_PATCHED_WITH_LIMIT),
            (OPEN_ORIGINAL, OPEN_PATCHED),
        ),
    )
    patched = _replace_once(patched, CLOSE_BROWSER_ORIGINAL, CLOSE_BROWSER_PATCHED)
    patched = _replace_once(patched, CLOSE_ALL_ORIGINAL, CLOSE_ALL_PATCHED)
    patched = _replace_once(patched, CONTEXT_CLOSED_ORIGINAL, CONTEXT_CLOSED_PATCHED)
    patched = _replace_once(patched, STOP_PLAYWRIGHT_ORIGINAL, STOP_PLAYWRIGHT_PATCHED)
    return patched


def patch_ws_browser_source_text(text: str) -> str:
    patched = _replace_once(text, WS_CLASS_ORIGINAL, WS_CLASS_PATCHED)
    patched = _replace_once(patched, WS_INPUT_ORIGINAL, WS_INPUT_PATCHED)
    return patched


def unpatch_ws_browser_source_text(text: str) -> str:
    restored = _replace_once(text, WS_CLASS_PATCHED, WS_CLASS_ORIGINAL)
    restored = _replace_once(restored, WS_INPUT_PATCHED, WS_INPUT_ORIGINAL)
    return restored


def upgrade_runtime_source_text(text: str) -> str:
    patched = text
    for old_marker in OLD_PATCH_MARKERS:
        patched = patched.replace(f"{old_marker}:", f"{PATCH_MARKER}:")
    patched = _ensure_helper_block(patched)
    patched = _replace_helper_block(patched)
    patched = _replace_first_matching_once(
        patched,
        (LAUNCH_PATCHED, LAUNCH_ORIGINAL),
        LAUNCH_PATCHED,
    )
    patched = _replace_first_matching_pair_once(
        patched,
        (
            (SHADOW_PATCHED, SHADOW_PATCHED),
            (SHADOW_ORIGINAL, SHADOW_PATCHED),
            (CONTENT_HELPER_PATCHED, CONTENT_HELPER_PATCHED),
            (CONTENT_HELPER_ORIGINAL, CONTENT_HELPER_PATCHED),
        ),
    )
    if START_PAGES_PATCHED in patched:
        pass
    elif START_PAGES_PATCHED_V1 in patched:
        patched = _replace_once(patched, START_PAGES_PATCHED_V1, START_PAGES_PATCHED)
    else:
        patched = _replace_once(patched, START_PAGES_ORIGINAL, START_PAGES_PATCHED)
    patched = _replace_first_matching_pair_once(
        patched,
        (
            (OPEN_PATCHED_WITH_LIMIT, OPEN_PATCHED_WITH_LIMIT),
            (OPEN_ORIGINAL_WITH_LIMIT, OPEN_PATCHED_WITH_LIMIT),
            (OPEN_PATCHED, OPEN_PATCHED),
            (OPEN_PATCHED_V2, OPEN_PATCHED),
            (OPEN_PATCHED_V1, OPEN_PATCHED),
            (OPEN_ORIGINAL, OPEN_PATCHED),
        ),
    )
    patched = _replace_first_matching_once(
        patched,
        (CLOSE_BROWSER_PATCHED, CLOSE_BROWSER_ORIGINAL),
        CLOSE_BROWSER_PATCHED,
    )
    patched = _replace_first_matching_once(
        patched,
        (CLOSE_ALL_PATCHED, CLOSE_ALL_ORIGINAL),
        CLOSE_ALL_PATCHED,
    )
    patched = _replace_first_matching_once(
        patched,
        (CONTEXT_CLOSED_PATCHED, CONTEXT_CLOSED_ORIGINAL),
        CONTEXT_CLOSED_PATCHED,
    )
    patched = _replace_first_matching_once(
        patched,
        (STOP_PLAYWRIGHT_PATCHED, STOP_PLAYWRIGHT_ORIGINAL),
        STOP_PLAYWRIGHT_PATCHED,
    )
    if PATCH_MARKER not in patched:
        raise ValueError("Expected upgraded runtime source to contain current patch marker")
    return patched


def unpatch_runtime_source_text(text: str) -> str:
    restored = _remove_helper_block(text)
    restored = _replace_once(restored, LAUNCH_PATCHED, LAUNCH_ORIGINAL)
    restored = _replace_first_matching_pair_once(
        restored,
        (
            (SHADOW_PATCHED, SHADOW_ORIGINAL),
            (CONTENT_HELPER_PATCHED, CONTENT_HELPER_ORIGINAL),
        ),
    )
    restored = _replace_once(restored, START_PAGES_PATCHED, START_PAGES_ORIGINAL)
    restored = _replace_first_matching_pair_once(
        restored,
        (
            (OPEN_PATCHED_WITH_LIMIT, OPEN_ORIGINAL_WITH_LIMIT),
            (OPEN_PATCHED, OPEN_ORIGINAL),
        ),
    )
    restored = _replace_once(restored, CLOSE_BROWSER_PATCHED, CLOSE_BROWSER_ORIGINAL)
    restored = _replace_once(restored, CLOSE_ALL_PATCHED, CLOSE_ALL_ORIGINAL)
    restored = _replace_once(restored, CONTEXT_CLOSED_PATCHED, CONTEXT_CLOSED_ORIGINAL)
    restored = _replace_once(restored, STOP_PLAYWRIGHT_PATCHED, STOP_PLAYWRIGHT_ORIGINAL)
    return restored


def _has_old_or_partial_patch(text: str) -> bool:
    if any(marker in text for marker in OLD_PATCH_MARKERS):
        return True
    return any(
        snippet in text
        for snippet in (
            LAUNCH_PATCHED,
            SHADOW_PATCHED,
            CONTENT_HELPER_PATCHED,
            START_PAGES_PATCHED,
            START_PAGES_PATCHED_V1,
            OPEN_PATCHED,
            OPEN_PATCHED_WITH_LIMIT,
            OPEN_PATCHED_V1,
            OPEN_PATCHED_V2,
            CLOSE_BROWSER_PATCHED,
            CLOSE_ALL_PATCHED,
            CONTEXT_CLOSED_PATCHED,
            STOP_PLAYWRIGHT_PATCHED,
        )
    )


def _ensure_helper_block(text: str) -> str:
    if PATCH_MARKER in text:
        updated = _replace_helper_block(text)
        if updated != text:
            return updated
        raise ValueError("Expected one CloakBrowser source helper block, found 0")
    anchor = 'CONTENT_HELPER_PATH = PLUGIN_DIR / "assets" / "browser-page-content.js"\n'
    return _replace_once(text, anchor, anchor + SOURCE_RUNTIME_HELPER)


def _replace_helper_block(text: str) -> str:
    pattern = rf"\n# {PATCH_MARKER}: start\n.*?\n# {PATCH_MARKER}: end\n"
    updated, count = re.subn(pattern, SOURCE_RUNTIME_HELPER, text, count=1, flags=re.DOTALL)
    if count == 1:
        return updated
    return text


def _remove_helper_block(text: str) -> str:
    pattern = rf"\n# {PATCH_MARKER}: start\n.*?\n# {PATCH_MARKER}: end\n"
    updated, count = re.subn(pattern, "\n", text, count=1, flags=re.DOTALL)
    if count != 1:
        raise ValueError("Expected one CloakBrowser source helper block, found 0")
    return updated


def _write_reconstructed_backup(target: Path, patched_text: str) -> Path:
    backup_dir = target.parent / ".cloakbrowser-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{target.name}.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.reconstructed.bak"
    backup.write_text(unpatch_runtime_source_text(patched_text), encoding="utf-8")
    return backup


def _replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected one runtime source patch target, found {count}")
    return text.replace(old, new, 1)


def _replace_first_matching_once(text: str, candidates: tuple[str, ...], new: str) -> str:
    for old in candidates:
        if old in text:
            return _replace_once(text, old, new)
    raise ValueError("Expected one runtime source patch target, found 0")


def _replace_first_matching_pair_once(text: str, replacements: tuple[tuple[str, str], ...]) -> str:
    for old, new in replacements:
        if old in text:
            return _replace_once(text, old, new)
    raise ValueError("Expected one runtime source patch target, found 0")


def _record_runtime_patch(manifest: dict[str, Any], result: dict[str, Any]) -> None:
    patches = [
        patch
        for patch in manifest.get("runtime_patches", [])
        if patch.get("kind") != "source_runtime"
    ]
    patches.append({"kind": "source_runtime", **result})
    manifest["runtime_patches"] = patches


def _record_ws_patch(manifest: dict[str, Any], result: dict[str, Any]) -> None:
    patches = [
        patch
        for patch in manifest.get("runtime_patches", [])
        if patch.get("kind") != "source_ws_browser"
    ]
    patches.append({"kind": "source_ws_browser", **result})
    manifest["runtime_patches"] = patches


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
