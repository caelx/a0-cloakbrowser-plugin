from __future__ import annotations

import inspect
import random
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from .config import apply_environment, get_config
from .extensions import active_extension_paths
from .seed_playwright import ensure_masquerade

DROP_EXACT = {"--disable-dev-shm-usage", "--disable-gpu", "--disable-extensions"}
DROP_PREFIXES = ("--disable-dev-shm-usage=", "--disable-gpu=", "--disable-extensions=")

_STATE: dict[str, Any] = {
    "patched": False,
    "async_originals": {},
    "sync_originals": {},
    "last_launch": {},
}
_IN_CLOAK_LAUNCH: ContextVar[bool] = ContextVar("cloakbrowser_in_cloak_launch", default=False)


def patch_playwright() -> dict[str, Any]:
    if _STATE["patched"]:
        return status()
    patched_targets: list[str] = []
    try:
        from playwright.async_api import BrowserType as AsyncBrowserType

        _patch_class(AsyncBrowserType, async_mode=True)
        patched_targets.append("playwright.async_api.BrowserType")
    except Exception as exc:
        _STATE["async_error"] = str(exc)
    try:
        from playwright.sync_api import BrowserType as SyncBrowserType

        _patch_class(SyncBrowserType, async_mode=False)
        patched_targets.append("playwright.sync_api.BrowserType")
    except Exception as exc:
        _STATE["sync_error"] = str(exc)
    _STATE["patched"] = bool(patched_targets)
    _STATE["patched_targets"] = patched_targets
    return status()


def unpatch_playwright() -> dict[str, Any]:
    for cls, methods in list(_STATE.get("async_originals", {}).items()):
        for name, original in methods.items():
            setattr(cls, name, original)
    for cls, methods in list(_STATE.get("sync_originals", {}).items()):
        for name, original in methods.items():
            setattr(cls, name, original)
    _STATE["async_originals"] = {}
    _STATE["sync_originals"] = {}
    _STATE["patched"] = False
    return status()


def status() -> dict[str, Any]:
    return {
        "patched": bool(_STATE.get("patched")),
        "patching": "process-local",
        "persistent": False,
        "patched_targets": list(_STATE.get("patched_targets", [])),
        "last_launch": dict(_STATE.get("last_launch", {})),
        "async_error": _STATE.get("async_error", ""),
        "sync_error": _STATE.get("sync_error", ""),
        "arg_filtering": "always_on",
    }


def filter_args(args: list[str] | tuple[str, ...] | None) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    dropped: list[str] = []
    for arg in list(args or []):
        text = str(arg)
        if text in DROP_EXACT or text.startswith(DROP_PREFIXES):
            dropped.append(text)
        else:
            kept.append(text)
    return kept, dropped


def build_launch_overrides(kwargs: dict[str, Any], *, persistent: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = get_config()
    apply_environment(cfg)
    if not should_patch_launch(kwargs):
        return dict(kwargs), {"patched": False, "reason": "launch outside CloakBrowser criteria"}

    from cloakbrowser import ensure_binary
    from cloakbrowser.browser import build_args, maybe_resolve_geoip
    from cloakbrowser.config import IGNORE_DEFAULT_ARGS

    binary = ensure_binary()
    ensure_masquerade(binary)
    original_args = list(kwargs.get("args") or [])
    filtered_args, dropped_args = filter_args(original_args)
    filtered_args.extend(_identity_args(cfg))
    filtered_args.extend(_extension_args(cfg))
    filtered_args.extend(cfg["advanced"]["extra_args"])

    proxy = cfg["network_location"]["proxy"] or None
    timezone = cfg["network_location"]["timezone"] or None
    locale = cfg["network_location"]["locale"] or None
    geoip = bool(cfg["network_location"]["geoip"])
    timezone, locale, exit_ip = maybe_resolve_geoip(geoip, proxy, timezone, locale)
    if cfg["network_location"]["webrtc_ip_mode"] == "auto" and exit_ip:
        filtered_args.append(f"--fingerprint-webrtc-ip={exit_ip}")
    elif cfg["network_location"]["webrtc_ip_mode"] == "explicit" and cfg["network_location"]["webrtc_ip"]:
        filtered_args.append(f"--fingerprint-webrtc-ip={cfg['network_location']['webrtc_ip']}")

    headless = not bool(cfg["runtime"]["headed"])
    final_args = build_args(
        True,
        filtered_args,
        timezone=timezone,
        locale=locale,
        headless=headless,
    )
    launch_kwargs = dict(kwargs)
    launch_kwargs.pop("channel", None)
    launch_kwargs["executable_path"] = binary
    launch_kwargs["headless"] = headless
    launch_kwargs["args"] = final_args
    launch_kwargs["ignore_default_args"] = _merge_ignore_default_args(
        kwargs.get("ignore_default_args"),
        IGNORE_DEFAULT_ARGS + list(DROP_EXACT),
    )
    launch_kwargs["viewport"] = {
        "width": cfg["runtime"]["viewport_width"],
        "height": cfg["runtime"]["viewport_height"],
    }
    launch_kwargs["screen"] = {
        "width": cfg["runtime"]["display_width"],
        "height": cfg["runtime"]["display_height"],
    }
    if cfg["humanization"]["humanize"]:
        launch_kwargs["humanize"] = True
        launch_kwargs["human_preset"] = cfg["humanization"]["human_preset"]
    if proxy:
        launch_kwargs["proxy"] = proxy

    info = {
        "patched": True,
        "persistent": persistent,
        "binary": binary,
        "headless": headless,
        "dropped_args": dropped_args,
        "final_args": redact_args(final_args),
        "viewport": launch_kwargs["viewport"],
        "screen": launch_kwargs["screen"],
    }
    _STATE["last_launch"] = info
    return launch_kwargs, info


def should_patch_launch(kwargs: dict[str, Any]) -> bool:
    cfg = get_config()
    if not cfg["runtime"]["enabled"]:
        return False
    if _IN_CLOAK_LAUNCH.get():
        return False
    executable = str(kwargs.get("executable_path") or "").strip()
    if not executable:
        return True
    lowered = executable.lower()
    normalized = lowered.replace("\\", "/")
    return (
        "cloakbrowser" in normalized
        or "chromium-cloakbrowser" in normalized
        or "/plugins/_browser/playwright/" in normalized
        or "/usr/plugins/_browser/playwright/" in normalized
    )


def redact_args(args: list[str]) -> list[str]:
    redacted: list[str] = []
    for arg in args:
        if arg.startswith("--proxy-server=") and "@" in arg:
            prefix, host = arg.rsplit("@", 1)
            redacted.append(prefix.split("=", 1)[0] + "=<redacted>@" + host)
        else:
            redacted.append(arg)
    return redacted


def _patch_class(cls: type, *, async_mode: bool) -> None:
    originals_key = "async_originals" if async_mode else "sync_originals"
    originals = _STATE[originals_key].setdefault(cls, {})
    if "launch" not in originals:
        originals["launch"] = cls.launch
        if async_mode:
            async def launch(self, **kwargs):
                patched_kwargs, _info = build_launch_overrides(kwargs, persistent=False)
                if "humanize" in patched_kwargs or "human_preset" in patched_kwargs:
                    return await _cloak_launch_async(patched_kwargs)
                return await originals["launch"](self, **patched_kwargs)
        else:
            def launch(self, **kwargs):
                patched_kwargs, _info = build_launch_overrides(kwargs, persistent=False)
                if "humanize" in patched_kwargs or "human_preset" in patched_kwargs:
                    return _cloak_launch_sync(patched_kwargs)
                return originals["launch"](self, **patched_kwargs)
        setattr(cls, "launch", launch)
    if "launch_persistent_context" not in originals:
        originals["launch_persistent_context"] = cls.launch_persistent_context
        if async_mode:
            async def launch_persistent_context(self, user_data_dir, **kwargs):
                patched_kwargs, _info = build_launch_overrides(kwargs, persistent=True)
                if "humanize" in patched_kwargs or "human_preset" in patched_kwargs:
                    return await _cloak_launch_persistent_async(user_data_dir, patched_kwargs)
                return await originals["launch_persistent_context"](self, user_data_dir, **patched_kwargs)
        else:
            def launch_persistent_context(self, user_data_dir, **kwargs):
                patched_kwargs, _info = build_launch_overrides(kwargs, persistent=True)
                if "humanize" in patched_kwargs or "human_preset" in patched_kwargs:
                    return _cloak_launch_persistent_sync(user_data_dir, patched_kwargs)
                return originals["launch_persistent_context"](self, user_data_dir, **patched_kwargs)
        setattr(cls, "launch_persistent_context", launch_persistent_context)


async def _cloak_launch_async(kwargs: dict[str, Any]):
    from cloakbrowser import launch_async

    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        return await launch_async(**_cloak_kwargs(kwargs))
    finally:
        _IN_CLOAK_LAUNCH.reset(token)


def _cloak_launch_sync(kwargs: dict[str, Any]):
    from cloakbrowser import launch

    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        return launch(**_cloak_kwargs(kwargs))
    finally:
        _IN_CLOAK_LAUNCH.reset(token)


async def _cloak_launch_persistent_async(user_data_dir: str | Path, kwargs: dict[str, Any]):
    from cloakbrowser import launch_persistent_context_async

    cleaned = _cloak_kwargs(kwargs)
    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        return await launch_persistent_context_async(user_data_dir=user_data_dir, **cleaned)
    finally:
        _IN_CLOAK_LAUNCH.reset(token)


def _cloak_launch_persistent_sync(user_data_dir: str | Path, kwargs: dict[str, Any]):
    from cloakbrowser import launch_persistent_context

    cleaned = _cloak_kwargs(kwargs)
    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        return launch_persistent_context(user_data_dir=user_data_dir, **cleaned)
    finally:
        _IN_CLOAK_LAUNCH.reset(token)


def _cloak_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(kwargs)
    cleaned.pop("executable_path", None)
    cleaned.pop("ignore_default_args", None)
    return cleaned


def _identity_args(cfg: dict[str, Any]) -> list[str]:
    ident = cfg["identity"]
    args: list[str] = []
    if ident["fingerprint_seed_mode"] == "fixed" and ident["fingerprint_seed"]:
        args.append(f"--fingerprint={ident['fingerprint_seed']}")
    elif ident["fingerprint_seed_mode"] == "random":
        args.append(f"--fingerprint={random.randint(10000, 99999)}")
    if ident["fingerprint_platform"]:
        args.append(f"--fingerprint-platform={ident['fingerprint_platform']}")
    args.append(f"--fingerprint-noise={'true' if ident['fingerprint_noise'] else 'false'}")
    args.append(f"--fingerprint-screen-width={ident['fingerprint_screen_width']}")
    args.append(f"--fingerprint-screen-height={ident['fingerprint_screen_height']}")
    if ident["storage_quota_mb"]:
        args.append(f"--fingerprint-storage-quota={ident['storage_quota_mb']}")
    return args


def _extension_args(cfg: dict[str, Any]) -> list[str]:
    paths = active_extension_paths(cfg)
    if not paths:
        return []
    joined = ",".join(paths)
    return [f"--disable-extensions-except={joined}", f"--load-extension={joined}"]


def _merge_ignore_default_args(existing: Any, additions: list[str]) -> list[str] | bool:
    if existing is True:
        return True
    merged: list[str] = []
    for item in list(existing or []) + additions:
        text = str(item)
        if text not in merged:
            merged.append(text)
    return merged
