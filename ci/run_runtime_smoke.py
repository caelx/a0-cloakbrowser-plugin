#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path


FORBIDDEN_ARGS = ("--disable-gpu", "--disable-extensions", "--enable-automation")
REQUIRED_ARGS = (
    "--fingerprint",
    "--fingerprint-noise=false",
    "--fingerprint-screen-width=1920",
    "--fingerprint-screen-height=1080",
)


async def main() -> int:
    sys.path.insert(0, "/git/agent-zero")
    from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch
    from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright, status
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore

    apply_runtime_patch()
    patch_playwright()
    core = _BrowserRuntimeCore("cloakbrowser-runtime-ci")
    result = {"profile_dir": str(core.profile_dir)}
    try:
        profile_root = Path("/git/agent-zero/tmp/browser/sessions")
        assert Path(core.profile_dir).resolve().is_relative_to(profile_root.resolve())
        await core.open("data:text/html,<title>runtime</title>")
        eval_result = await core.evaluate(
            next(iter(core.pages)),
            """({
              innerWidth: window.innerWidth,
              innerHeight: window.innerHeight,
              screenWidth: screen.width,
              screenHeight: screen.height
            })""",
        )
        result["pages"] = len(core.pages)
        result["shim"] = status()
        result["dimensions"] = eval_result.get("result", {})
        result["command_lines"] = browser_command_lines(str(core.profile_dir))
        assert result["command_lines"], "No browser process found for runtime profile"
        last_launch = result["shim"]["last_launch"]
        assert last_launch.get("patched") is True
        assert "cloakbrowser" in last_launch.get("binary", "").lower()
        assert last_launch.get("headless") is False
        final_args = last_launch.get("final_args", [])
        for forbidden in FORBIDDEN_ARGS:
            assert forbidden not in final_args
        assert not any(arg.startswith("--disable-extensions=") for arg in final_args)
        for required in REQUIRED_ARGS:
            assert any(
                arg == required or arg.startswith(required + "=") for arg in final_args
            ), required
        assert any(arg.startswith("--load-extension=") for arg in final_args)
        for arg in final_args:
            if not (
                arg.startswith("--load-extension=")
                or arg.startswith("--disable-extensions-except=")
            ):
                continue
            paths = arg.split("=", 1)[1].split(",")
            assert len(paths) == len(set(paths)), arg
        main_commands = [
            line for line in result["command_lines"] if " --type=" not in line and "chrome" in line
        ]
        assert main_commands, "No main browser process command line found"
        result["main_command_line"] = main_commands[0]
        assert "--enable-automation" not in main_commands[0], main_commands[0]
        assert main_commands[0].count("--no-sandbox") == 1, main_commands[0]
        assert main_commands[0].count("--disable-dev-shm-usage") == 1, main_commands[0]
        assert result["dimensions"] == {
            "innerWidth": 1920,
            "innerHeight": 1080,
            "screenWidth": 1920,
            "screenHeight": 1080,
        }
        await core.close(delete_profile=False)
        result["remaining_command_lines"] = wait_for_process_cleanup(str(core.profile_dir))
        assert not result["remaining_command_lines"], "Browser process remained after close"
    finally:
        Path("artifacts").mkdir(exist_ok=True)
        Path("artifacts/runtime-smoke-results.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    return 0


def browser_command_lines(profile_dir: str) -> list[str]:
    lines: list[str] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            raw = (proc / "cmdline").read_bytes()
        except OSError:
            continue
        text = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
        if profile_dir in text:
            lines.append(text)
    return lines


def wait_for_process_cleanup(profile_dir: str) -> list[str]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        lines = browser_command_lines(profile_dir)
        if not lines:
            return []
        time.sleep(0.25)
    return browser_command_lines(profile_dir)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
