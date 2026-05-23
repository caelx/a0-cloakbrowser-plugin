from types import SimpleNamespace

import hooks


def test_uninstall_returns_helper_result(monkeypatch):
    helper = SimpleNamespace(uninstall=lambda **_kwargs: {"ok": False})
    monkeypatch.setattr(hooks, "_plugin_import", lambda name: helper)

    assert hooks.uninstall() is False
