import asyncio

from helpers import source_runtime


def test_launch_persistent_context_uses_cloakbrowser_wrapper_when_enabled(monkeypatch):
    calls = []

    async def fake_cloak_launch(user_data_dir, kwargs):
        calls.append(("cloak", user_data_dir, kwargs))
        return "cloak-context"

    def fake_build_launch_overrides(kwargs, *, persistent):
        assert persistent is True
        assert kwargs["user_data_dir"] == "/tmp/profile"
        return {"user_data_dir": "/tmp/profile", "humanize": False}, {"patched": True}

    class BrowserType:
        async def launch_persistent_context(self, user_data_dir, **kwargs):
            calls.append(("upstream", user_data_dir, kwargs))
            return "upstream-context"

    monkeypatch.setattr(source_runtime, "build_launch_overrides", fake_build_launch_overrides)
    monkeypatch.setattr(source_runtime, "_cloak_launch_persistent_async", fake_cloak_launch)

    result = asyncio.run(
        source_runtime.launch_persistent_context(
            BrowserType(),
            {"user_data_dir": "/tmp/profile"},
        )
    )

    assert result == "cloak-context"
    assert calls == [("cloak", "/tmp/profile", {"humanize": False})]


def test_launch_persistent_context_falls_back_when_runtime_disabled(monkeypatch):
    calls = []

    def fake_build_launch_overrides(kwargs, *, persistent):
        return dict(kwargs), {"patched": False, "reason": "disabled"}

    class BrowserType:
        async def launch_persistent_context(self, user_data_dir, **kwargs):
            calls.append(("upstream", user_data_dir, kwargs))
            return "upstream-context"

    monkeypatch.setattr(source_runtime, "build_launch_overrides", fake_build_launch_overrides)

    result = asyncio.run(
        source_runtime.launch_persistent_context(
            BrowserType(),
            {"user_data_dir": "/tmp/profile", "headless": False},
        )
    )

    assert result == "upstream-context"
    assert calls == [("upstream", "/tmp/profile", {"headless": False})]
