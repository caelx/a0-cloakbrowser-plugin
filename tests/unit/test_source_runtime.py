import pytest

from helpers import source_runtime


def test_source_runtime_fails_closed_when_enabled_launch_is_not_patched(monkeypatch):
    monkeypatch.setattr(
        source_runtime,
        "build_launch_overrides",
        lambda kwargs, persistent: (dict(kwargs), {"patched": False}),
    )
    monkeypatch.setattr(source_runtime, "_plugin_enabled", lambda: True)

    with pytest.raises(RuntimeError, match="launch hook is unavailable"):
        import asyncio

        asyncio.run(source_runtime.launch_persistent_context(object(), {"user_data_dir": "/tmp/p"}))
