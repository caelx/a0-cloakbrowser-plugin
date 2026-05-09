import json

from helpers import xvfb


def test_ensure_display_allocates_alternate_when_preferred_socket_unusable(monkeypatch):
    manifest = {}
    starts = []
    monkeypatch.setattr(xvfb, "display_usable", lambda display: False)
    monkeypatch.setattr(xvfb, "display_socket_exists", lambda display: display == ":99")

    def fake_start(display, width, height, depth):
        starts.append(display)
        return {
            "ok": display == ":98",
            "display": display,
            "managed_by": "cloakbrowser",
            "command": ["Xvfb", display],
        }

    monkeypatch.setattr(xvfb, "start_xvfb", fake_start)

    result = xvfb.ensure_display(
        {
            "runtime": {
                "display": ":99",
                "reuse_existing_display": False,
                "auto_start_xvfb": True,
                "display_width": 1920,
                "display_height": 1080,
                "display_depth": 24,
            }
        },
        manifest,
    )

    assert result["ok"] is True
    assert result["display"] == ":98"
    assert starts == [":98"]
    assert manifest["display"] == ":98"
    assert manifest["xvfb"]["attempts"][0]["display"] == ":99"
    json.dumps(manifest)
