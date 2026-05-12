from helpers import config
from helpers.config import normalize_config, plugin_dir, redacted_config


def test_normalize_config_defaults_and_invalid_values(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    cfg = normalize_config(
        {
            "runtime": {"viewport_width": "bad", "display": "98"},
            "humanization": {"human_preset": "unknown"},
            "network_location": {"webrtc_ip_mode": "bad"},
            "advanced": {"extra_args": "--foo\n\n--bar"},
        }
    )

    assert cfg["runtime"]["display_width"] == 1440
    assert cfg["runtime"]["display_height"] == 960
    assert cfg["runtime"]["viewport_width"] == 1440
    assert cfg["runtime"]["viewport_height"] == 960
    assert cfg["identity"]["fingerprint_screen_width"] == 1440
    assert cfg["identity"]["fingerprint_screen_height"] == 960
    assert cfg["runtime"]["display"] == ":98"
    assert cfg["humanization"]["human_preset"] == "default"
    assert cfg["network_location"]["geoip"] is True
    assert cfg["network_location"]["timezone"] == ""
    assert cfg["network_location"]["locale"] == ""
    assert cfg["network_location"]["webrtc_ip_mode"] == "auto"
    assert cfg["identity"]["fingerprint_platform"] == "Windows"
    assert cfg["extensions"]["enable_i_still_dont_care_about_cookies"] is False
    assert "install_i_still_dont_care_about_cookies" not in cfg["extensions"]
    assert "update_i_still_dont_care_about_cookies_on_setup" not in cfg["extensions"]
    assert cfg["bypass_paywalls_clean"]["opt_in_setcookie"] is True
    assert cfg["bypass_paywalls_clean"]["opt_in_custom_sites"] is True
    assert cfg["bypass_paywalls_clean"]["opt_in_update"] is True
    assert "preserve_headed_placeholder_page" not in cfg["advanced"]
    assert cfg["advanced"]["extra_args"] == ["--foo", "--bar"]


def test_explicit_timezone_locale_override_geoip_resolution():
    cfg = normalize_config(
        {
            "network_location": {
                "timezone": "America/Chicago",
                "locale": "en-US",
            },
        }
    )

    assert cfg["network_location"]["geoip"] is True
    assert cfg["network_location"]["timezone"] == "America/Chicago"
    assert cfg["network_location"]["locale"] == "en-US"


def test_geoip_disabled_uses_local_timezone_locale(monkeypatch):
    monkeypatch.setenv("TZ", "America/Denver")
    monkeypatch.setenv("LANG", "en_US.UTF-8")

    cfg = normalize_config({"network_location": {"geoip": False}})

    assert cfg["network_location"]["geoip"] is False
    assert cfg["network_location"]["timezone"] == "America/Denver"
    assert cfg["network_location"]["locale"] == "en-US"


def test_redacted_config_hides_proxy_credentials():
    cfg = redacted_config({"network_location": {"proxy": "http://user:pass@example.com:8080"}})

    assert cfg["network_location"]["proxy"] == "http://<redacted>@example.com:8080"


def test_plugin_dir_prefers_upstream_plugin_helper(monkeypatch, tmp_path):
    upstream = tmp_path / "git" / "agent-zero"
    plugin = upstream / "usr" / "plugins" / "cloakbrowser"
    plugin.mkdir(parents=True)
    (upstream / "plugins" / "_browser").mkdir(parents=True)
    (upstream / "helpers").mkdir()
    (upstream / "helpers" / "__init__.py").write_text("", encoding="utf-8")
    (upstream / "helpers" / "plugins.py").write_text(
        "def find_plugin_dir(name):\n    return " + repr(str(plugin)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "AGENT_ZERO_FALLBACK_DIR", upstream)

    assert plugin_dir() == plugin
