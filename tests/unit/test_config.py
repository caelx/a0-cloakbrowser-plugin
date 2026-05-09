from helpers.config import normalize_config, redacted_config


def test_normalize_config_defaults_and_invalid_values():
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
    assert cfg["network_location"]["webrtc_ip_mode"] == "auto"
    assert cfg["advanced"]["extra_args"] == ["--foo", "--bar"]


def test_redacted_config_hides_proxy_credentials():
    cfg = redacted_config({"network_location": {"proxy": "http://user:pass@example.com:8080"}})

    assert cfg["network_location"]["proxy"] == "http://<redacted>@example.com:8080"
