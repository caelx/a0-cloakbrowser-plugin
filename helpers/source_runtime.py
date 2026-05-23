from __future__ import annotations

from typing import Any

from .config import get_config
from .playwright_shim import (
    _IN_CLOAK_LAUNCH,
    _cloak_launch_persistent_async,
    build_launch_overrides,
    _plugin_enabled,
)


async def launch_persistent_context(browser_type: Any, launch_kwargs: dict[str, Any]) -> Any:
    patched_kwargs, info = build_launch_overrides(dict(launch_kwargs), persistent=True)
    if not info.get("patched"):
        if _plugin_enabled():
            raise RuntimeError(
                "CloakBrowser is enabled, but the launch hook is unavailable. "
                "Run: python execute.py repair --noninteractive"
            )
        user_data_dir = patched_kwargs.pop("user_data_dir")
        token = _IN_CLOAK_LAUNCH.set(True)
        try:
            return await browser_type.launch_persistent_context(user_data_dir, **patched_kwargs)
        finally:
            _IN_CLOAK_LAUNCH.reset(token)

    user_data_dir = patched_kwargs.pop("user_data_dir")
    return await _cloak_launch_persistent_async(user_data_dir, patched_kwargs)


def disable_shadow_dom_init() -> bool:
    return bool(get_config()["advanced"]["disable_shadow_dom_init_patch"])
