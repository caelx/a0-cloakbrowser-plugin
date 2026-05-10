#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PAGE_COUNT = 21


async def main() -> int:
    sys.path.insert(0, "/git/agent-zero")
    from plugins._browser.helpers.runtime import _BrowserRuntimeCore
    from usr.plugins.cloakbrowser.helpers.playwright_shim import patch_playwright, status
    from usr.plugins.cloakbrowser.helpers.runtime_patch import apply_runtime_patch

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    apply_runtime_patch()
    patch_playwright()
    core = _BrowserRuntimeCore("cloakbrowser-heavy-browsing-ci")
    core_closed = False
    result: dict[str, object] = {
        "navigations": [],
        "profile_dir": str(core.profile_dir),
        "errors": [],
    }
    artifacts = Path("artifacts")
    screenshots = artifacts / "heavy-browsing"
    artifacts.mkdir(exist_ok=True)
    screenshots.mkdir(exist_ok=True)

    try:
        start_url = f"http://127.0.0.1:{server.server_port}/page/0"
        opened = await core.open(start_url)
        browser_id = opened["id"]
        page = core.pages[browser_id].page

        for step in range(1, PAGE_COUNT):
            async with page.expect_navigation(wait_until="domcontentloaded"):
                await page.click("#next")
            title = await page.title()
            body = await page.locator("body").inner_text(timeout=5000)
            screenshot_path = screenshots / f"page-{step:02d}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            command_lines = browser_command_lines(str(core.profile_dir))
            assert command_lines, f"browser process missing after navigation {step}"
            expected = f"CloakBrowser heavy page {step}"
            assert title == expected, f"unexpected title after navigation {step}: {title}"
            assert f"Page {step}" in body, f"missing body marker after navigation {step}"
            result["navigations"].append(
                {
                    "step": step,
                    "url": page.url,
                    "title": title,
                    "body_marker": f"Page {step}",
                    "screenshot": str(screenshot_path),
                    "browser_process_count": len(command_lines),
                }
            )

        alive = await page.evaluate("document.readyState")
        assert alive in {"interactive", "complete"}
        result["post_navigation_action"] = {
            "ready_state": alive,
            "title": await page.title(),
        }
        result["shim"] = status()
        result["command_lines_before_close"] = browser_command_lines(str(core.profile_dir))
        assert len(result["navigations"]) == 20
        await core.close(delete_profile=False)
        core_closed = True
        result["remaining_command_lines"] = wait_for_process_cleanup(str(core.profile_dir))
        assert not result["remaining_command_lines"], "browser process remained after close"
    except Exception as exc:
        result["errors"].append(repr(exc))
        raise
    finally:
        if not core_closed:
            try:
                await core.close(delete_profile=False)
            except Exception as exc:
                result["errors"].append(f"cleanup failed: {exc!r}")
        server.shutdown()
        server.server_close()
        Path("artifacts/heavy-browsing-results.json").write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            number = int(path.rsplit("/", 1)[1])
        except (IndexError, ValueError):
            number = 0
        number = max(0, min(PAGE_COUNT - 1, number))
        next_number = min(PAGE_COUNT - 1, number + 1)
        body = f"""<!doctype html>
<html>
  <head><title>CloakBrowser heavy page {number}</title></head>
  <body>
    <main>
      <h1>Page {number}</h1>
      <p>Heavy browsing smoke page {number} of {PAGE_COUNT - 1}.</p>
      <a id="next" href="/page/{next_number}">Next page</a>
    </main>
  </body>
</html>
"""
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format, *args):
        return


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
