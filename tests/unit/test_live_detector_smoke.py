from ci import run_live_detector_smoke as smoke


def test_selected_targets_defaults_to_all_live_targets():
    assert smoke.selected_targets("all") == list(smoke.LIVE_TARGETS)
    assert "audio-fp" not in {target.name for target in smoke.LIVE_TARGETS}
    assert "audio-fp" in {target.name for target in smoke.SKIPPED_TARGETS}
    assert {"google-recaptcha-v3", "2captcha-recaptcha-v3", "turnstile"} <= {
        target.name for target in smoke.LIVE_TARGETS
    }


def test_selected_targets_accepts_comma_or_space_separated_names():
    targets = smoke.selected_targets("sannysoft,httpbin-ip browserleaks-js")

    assert [target.name for target in targets] == ["sannysoft", "httpbin-ip", "browserleaks-js"]


def test_extract_json_object_from_page_text():
    assert smoke.extract_json_object('prefix {"origin": "127.0.0.1"} suffix') == {
        "origin": "127.0.0.1"
    }


def test_live_failures_reports_errors_and_failed_checks():
    failures = smoke.live_failures(
        [
            {"status": "ok", "checks": [{"status": "passed"}]},
            {"status": "skipped", "checks": []},
            {"status": "error", "checks": []},
            {"status": "ok", "checks": [{"status": "failed"}]},
        ]
    )

    assert len(failures) == 2


def test_target_checks_include_infrastructure_checks(tmp_path):
    screenshot = tmp_path / "page.png"
    screenshot.write_bytes(b"png")
    checks = smoke.target_checks(
        smoke.LiveTarget("example", "detection", "https://example.com"),
        {
            "state": {"url": "https://example.com", "title": "Example"},
            "text": "",
            "screenshot": str(screenshot),
            "environment": {
                "webdriver": False,
                "userAgent": "Chrome",
                "innerWidth": 1440,
                "innerHeight": 960,
                "screenWidth": 1440,
                "screenHeight": 960,
            },
        },
    )

    by_name = {item["name"]: item["status"] for item in checks}
    assert by_name["page loaded"] == "passed"
    assert by_name["page has title or body text"] == "passed"
    assert by_name["screenshot was created"] == "passed"


def test_httpbin_5xx_is_classified_as_unavailable_target():
    reason = smoke.unavailable_target_reason(
        smoke.LiveTarget("httpbin-ip", "headers-tls", "https://httpbin.org/ip"),
        {
            "state": {"title": "502 Bad Gateway"},
            "text": "502 Bad Gateway",
        },
    )

    assert reason == "httpbin returned a transient 5xx response"


def test_non_httpbin_5xx_is_not_classified_as_unavailable_target():
    reason = smoke.unavailable_target_reason(
        smoke.LiveTarget("sannysoft", "detection", "https://bot.sannysoft.com/"),
        {
            "state": {"title": "502 Bad Gateway"},
            "text": "502 Bad Gateway",
        },
    )

    assert reason == ""
