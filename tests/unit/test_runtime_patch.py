import sys
import types

from helpers import runtime_patch


class FakeRuntimeCore:
    @staticmethod
    def _shadow_dom_script():
        return "original"

    async def _start(self):
        return None


def install_fake_runtime(monkeypatch):
    runtime_mod = types.ModuleType("plugins._browser.helpers.runtime")
    runtime_mod._BrowserRuntimeCore = FakeRuntimeCore
    monkeypatch.setitem(sys.modules, "plugins", types.ModuleType("plugins"))
    monkeypatch.setitem(sys.modules, "plugins._browser", types.ModuleType("plugins._browser"))
    monkeypatch.setitem(sys.modules, "plugins._browser.helpers", types.ModuleType("plugins._browser.helpers"))
    monkeypatch.setitem(sys.modules, "plugins._browser.helpers.runtime", runtime_mod)


def test_shadow_dom_script_is_noop_and_restored(monkeypatch):
    install_fake_runtime(monkeypatch)
    monkeypatch.setattr(
        runtime_patch,
        "_agent_zero_import_context",
        lambda: _NullContext(),
    )
    monkeypatch.setattr(
        "helpers.config.get_config",
        lambda: {
            "advanced": {
                "disable_shadow_dom_init_patch": True,
                "preserve_headed_placeholder_page": True,
            },
            "runtime": {"headed": True},
        },
    )

    runtime_patch.unpatch_runtime()
    status = runtime_patch.apply_runtime_patch()

    assert status["patched"] is True
    assert status["shadow_dom_disabled"] is True
    assert FakeRuntimeCore._shadow_dom_script() == "(() => {})();"

    restored = runtime_patch.unpatch_runtime()
    assert restored["patched"] is False
    assert FakeRuntimeCore._shadow_dom_script() == "original"


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False
