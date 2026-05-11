from __future__ import annotations

import random
import json
import urllib.error
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from .config import apply_environment, get_config
from .extensions import active_extension_paths
from .seed_playwright import ensure_masquerade

DROP_EXACT = {"--disable-dev-shm-usage", "--disable-gpu", "--disable-extensions", "--no-sandbox"}
DROP_PREFIXES = ("--disable-dev-shm-usage=", "--disable-gpu=", "--disable-extensions=")
IGNORE_DEFAULT_ADDITIONS = [
    "--disable-gpu",
    "--disable-extensions",
    "--disable-dev-shm-usage",
]

_STATE: dict[str, Any] = {
    "patched": False,
    "async_originals": {},
    "sync_originals": {},
    "last_launch": {},
}
_PUBLIC_GEOIP_CACHE: dict[str, str | None] | None = None
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
    return dedupe_args(kept), dropped


def dedupe_args(args: list[str] | tuple[str, ...] | None) -> list[str]:
    deduped: list[str] = []
    positions: dict[str, int] = {}
    for arg in list(args or []):
        text = str(arg)
        key = _switch_key(text)
        if key in positions:
            deduped[positions[key]] = text
            continue
        positions[key] = len(deduped)
        deduped.append(text)
    return deduped


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
    filtered_args, extra_dropped_args = filter_args(filtered_args)
    dropped_args.extend(arg for arg in extra_dropped_args if arg not in dropped_args)
    filtered_args = dedupe_args(filtered_args)

    proxy = cfg["network_location"]["proxy"] or None
    timezone = cfg["network_location"]["timezone"] or None
    locale = cfg["network_location"]["locale"] or None
    geoip = bool(cfg["network_location"]["geoip"])
    timezone, locale, exit_ip = resolve_location(
        maybe_resolve_geoip,
        geoip=geoip,
        proxy=proxy,
        timezone=timezone,
        locale=locale,
    )
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
    final_args = [arg for arg in dedupe_args(final_args) if arg != "--no-sandbox"]
    launch_kwargs = dict(kwargs)
    launch_kwargs.pop("channel", None)
    launch_kwargs["executable_path"] = binary
    launch_kwargs["headless"] = headless
    launch_kwargs["args"] = final_args
    launch_kwargs["ignore_default_args"] = _merge_ignore_default_args(
        kwargs.get("ignore_default_args"),
        IGNORE_DEFAULT_ARGS + IGNORE_DEFAULT_ADDITIONS,
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
        "shared_memory": {
            "disable_dev_shm_usage": "--disable-dev-shm-usage" not in launch_kwargs["ignore_default_args"],
        },
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


def resolve_location(
    maybe_resolve_geoip,
    *,
    geoip: bool,
    proxy: str | None,
    timezone: str | None,
    locale: str | None,
) -> tuple[str | None, str | None, str | None]:
    if not geoip:
        return timezone, locale, None
    if proxy:
        return maybe_resolve_geoip(geoip, proxy, timezone, locale)
    if timezone and locale:
        return timezone, locale, None
    public_geo = _resolve_public_geoip()
    if timezone is None:
        timezone = public_geo.get("timezone")
    if locale is None:
        locale = public_geo.get("locale")
    return timezone, locale, public_geo.get("ip")


def _resolve_public_geoip() -> dict[str, str | None]:
    global _PUBLIC_GEOIP_CACHE
    if _PUBLIC_GEOIP_CACHE is not None:
        return dict(_PUBLIC_GEOIP_CACHE)

    for url, parser in (
        ("https://ipapi.co/json/", _parse_ipapi_geo),
        ("https://ipwho.is/", _parse_ipwhois_geo),
    ):
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            parsed = parser(payload)
            if parsed.get("timezone") or parsed.get("locale") or parsed.get("ip"):
                _PUBLIC_GEOIP_CACHE = parsed
                return dict(parsed)
        except (OSError, ValueError, urllib.error.URLError):
            continue

    _PUBLIC_GEOIP_CACHE = {"timezone": None, "locale": None, "ip": None}
    return dict(_PUBLIC_GEOIP_CACHE)


def _parse_ipapi_geo(payload: dict[str, Any]) -> dict[str, str | None]:
    languages = str(payload.get("languages") or "")
    locale = languages.split(",", 1)[0].strip() or _locale_for_country(payload.get("country_code"))
    return {
        "timezone": _clean_geo_string(payload.get("timezone")),
        "locale": _clean_geo_string(locale),
        "ip": _clean_geo_string(payload.get("ip")),
    }


def _parse_ipwhois_geo(payload: dict[str, Any]) -> dict[str, str | None]:
    timezone_payload = payload.get("timezone") if isinstance(payload.get("timezone"), dict) else {}
    return {
        "timezone": _clean_geo_string(timezone_payload.get("id")),
        "locale": _locale_for_country(payload.get("country_code")),
        "ip": _clean_geo_string(payload.get("ip")),
    }


def _locale_for_country(country_code: Any) -> str | None:
    country = str(country_code or "").strip().upper()
    if not country:
        return None
    language = {
        "US": "en",
        "GB": "en",
        "CA": "en",
        "AU": "en",
        "NZ": "en",
        "IE": "en",
    }.get(country, "en")
    return f"{language}-{country}"


def _clean_geo_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _patch_class(cls: type, *, async_mode: bool) -> None:
    originals_key = "async_originals" if async_mode else "sync_originals"
    originals = _STATE[originals_key].setdefault(cls, {})
    if "launch" not in originals:
        originals["launch"] = cls.launch
        if async_mode:
            async def launch(self, **kwargs):
                if _IN_CLOAK_LAUNCH.get():
                    return await originals["launch"](self, **kwargs)
                patched_kwargs, _info = build_launch_overrides(kwargs, persistent=False)
                if "humanize" in patched_kwargs or "human_preset" in patched_kwargs:
                    return await _cloak_launch_async(patched_kwargs)
                return await originals["launch"](self, **patched_kwargs)
        else:
            def launch(self, **kwargs):
                if _IN_CLOAK_LAUNCH.get():
                    return originals["launch"](self, **kwargs)
                patched_kwargs, _info = build_launch_overrides(kwargs, persistent=False)
                if "humanize" in patched_kwargs or "human_preset" in patched_kwargs:
                    return _cloak_launch_sync(patched_kwargs)
                return originals["launch"](self, **patched_kwargs)
        setattr(cls, "launch", launch)
    if "launch_persistent_context" not in originals:
        originals["launch_persistent_context"] = cls.launch_persistent_context
        if async_mode:
            async def launch_persistent_context(self, user_data_dir, **kwargs):
                if _IN_CLOAK_LAUNCH.get():
                    return await originals["launch_persistent_context"](
                        self, user_data_dir, **kwargs
                    )
                patched_kwargs, _info = build_launch_overrides(kwargs, persistent=True)
                if "humanize" in patched_kwargs or "human_preset" in patched_kwargs:
                    return await _cloak_launch_persistent_async(user_data_dir, patched_kwargs)
                return await originals["launch_persistent_context"](self, user_data_dir, **patched_kwargs)
        else:
            def launch_persistent_context(self, user_data_dir, **kwargs):
                if _IN_CLOAK_LAUNCH.get():
                    return originals["launch_persistent_context"](self, user_data_dir, **kwargs)
                patched_kwargs, _info = build_launch_overrides(kwargs, persistent=True)
                if "humanize" in patched_kwargs or "human_preset" in patched_kwargs:
                    return _cloak_launch_persistent_sync(user_data_dir, patched_kwargs)
                return originals["launch_persistent_context"](self, user_data_dir, **patched_kwargs)
        setattr(cls, "launch_persistent_context", launch_persistent_context)


async def _cloak_launch_async(kwargs: dict[str, Any]):
    from cloakbrowser import launch_async

    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        with _cloak_ignore_default_args(kwargs):
            return await launch_async(**_cloak_kwargs(kwargs))
    finally:
        _IN_CLOAK_LAUNCH.reset(token)


def _cloak_launch_sync(kwargs: dict[str, Any]):
    from cloakbrowser import launch

    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        with _cloak_ignore_default_args(kwargs):
            return launch(**_cloak_kwargs(kwargs))
    finally:
        _IN_CLOAK_LAUNCH.reset(token)


async def _cloak_launch_persistent_async(user_data_dir: str | Path, kwargs: dict[str, Any]):
    from cloakbrowser import launch_persistent_context_async

    cleaned = _cloak_kwargs(kwargs)
    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        with _cloak_ignore_default_args(kwargs):
            return await launch_persistent_context_async(user_data_dir=user_data_dir, **cleaned)
    finally:
        _IN_CLOAK_LAUNCH.reset(token)


def _cloak_launch_persistent_sync(user_data_dir: str | Path, kwargs: dict[str, Any]):
    from cloakbrowser import launch_persistent_context

    cleaned = _cloak_kwargs(kwargs)
    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        with _cloak_ignore_default_args(kwargs):
            return launch_persistent_context(user_data_dir=user_data_dir, **cleaned)
    finally:
        _IN_CLOAK_LAUNCH.reset(token)


def _cloak_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(kwargs)
    cleaned.pop("executable_path", None)
    cleaned.pop("ignore_default_args", None)
    return cleaned


@contextmanager
def _cloak_ignore_default_args(kwargs: dict[str, Any]):
    additions = kwargs.get("ignore_default_args")
    if not additions:
        yield
        return

    import cloakbrowser.browser as cloak_browser

    original = getattr(cloak_browser, "IGNORE_DEFAULT_ARGS", None)
    original_stealth_args = getattr(cloak_browser, "get_default_stealth_args", None)
    if additions is True:
        merged: list[str] | bool = True
    else:
        merged = _merge_ignore_default_args(original or [], list(additions))
    cloak_browser.IGNORE_DEFAULT_ARGS = merged
    if callable(original_stealth_args):
        cloak_browser.get_default_stealth_args = _default_stealth_args_without_no_sandbox(
            original_stealth_args
        )
    try:
        yield
    finally:
        cloak_browser.IGNORE_DEFAULT_ARGS = original
        if callable(original_stealth_args):
            cloak_browser.get_default_stealth_args = original_stealth_args


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


def _switch_key(arg: str) -> str:
    if arg.startswith("--") and "=" in arg:
        return arg.split("=", 1)[0]
    return arg


def _default_stealth_args_without_no_sandbox(original):
    def wrapped():
        return [arg for arg in original() if arg != "--no-sandbox"]

    return wrapped
