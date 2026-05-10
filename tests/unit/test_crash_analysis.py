from ci.analyze_chromium_crashes import infer_root_cause


def test_infer_root_cause_identifies_shared_memory_oom_signature():
    result = infer_root_cause(
        [
            {
                "crash_reason": "SIGTRAP",
                "has_oom_frame": True,
                "has_shared_image_frame": True,
                "has_discardable_memory_frame": False,
            },
            {
                "crash_reason": "SIGTRAP",
                "has_oom_frame": True,
                "has_shared_image_frame": False,
                "has_discardable_memory_frame": True,
            },
        ]
    )

    assert "partition_alloc out-of-memory" in result
