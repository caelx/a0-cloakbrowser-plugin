from __future__ import annotations

import os
from pathlib import Path

from .config import plugin_dir, shim_root


def masquerade_path() -> Path:
    return playwright_cache_dir() / "chromium-cloakbrowser" / "chrome-linux" / "chrome"


def playwright_cache_dir() -> Path:
    try:
        from .runtime_patch import _agent_zero_import_context

        with _agent_zero_import_context():
            from plugins._browser.helpers.playwright import get_playwright_cache_dir

            return Path(get_playwright_cache_dir())
    except Exception:
        root = plugin_dir().resolve()
        for parent in root.parents:
            if (parent / "usr" / "plugins" / "_browser").is_dir():
                return parent / "usr" / "plugins" / "_browser" / "playwright"
        return shim_root()


def ensure_masquerade(binary_path: str | None = None) -> Path:
    if not binary_path:
        from cloakbrowser import ensure_binary

        binary_path = ensure_binary()
    target = masquerade_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        try:
            if target.resolve() == Path(binary_path).resolve():
                return target
        except OSError:
            pass
        target.unlink()
    try:
        target.symlink_to(binary_path)
    except OSError:
        target.write_text(f"#!/bin/sh\nexec {binary_path!r} \"$@\"\n", encoding="utf-8")
        target.chmod(0o755)
    return target


def remove_masquerade(path: str | None = None) -> bool:
    target = Path(path) if path else masquerade_path()
    if not (target.exists() or target.is_symlink()):
        return False
    target.unlink()
    for parent in (target.parent, target.parent.parent):
        try:
            parent.rmdir()
        except OSError:
            break
    return True
