import asyncio
import sys
from types import ModuleType

from helpers.playwright_shim import (
    _IN_CLOAK_LAUNCH,
    _STATE,
    _cloak_ignore_default_args,
    _cloak_kwargs,
    _patch_class,
    dedupe_args,
    filter_args,
    should_patch_launch,
)


def test_filter_args_drops_conflicts_but_keeps_extension_flags():
    kept, dropped = filter_args(
        [
            "--disable-gpu",
            "--disable-gpu=true",
            "--disable-dev-shm-usage",
            "--disable-dev-shm-usage=true",
            "--disable-extensions",
            "--disable-extensions-except=/tmp/ext",
            "--load-extension=/tmp/ext",
            "--no-sandbox",
        ]
    )

    assert dropped == [
        "--disable-gpu",
        "--disable-gpu=true",
        "--disable-dev-shm-usage",
        "--disable-dev-shm-usage=true",
        "--disable-extensions",
        "--no-sandbox",
    ]
    assert "--disable-extensions-except=/tmp/ext" in kept
    assert "--load-extension=/tmp/ext" in kept
    assert "--no-sandbox" in dropped


def test_dedupe_args_keeps_last_switch_value():
    assert dedupe_args(
        [
            "--no-sandbox",
            "--fingerprint-platform=Linux",
            "--fingerprint-platform=Windows",
            "--proxy-server=http://old.test",
            "--proxy-server=http://new.test",
        ]
    ) == [
        "--no-sandbox",
        "--fingerprint-platform=Windows",
        "--proxy-server=http://new.test",
    ]


def test_build_launch_overrides_drops_explicit_no_sandbox(monkeypatch):
    from helpers import playwright_shim

    package = ModuleType("cloakbrowser")
    package.ensure_binary = lambda: "/opt/cloakbrowser/chrome"
    browser_module = ModuleType("cloakbrowser.browser")
    browser_module.build_args = lambda _stealth, args, **_kwargs: list(args)
    browser_module.maybe_resolve_geoip = lambda geoip, proxy, timezone, locale: (
        timezone,
        locale,
        None,
    )
    config_module = ModuleType("cloakbrowser.config")
    config_module.IGNORE_DEFAULT_ARGS = []
    monkeypatch.setitem(sys.modules, "cloakbrowser", package)
    monkeypatch.setitem(sys.modules, "cloakbrowser.browser", browser_module)
    monkeypatch.setitem(sys.modules, "cloakbrowser.config", config_module)
    monkeypatch.setattr(playwright_shim, "ensure_masquerade", lambda _binary: None)
    monkeypatch.setattr(playwright_shim, "apply_environment", lambda _cfg: None)
    monkeypatch.setattr(playwright_shim, "get_config", lambda: _minimal_config())

    launch_kwargs, _info = playwright_shim.build_launch_overrides(
        {"args": ["--no-sandbox"]},
        persistent=True,
    )

    assert "--no-sandbox" not in launch_kwargs["args"]
    assert "--no-sandbox" not in launch_kwargs["ignore_default_args"]
    assert "--disable-dev-shm-usage" not in launch_kwargs["args"]
    assert "--disable-dev-shm-usage" in launch_kwargs["ignore_default_args"]


def test_build_launch_overrides_uses_old_working_profile_defaults(monkeypatch):
    from helpers import playwright_shim
    from helpers.config import normalize_config

    geoip_calls = []
    package = ModuleType("cloakbrowser")
    package.ensure_binary = lambda: "/opt/cloakbrowser/chrome"
    browser_module = ModuleType("cloakbrowser.browser")

    def maybe_resolve_geoip(geoip, proxy, timezone, locale):
        geoip_calls.append(
            {
                "geoip": geoip,
                "proxy": proxy,
                "timezone": timezone,
                "locale": locale,
            }
        )
        return "America/New_York", "en-US", "203.0.113.10"

    def build_args(_stealth, args, **kwargs):
        out = list(args)
        if kwargs.get("timezone"):
            out.append(f"--fingerprint-timezone={kwargs['timezone']}")
        if kwargs.get("locale"):
            out.append(f"--fingerprint-locale={kwargs['locale']}")
        return out

    browser_module.build_args = build_args
    browser_module.maybe_resolve_geoip = maybe_resolve_geoip
    config_module = ModuleType("cloakbrowser.config")
    config_module.IGNORE_DEFAULT_ARGS = []
    monkeypatch.setitem(sys.modules, "cloakbrowser", package)
    monkeypatch.setitem(sys.modules, "cloakbrowser.browser", browser_module)
    monkeypatch.setitem(sys.modules, "cloakbrowser.config", config_module)
    monkeypatch.setattr(playwright_shim, "ensure_masquerade", lambda _binary: None)
    monkeypatch.setattr(playwright_shim, "apply_environment", lambda _cfg: None)
    monkeypatch.setattr(playwright_shim, "get_config", lambda: normalize_config({}))
    monkeypatch.setattr(playwright_shim, "active_extension_paths", lambda _cfg: [])
    monkeypatch.setattr(
        playwright_shim,
        "_resolve_public_geoip",
        lambda: {
            "timezone": "America/New_York",
            "locale": "en-US",
            "ip": "203.0.113.10",
        },
    )

    launch_kwargs, _info = playwright_shim.build_launch_overrides({}, persistent=True)

    assert geoip_calls == []
    assert launch_kwargs["headless"] is False
    assert launch_kwargs["viewport"] == {"width": 1440, "height": 960}
    assert launch_kwargs["screen"] == {"width": 1440, "height": 960}
    assert launch_kwargs["humanize"] is True
    assert launch_kwargs["human_preset"] == "default"
    assert "--fingerprint-screen-width=1440" in launch_kwargs["args"]
    assert "--fingerprint-screen-height=960" in launch_kwargs["args"]
    assert "--fingerprint-timezone=America/New_York" in launch_kwargs["args"]
    assert "--fingerprint-locale=en-US" in launch_kwargs["args"]
    assert "--fingerprint-webrtc-ip=203.0.113.10" in launch_kwargs["args"]


def test_build_launch_overrides_uses_cloakbrowser_geoip_for_proxy(monkeypatch):
    from helpers import playwright_shim
    from helpers.config import normalize_config

    geoip_calls = []
    proxy_calls = []
    package = ModuleType("cloakbrowser")
    package.ensure_binary = lambda: "/opt/cloakbrowser/chrome"
    browser_module = ModuleType("cloakbrowser.browser")

    def maybe_resolve_geoip(geoip, proxy, timezone, locale):
        geoip_calls.append(
            {
                "geoip": geoip,
                "proxy": proxy,
                "timezone": timezone,
                "locale": locale,
            }
        )
        return "America/Chicago", "en-US", "198.51.100.10"

    def build_args(_stealth, args, **kwargs):
        out = list(args)
        if kwargs.get("timezone"):
            out.append(f"--fingerprint-timezone={kwargs['timezone']}")
        if kwargs.get("locale"):
            out.append(f"--fingerprint-locale={kwargs['locale']}")
        return out

    browser_module.build_args = build_args
    browser_module.maybe_resolve_geoip = maybe_resolve_geoip
    browser_module._resolve_proxy_config = lambda proxy: (
        proxy_calls.append(proxy)
        or ({"proxy": {"server": proxy}}, ["--proxy-bypass-list=<-loopback>"])
    )
    browser_module._resolve_webrtc_args = lambda args, proxy: list(args)
    config_module = ModuleType("cloakbrowser.config")
    config_module.IGNORE_DEFAULT_ARGS = []
    monkeypatch.setitem(sys.modules, "cloakbrowser", package)
    monkeypatch.setitem(sys.modules, "cloakbrowser.browser", browser_module)
    monkeypatch.setitem(sys.modules, "cloakbrowser.config", config_module)
    monkeypatch.setattr(playwright_shim, "ensure_masquerade", lambda _binary: None)
    monkeypatch.setattr(playwright_shim, "apply_environment", lambda _cfg: None)
    monkeypatch.setattr(playwright_shim, "active_extension_paths", lambda _cfg: [])
    monkeypatch.setattr(
        playwright_shim,
        "get_config",
        lambda: normalize_config({"network_location": {"proxy": "http://proxy.test:8080"}}),
    )
    monkeypatch.setattr(
        playwright_shim,
        "_resolve_public_geoip",
        lambda: {"timezone": "America/New_York", "locale": "en-US", "ip": "203.0.113.10"},
    )

    launch_kwargs, _info = playwright_shim.build_launch_overrides({}, persistent=True)

    assert geoip_calls == [
        {
            "geoip": True,
            "proxy": "http://proxy.test:8080",
            "timezone": None,
            "locale": None,
        }
    ]
    assert "--fingerprint-timezone=America/Chicago" in launch_kwargs["args"]
    assert "--fingerprint-webrtc-ip=198.51.100.10" in launch_kwargs["args"]
    assert "--proxy-bypass-list=<-loopback>" in launch_kwargs["args"]
    assert launch_kwargs["proxy"] == {"server": "http://proxy.test:8080"}
    assert proxy_calls == ["http://proxy.test:8080"]


def test_build_launch_overrides_uses_native_webrtc_proxy_helper(monkeypatch):
    from helpers import playwright_shim
    from helpers.config import normalize_config

    package = ModuleType("cloakbrowser")
    package.ensure_binary = lambda: "/opt/cloakbrowser/chrome"
    browser_module = ModuleType("cloakbrowser.browser")
    browser_module.build_args = lambda _stealth, args, **_kwargs: list(args)
    browser_module.maybe_resolve_geoip = lambda geoip, proxy, timezone, locale: (
        timezone,
        locale,
        None,
    )
    browser_module._resolve_proxy_config = lambda proxy: ({}, [f"--proxy-server={proxy}"])
    browser_module._resolve_webrtc_args = lambda args, proxy: [
        "--fingerprint-webrtc-ip=198.51.100.55" if arg == "--fingerprint-webrtc-ip=auto" else arg
        for arg in args
    ]
    config_module = ModuleType("cloakbrowser.config")
    config_module.IGNORE_DEFAULT_ARGS = []
    monkeypatch.setitem(sys.modules, "cloakbrowser", package)
    monkeypatch.setitem(sys.modules, "cloakbrowser.browser", browser_module)
    monkeypatch.setitem(sys.modules, "cloakbrowser.config", config_module)
    monkeypatch.setattr(playwright_shim, "ensure_masquerade", lambda _binary: None)
    monkeypatch.setattr(playwright_shim, "apply_environment", lambda _cfg: None)
    monkeypatch.setattr(playwright_shim, "active_extension_paths", lambda _cfg: [])
    monkeypatch.setattr(
        playwright_shim,
        "get_config",
        lambda: normalize_config(
            {
                "network_location": {
                    "proxy": "socks5://proxy.test:1080",
                    "timezone": "America/Chicago",
                    "locale": "en-US",
                }
            }
        ),
    )

    launch_kwargs, _info = playwright_shim.build_launch_overrides({}, persistent=True)

    assert "proxy" not in launch_kwargs
    assert "--proxy-server=socks5://proxy.test:1080" in launch_kwargs["args"]
    assert "--fingerprint-webrtc-ip=198.51.100.55" in launch_kwargs["args"]


def test_agent_zero_managed_browser_path_is_patched():
    assert should_patch_launch(
        {
            "executable_path": "/git/agent-zero/usr/plugins/_browser/playwright/chromium-1169/chrome-linux/chrome"
        }
    )


def test_cloak_kwargs_strips_launch_wrapper_args():
    cleaned = _cloak_kwargs(
        {
            "executable_path": "/opt/cloakbrowser/chrome",
            "ignore_default_args": ["--disable-dev-shm-usage"],
            "args": ["--fingerprint=12345"],
        }
    )

    assert "executable_path" not in cleaned
    assert "ignore_default_args" not in cleaned


def test_cloak_ignore_default_args_patches_cloakbrowser_module(monkeypatch):
    package = ModuleType("cloakbrowser")
    browser_module = ModuleType("cloakbrowser.browser")
    browser_module.IGNORE_DEFAULT_ARGS = ["--enable-automation"]
    browser_module.get_default_stealth_args = lambda: ["--no-sandbox", "--fingerprint=12345"]
    package.browser = browser_module
    monkeypatch.setitem(sys.modules, "cloakbrowser", package)
    monkeypatch.setitem(sys.modules, "cloakbrowser.browser", browser_module)

    with _cloak_ignore_default_args(
        {"ignore_default_args": ["--enable-automation", "--disable-dev-shm-usage"]}
    ):
        assert browser_module.IGNORE_DEFAULT_ARGS == [
            "--enable-automation",
            "--disable-dev-shm-usage",
        ]
        assert browser_module.get_default_stealth_args() == ["--fingerprint=12345"]

    assert browser_module.IGNORE_DEFAULT_ARGS == ["--enable-automation"]
    assert browser_module.get_default_stealth_args() == ["--no-sandbox", "--fingerprint=12345"]


def test_patched_async_launch_bypasses_when_inside_cloak_launch():
    calls = []

    class BrowserType:
        async def launch(self, **kwargs):
            calls.append(("launch", kwargs))
            return "browser"

        async def launch_persistent_context(self, user_data_dir, **kwargs):
            calls.append(("persistent", user_data_dir, kwargs))
            return "context"

    _STATE["async_originals"].pop(BrowserType, None)
    _patch_class(BrowserType, async_mode=True)
    token = _IN_CLOAK_LAUNCH.set(True)
    try:
        result = asyncio.run(
            BrowserType().launch_persistent_context(
                "/tmp/profile",
                ignore_default_args=["--disable-dev-shm-usage"],
                humanize=True,
            )
        )
    finally:
        _IN_CLOAK_LAUNCH.reset(token)
        for name, original in _STATE["async_originals"].pop(BrowserType, {}).items():
            setattr(BrowserType, name, original)

    assert result == "context"
    assert calls == [
        (
            "persistent",
            "/tmp/profile",
            {"ignore_default_args": ["--disable-dev-shm-usage"], "humanize": True},
        )
    ]


def _minimal_config():
    return {
        "runtime": {
            "enabled": True,
            "headed": True,
            "viewport_width": 1440,
            "viewport_height": 960,
            "display_width": 1440,
            "display_height": 960,
        },
        "humanization": {"humanize": False, "human_preset": "default"},
        "identity": {
            "fingerprint_seed_mode": "fixed",
            "fingerprint_seed": "12345",
            "fingerprint_platform": "Windows",
            "fingerprint_noise": False,
            "fingerprint_screen_width": 1440,
            "fingerprint_screen_height": 960,
            "storage_quota_mb": "",
        },
        "network_location": {
            "proxy": "",
            "timezone": "",
            "locale": "",
            "geoip": True,
            "webrtc_ip_mode": "auto",
            "webrtc_ip": "",
        },
        "advanced": {"extra_args": []},
        "extensions": {},
    }
