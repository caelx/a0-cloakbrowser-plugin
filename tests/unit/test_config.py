from helpers.config import normalize_config, redacted_config


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

    assert cfg["runtime"]["viewport_width"] == 1920
    assert cfg["runtime"]["display"] == ":98"
    assert cfg["humanization"]["human_preset"] == "default"
    assert cfg["network_location"]["geoip"] is False
    assert cfg["network_location"]["timezone"] == "America/New_York"
    assert cfg["network_location"]["locale"] == "en-US"
    assert cfg["network_location"]["webrtc_ip_mode"] == "disabled"
    assert cfg["identity"]["fingerprint_platform"] == "Windows"
    assert cfg["extensions"]["update_i_still_dont_care_about_cookies_on_setup"] is True
    assert cfg["advanced"]["extra_args"] == ["--foo", "--bar"]


def test_redacted_config_hides_proxy_credentials():
    cfg = redacted_config({"network_location": {"proxy": "http://user:pass@example.com:8080"}})

    assert cfg["network_location"]["proxy"] == "http://<redacted>@example.com:8080"
