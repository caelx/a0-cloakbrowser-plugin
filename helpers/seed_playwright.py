from __future__ import annotations

import os
from pathlib import Path

from .config import shim_root


def ensure_masquerade(binary_path: str | None = None) -> Path:
    if not binary_path:
        from cloakbrowser import ensure_binary

        binary_path = ensure_binary()
    target = shim_root() / "chromium-cloakbrowser"
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
    target = Path(path) if path else shim_root() / "chromium-cloakbrowser"
    if not (target.exists() or target.is_symlink()):
        return False
    target.unlink()
    return True
