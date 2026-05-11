from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

PLUGIN_NAME = "cloakbrowser"
PLUGIN_TITLE = "CloakBrowser"
MANIFEST_NAME = ".cloakbrowser-install-manifest.json"
MATERIALIZED_PLUGIN_DIR = Path("/a0") / "usr" / "plugins" / PLUGIN_NAME

BPC_SOURCE_URL = (
    "https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw"
    "?file=bypass-paywalls-chrome-clean-master.zip"
)
COOKIE_EXTENSION_ID = "edibdbjcniadpccecjdfdjjppcpchdlm"

DEFAULT_CONFIG: dict[str, Any] = {
    "runtime": {
        "enabled": True,
        "headed": True,
        "display": ":99",
        "auto_start_xvfb": True,
        "reuse_existing_display": True,
        "display_width": 1440,
        "display_height": 960,
        "display_depth": 24,
        "viewport_width": 1440,
        "viewport_height": 960,
        "cloakbrowser_cache_dir": "/opt/cloakbrowser",
        "cloakbrowser_auto_update": False,
    },
    "humanization": {
        "humanize": True,
        "human_preset": "default",
    },
    "identity": {
        "fingerprint_seed_mode": "random",
        "fingerprint_seed": "",
        "fingerprint_platform": "Windows",
        "fingerprint_noise": False,
        "fingerprint_screen_width": 1440,
        "fingerprint_screen_height": 960,
        "storage_quota_mb": "",
    },
    "network_location": {
        "proxy": "",
        "geoip": True,
        "timezone": "",
        "locale": "",
        "webrtc_ip_mode": "auto",
        "webrtc_ip": "",
    },
    "advanced": {
        "extra_args": [],
        "filter_default_playwright_args": True,
        "disable_shadow_dom_init_patch": True,
        "patch_runtime_file_if_needed": True,
    },
    "extensions": {
        "install_ublock_origin_lite": True,
        "enable_ublock_origin_lite": True,
        "update_ublock_origin_lite_on_setup": False,
        "install_i_still_dont_care_about_cookies": True,
        "enable_i_still_dont_care_about_cookies": True,
        "update_i_still_dont_care_about_cookies_on_setup": True,
        "install_bypass_paywalls_clean": False,
        "enable_bypass_paywalls_clean": False,
        "update_bypass_paywalls_clean_on_setup": False,
    },
    "ublock_origin_lite": {
        "filtering_mode": "complete",
        "strict_block_mode": True,
        "enabled_rulesets": [
            "ublock-filters",
            "easylist",
            "easyprivacy",
            "pgl",
            "adguard-spyware-url",
            "block-lan",
            "ublock-badware",
            "urlhaus-full",
            "annoyances-ai",
            "annoyances-cookies",
            "annoyances-notifications",
            "annoyances-others",
            "annoyances-overlays",
            "annoyances-social",
            "annoyances-widgets",
        ],
    },
    "bypass_paywalls_clean": {
        "opt_in_setcookie": True,
        "opt_in_custom_sites": True,
        "opt_in_update": True,
    },
}


def plugin_dir() -> Path:
    local_root = Path(__file__).resolve().parents[1]
    if local_root == MATERIALIZED_PLUGIN_DIR:
        return local_root
    if MATERIALIZED_PLUGIN_DIR.is_dir():
        return MATERIALIZED_PLUGIN_DIR
    try:
        from helpers import plugins

        found = plugins.find_plugin_dir(PLUGIN_NAME)
        if found:
            return Path(found)
    except Exception:
        pass
    return Path(__file__).resolve().parents[1]


def manifest_path() -> Path:
    return plugin_dir() / MANIFEST_NAME


def state_dir() -> Path:
    path = plugin_dir() / ".cloakbrowser"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extension_root() -> Path:
    path = state_dir() / "extensions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def shim_root() -> Path:
    path = state_dir() / "playwright"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_saved_config() -> dict[str, Any]:
    path = plugin_dir() / "config.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
    return {}


def get_config(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    if raw is None:
        try:
            from helpers import plugins

            raw = plugins.get_plugin_config(PLUGIN_NAME) or {}
        except Exception:
            raw = _load_saved_config()
    return normalize_config(raw)


def save_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_config(config)
    try:
        from helpers import plugins

        plugins.save_plugin_config(PLUGIN_NAME, "", "", normalized)
    except Exception:
        (plugin_dir() / "config.json").write_text(
            json.dumps(normalized, indent=2) + "\n",
            encoding="utf-8",
        )
    return normalized


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw_cfg = raw if isinstance(raw, dict) else {}
    cfg = _deep_merge(DEFAULT_CONFIG, raw_cfg)
    rt = cfg["runtime"]
    rt["enabled"] = _bool(rt.get("enabled"), True)
    rt["headed"] = _bool(rt.get("headed"), True)
    rt["display"] = _display(rt.get("display"), ":99")
    rt["auto_start_xvfb"] = _bool(rt.get("auto_start_xvfb"), True)
    rt["reuse_existing_display"] = _bool(rt.get("reuse_existing_display"), True)
    rt["display_width"] = _int(rt.get("display_width"), 1440, 320, 8192)
    rt["display_height"] = _int(rt.get("display_height"), 960, 200, 8192)
    rt["display_depth"] = _int(rt.get("display_depth"), 24, 8, 32)
    rt["viewport_width"] = _int(rt.get("viewport_width"), 1440, 320, 8192)
    rt["viewport_height"] = _int(rt.get("viewport_height"), 960, 200, 8192)
    rt["cloakbrowser_cache_dir"] = str(rt.get("cloakbrowser_cache_dir") or "/opt/cloakbrowser")
    rt["cloakbrowser_auto_update"] = _bool(rt.get("cloakbrowser_auto_update"), False)

    human = cfg["humanization"]
    human["humanize"] = _bool(human.get("humanize"), True)
    human["human_preset"] = str(human.get("human_preset") or "default").strip()
    if human["human_preset"] not in {"default", "careful"}:
        human["human_preset"] = "default"

    ident = cfg["identity"]
    ident["fingerprint_seed_mode"] = str(ident.get("fingerprint_seed_mode") or "random").strip()
    if ident["fingerprint_seed_mode"] not in {"random", "fixed"}:
        ident["fingerprint_seed_mode"] = "random"
    ident["fingerprint_seed"] = str(ident.get("fingerprint_seed") or "").strip()
    ident["fingerprint_platform"] = str(ident.get("fingerprint_platform") or "Windows").strip()
    ident["fingerprint_noise"] = _bool(ident.get("fingerprint_noise"), False)
    ident["fingerprint_screen_width"] = _int(
        ident.get("fingerprint_screen_width"), 1440, 320, 8192
    )
    ident["fingerprint_screen_height"] = _int(
        ident.get("fingerprint_screen_height"), 960, 200, 8192
    )
    ident["storage_quota_mb"] = _optional_int_string(ident.get("storage_quota_mb"))

    net = cfg["network_location"]
    net["proxy"] = str(net.get("proxy") or "").strip()
    net["geoip"] = _bool(net.get("geoip"), True)
    explicit_timezone = _has_nested_key(raw_cfg, "network_location", "timezone")
    explicit_locale = _has_nested_key(raw_cfg, "network_location", "locale")
    net["timezone"] = str(net.get("timezone") or "").strip()
    net["locale"] = str(net.get("locale") or "").strip()
    if not net["geoip"]:
        net["timezone"] = net["timezone"] or _detect_timezone()
        net["locale"] = net["locale"] or _detect_locale()
    elif not explicit_timezone:
        net["timezone"] = ""
    elif not explicit_locale:
        net["locale"] = ""
    net["webrtc_ip_mode"] = str(net.get("webrtc_ip_mode") or "auto").strip()
    if net["webrtc_ip_mode"] not in {"auto", "disabled", "explicit"}:
        net["webrtc_ip_mode"] = "auto"
    net["webrtc_ip"] = str(net.get("webrtc_ip") or "").strip()

    adv = cfg["advanced"]
    adv["extra_args"] = _string_list(adv.get("extra_args"))
    adv["filter_default_playwright_args"] = _bool(adv.get("filter_default_playwright_args"), True)
    adv["disable_shadow_dom_init_patch"] = _bool(adv.get("disable_shadow_dom_init_patch"), True)
    adv.pop("preserve_headed_placeholder_page", None)
    adv["patch_runtime_file_if_needed"] = _bool(adv.get("patch_runtime_file_if_needed"), True)

    for key, default in DEFAULT_CONFIG["extensions"].items():
        cfg["extensions"][key] = _bool(cfg["extensions"].get(key), bool(default))

    ubol = cfg["ublock_origin_lite"]
    ubol["filtering_mode"] = str(ubol.get("filtering_mode") or "complete").strip()
    if ubol["filtering_mode"] not in {"none", "basic", "optimal", "complete"}:
        ubol["filtering_mode"] = "complete"
    ubol["strict_block_mode"] = _bool(ubol.get("strict_block_mode"), True)
    ubol["enabled_rulesets"] = _string_list(ubol.get("enabled_rulesets")) or list(
        DEFAULT_CONFIG["ublock_origin_lite"]["enabled_rulesets"]
    )

    bpc = cfg["bypass_paywalls_clean"]
    bpc["opt_in_setcookie"] = _bool(bpc.get("opt_in_setcookie"), True)
    bpc["opt_in_custom_sites"] = _bool(bpc.get("opt_in_custom_sites"), True)
    bpc["opt_in_update"] = _bool(bpc.get("opt_in_update"), True)
    return cfg


def redacted_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = copy.deepcopy(get_config(config))
    proxy = cfg["network_location"].get("proxy", "")
    if proxy:
        cfg["network_location"]["proxy"] = _redact_proxy(proxy)
    return cfg


def apply_environment(config: dict[str, Any] | None = None) -> None:
    cfg = get_config(config)
    os.environ["CLOAKBROWSER_CACHE_DIR"] = cfg["runtime"]["cloakbrowser_cache_dir"]
    os.environ["CLOAKBROWSER_AUTO_UPDATE"] = (
        "true" if cfg["runtime"]["cloakbrowser_auto_update"] else "false"
    )
    display = cfg["runtime"].get("display")
    if display:
        os.environ.setdefault("DISPLAY", display)


def _bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def _int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _optional_int_string(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        number = int(raw)
    except ValueError:
        return ""
    return str(max(0, number))


def _display(value: Any, default: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return default
    return raw if raw.startswith(":") else f":{raw}"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _has_nested_key(value: dict[str, Any], section: str, key: str) -> bool:
    section_value = value.get(section)
    return isinstance(section_value, dict) and key in section_value


def _detect_timezone() -> str:
    env_tz = str(os.environ.get("TZ") or "").strip()
    if env_tz and env_tz.upper() not in {"UTC0", "GMT0"}:
        return env_tz
    try:
        text = Path("/etc/timezone").read_text(encoding="utf-8").strip()
        if text:
            return text
    except Exception:
        pass
    try:
        target = Path("/etc/localtime").resolve()
        marker = "zoneinfo/"
        target_text = str(target)
        if marker in target_text:
            return target_text.split(marker, 1)[1]
    except Exception:
        pass
    return ""


def _detect_locale() -> str:
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        locale = _normalize_locale(os.environ.get(key))
        if locale:
            return locale
    return ""


def _normalize_locale(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw or raw.upper() in {"C", "POSIX"}:
        return ""
    raw = raw.split(".", 1)[0].split("@", 1)[0]
    if not raw or raw.upper() in {"C", "POSIX"}:
        return ""
    return raw.replace("_", "-")


def _redact_proxy(proxy: str) -> str:
    if "@" not in proxy:
        return proxy
    scheme, rest = proxy.split("://", 1) if "://" in proxy else ("", proxy)
    _, host = rest.rsplit("@", 1)
    prefix = f"{scheme}://" if scheme else ""
    return f"{prefix}<redacted>@{host}"
