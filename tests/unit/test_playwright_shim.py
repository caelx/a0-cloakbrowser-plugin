import asyncio
import sys
from types import ModuleType

from helpers.playwright_shim import (
    _IN_CLOAK_LAUNCH,
    _STATE,
    _cloak_ignore_default_args,
    _cloak_kwargs,
    _patch_class,
    filter_args,
    should_patch_launch,
)


def test_filter_args_drops_conflicts_but_keeps_extension_flags():
    kept, dropped = filter_args(
        [
            "--disable-gpu",
            "--disable-gpu=true",
            "--disable-dev-shm-usage",
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
        "--disable-extensions",
    ]
    assert "--disable-extensions-except=/tmp/ext" in kept
    assert "--load-extension=/tmp/ext" in kept
    assert "--no-sandbox" in kept


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

    assert browser_module.IGNORE_DEFAULT_ARGS == ["--enable-automation"]


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
