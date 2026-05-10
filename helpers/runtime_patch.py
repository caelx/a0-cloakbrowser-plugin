from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_STATE: dict[str, Any] = {
    "patched": False,
    "shadow_dom_disabled": False,
    "original_shadow_dom_script": None,
    "original_start": None,
    "original_close_all_methods": {},
}


def _context_pages(context: Any) -> list[Any]:
    if context is None:
        return []
    pages = getattr(context, "pages", [])
    if callable(pages):
        pages = pages()
    return list(pages or [])


def _page_is_closed(page: Any) -> bool:
    is_closed = getattr(page, "is_closed", None)
    if callable(is_closed):
        try:
            return bool(is_closed())
        except Exception:
            return False
    return False


def _page_is_about_blank(page: Any) -> bool:
    return not _page_is_closed(page) and getattr(page, "url", "") == "about:blank"


async def _ensure_registered_about_blank(core: Any) -> Any:
    for page_record in list(getattr(core, "pages", {}).values()):
        page = getattr(page_record, "page", None)
        if _page_is_about_blank(page):
            return page_record

    for page in _context_pages(getattr(core, "context", None)):
        if _page_is_about_blank(page):
            return await core._register_page(page)

    page = await core.context.new_page()
    if getattr(page, "url", "") != "about:blank":
        await page.goto("about:blank")
    return await core._register_page(page)


async def _close_all_preserving_placeholder(core: Any) -> dict[str, Any]:
    await core.ensure_started()

    stop_screencasts = getattr(core, "_stop_all_screencasts", None)
    if callable(stop_screencasts):
        await stop_screencasts()

    placeholder_record = await _ensure_registered_about_blank(core)
    placeholder_page = placeholder_record.page
    registered_pages = {record.page for record in list(core.pages.values())}

    for browser_id, page_record in list(core.pages.items()):
        page = page_record.page
        if page is placeholder_page:
            continue
        try:
            await page.close()
        except Exception:
            pass
        core.pages.pop(browser_id, None)

    for page in _context_pages(core.context):
        if page is placeholder_page or page in registered_pages:
            continue
        try:
            await page.close()
        except Exception:
            pass

    core.pages.clear()
    core.pages[placeholder_record.id] = placeholder_record
    core.last_interacted_browser_id = placeholder_record.id
    return await core.list()


def apply_runtime_patch() -> dict[str, Any]:
    if _STATE["patched"]:
        return status()
    try:
        with _agent_zero_import_context():
            from plugins._browser.helpers import runtime
    except Exception as exc:
        _STATE["error"] = str(exc)
        return status()

    from .config import get_config

    cfg = get_config()
    core = runtime._BrowserRuntimeCore
    if cfg["advanced"]["disable_shadow_dom_init_patch"]:
        _STATE["original_shadow_dom_script"] = core._shadow_dom_script
        core._shadow_dom_script = staticmethod(_empty_shadow_dom_script)
        _STATE["shadow_dom_disabled"] = True
    else:
        _STATE["original_shadow_dom_script"] = None
        _STATE["shadow_dom_disabled"] = False
    _STATE["original_start"] = core._start

    async def _patched_start(self):
        cfg = get_config()
        restore_page_close = None
        if cfg["advanced"]["preserve_headed_placeholder_page"] and cfg["runtime"]["headed"]:
            try:
                from playwright.async_api import Page

                original_page_close = Page.close

                async def _close_preserving_sole_placeholder(page, *args, **kwargs):
                    try:
                        context_pages = list(getattr(page.context, "pages", []) or [])
                        if page.url == "about:blank" and len(context_pages) == 1:
                            return None
                    except Exception:
                        pass
                    return await original_page_close(page, *args, **kwargs)

                Page.close = _close_preserving_sole_placeholder

                def restore_page_close():
                    setattr(Page, "close", original_page_close)
            except Exception:
                restore_page_close = None
        try:
            await _STATE["original_start"](self)
        finally:
            if restore_page_close:
                restore_page_close()
        if not cfg["advanced"]["preserve_headed_placeholder_page"]:
            return
        if not cfg["runtime"]["headed"]:
            return
        try:
            if self.pages:
                return
            context_pages = list(getattr(self.context, "pages", []) or [])
            if len(context_pages) == 1 and context_pages[0].url == "about:blank":
                await self._register_page(context_pages[0])
        except Exception:
            return

    core._start = _patched_start

    original_close_all_methods = _STATE["original_close_all_methods"]
    for method_name in ("close_all", "close_all_browsers"):
        if not hasattr(core, method_name) or method_name in original_close_all_methods:
            continue
        original_close_all_methods[method_name] = getattr(core, method_name)

        async def _patched_close_all(self, _method_name=method_name):
            cfg = get_config()
            if not cfg["runtime"]["headed"]:
                return await _STATE["original_close_all_methods"][_method_name](self)
            if not cfg["advanced"]["preserve_headed_placeholder_page"]:
                return await _STATE["original_close_all_methods"][_method_name](self)
            return await _close_all_preserving_placeholder(self)

        setattr(core, method_name, _patched_close_all)

    _STATE["patched"] = True
    return status()


def unpatch_runtime() -> dict[str, Any]:
    if not _STATE["patched"]:
        return status()
    try:
        with _agent_zero_import_context():
            from plugins._browser.helpers import runtime

        core = runtime._BrowserRuntimeCore
        if _STATE["original_shadow_dom_script"] is not None:
            core._shadow_dom_script = _STATE["original_shadow_dom_script"]
        if _STATE["original_start"] is not None:
            core._start = _STATE["original_start"]
        for method_name, original in dict(_STATE["original_close_all_methods"]).items():
            setattr(core, method_name, original)
    except Exception as exc:
        _STATE["error"] = str(exc)
    _STATE["patched"] = False
    _STATE["shadow_dom_disabled"] = False
    _STATE["original_start"] = None
    _STATE["original_close_all_methods"] = {}
    return status()


def status() -> dict[str, Any]:
    return {
        "patched": bool(_STATE.get("patched")),
        "patching": "process-local",
        "persistent": False,
        "shadow_dom_disabled": bool(_STATE.get("shadow_dom_disabled")),
        "close_all_patched": bool(_STATE.get("original_close_all_methods")),
        "error": _STATE.get("error", ""),
    }


def _empty_shadow_dom_script() -> str:
    return "(() => {})();"


@contextmanager
def _agent_zero_import_context():
    from .config import plugin_dir

    root = plugin_dir().resolve()
    removed_entries: list[tuple[int, str]] = []
    removed_modules: dict[str, Any] = {}
    for name, module in list(sys.modules.items()):
        if name != "helpers" and not name.startswith("helpers."):
            continue
        module_file = Path(getattr(module, "__file__", "") or "")
        if not module_file:
            continue
        try:
            if not module_file.resolve().is_relative_to(root):
                continue
        except Exception:
            continue
        removed_modules[name] = module
        sys.modules.pop(name, None)

    for index, entry in reversed(list(enumerate(sys.path))):
        try:
            matches_root = Path(entry or ".").resolve() == root
        except Exception:
            matches_root = False
        if entry == str(root) or matches_root:
            removed_entries.append((index, entry))
            sys.path.pop(index)

    for parent in root.parents:
        if (parent / "plugins" / "_browser").is_dir() and (parent / "helpers" / "tool.py").is_file():
            parent_str = str(parent)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)
            break

    try:
        yield
    finally:
        for index, entry in sorted(removed_entries):
            sys.path.insert(min(index, len(sys.path)), entry)
        for name, module in removed_modules.items():
            sys.modules.setdefault(name, module)
