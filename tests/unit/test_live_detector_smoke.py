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
            {"status": "error", "checks": []},
            {"status": "ok", "checks": [{"status": "failed"}]},
        ]
    )

    assert len(failures) == 2
