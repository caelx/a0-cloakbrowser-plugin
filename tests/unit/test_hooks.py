import sys
from types import ModuleType, SimpleNamespace

import hooks


def test_uninstall_returns_helper_result(monkeypatch):
    helper = SimpleNamespace(uninstall=lambda **_kwargs: {"ok": False})
    plugin_imports = ModuleType("plugin_imports")
    plugin_imports.plugin_import = lambda name: helper if name == "helpers.uninstall" else None
    monkeypatch.setitem(sys.modules, "plugin_imports", plugin_imports)

    assert hooks.uninstall() is False
