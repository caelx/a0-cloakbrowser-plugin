#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import quote

try:
    from runtime_paths import bootstrap
except ImportError:
    from ci.runtime_paths import bootstrap


class FakeContext:
    def __init__(self, context_id: str):
        self.id = context_id
        self.log = Log()
        self._data: dict[str, object] = {}

    def get_data(self, key: str, default=None):
        return self._data.get(key, default)

    def set_data(self, key: str, value) -> None:
        self._data[key] = value


class FakeAgent:
    def __init__(self, context_id: str):
        self.context = FakeContext(context_id)
        self.config = FakeConfig()
        self.agent_name = "CI"


class FakeConfig:
    profile = "default"


class Log:
    def log(self, **kwargs):
        return kwargs


async def main() -> int:
    bootstrap()
    from plugins._browser.helpers import runtime as browser_runtime
    from plugins._browser.tools.browser import Browser

    agent = FakeAgent("cloakbrowser-ci")
    tool = Browser(agent=agent, name="browser", method=None, args={}, message="", loop_data=None)
    results = []
    upload = Path("/tmp/cloakbrowser-upload.txt")
    upload.write_text("upload", encoding="utf-8")
    markup = """
    <html>
      <head><title>CloakBrowser CI</title></head>
      <body>
        <form id=f onsubmit="window.submitted=1; return false">
          <a id=a href="#next">link</a>
          <button id=b type=button onclick="window.clicked=(window.clicked||0)+1">Click</button>
          <input id=t name=t>
          <input id=c type=checkbox>
          <select id=s><option value=a>A</option><option value=b>B</option></select>
          <input id=u type=file>
          <div id=e contenteditable=true>edit</div>
          <button id=d type=button draggable=true style="width:60px;height:30px;background:#ddd">drag</button>
          <button id=target type=button style="width:80px;height:40px;background:#bbb">target</button>
          <button id=submit type=submit>Submit</button>
        </form>
        <script>window.submitted=0;</script>
      </body>
    </html>
    """
    html = "data:text/html;charset=utf-8," + quote(markup)

    async def call(**kwargs):
        response = await tool.execute(**kwargs)
        results.append(
            {"call": kwargs, "message": response.message, "break_loop": response.break_loop}
        )
        if response.message.startswith("Browser ") and " failed:" in response.message:
            Path("artifacts").mkdir(exist_ok=True)
            Path("artifacts/browser-tool-results.json").write_text(
                json.dumps(results, indent=2) + "\n", encoding="utf-8"
            )
            raise AssertionError(response.message)
        return response

    async def resolve_refs(*element_ids: str) -> dict[str, str]:
        content_response = await call(
            action="content", selectors=[f"#{element_id}" for element_id in element_ids]
        )
        refs: dict[str, str] = {}
        try:
            content = json.loads(content_response.message)
        except json.JSONDecodeError:
            content = {}
        for element_id in element_ids:
            selector_content = str(content.get(f"#{element_id}") or "")
            match = re.search(r"\[[^\]]*?(\d+)\]", selector_content)
            if match:
                refs[element_id] = match.group(1)
        for candidate in refs.values():
            response = await tool.execute(action="detail", ref=candidate)
            if response.message.startswith("Browser ") and " failed:" in response.message:
                continue
            try:
                detail = json.loads(response.message)
            except json.JSONDecodeError:
                continue
            state = detail.get("state") or {}
            dom = detail.get("dom") or ""
            found_id = state.get("id") or ""
            if not found_id and isinstance(dom, str):
                match = re.search(r'\bid=["\\\']?([A-Za-z0-9_-]+)', dom)
                found_id = match.group(1) if match else ""
            if found_id in element_ids and not refs.get(found_id):
                refs[found_id] = str(detail.get("referenceId") or candidate)
        if len(refs) == len(element_ids):
            return refs
        missing = sorted(set(element_ids) - set(refs))
        Path("artifacts").mkdir(exist_ok=True)
        Path("artifacts/browser-tool-results.json").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8"
        )
        raise AssertionError(f"Missing Browser refs for: {missing}; resolved={refs}")

    await call(action="open", url=html)
    await call(action="state")
    await call(action="list")
    refs = await resolve_refs("a", "b", "t", "c", "s", "u", "d", "target", "submit")

    calls = [
        {"action": "detail", "ref": refs["a"]},
        {"action": "click", "ref": refs["b"]},
        {"action": "type", "ref": refs["t"], "text": "abc"},
        {"action": "submit", "ref": refs["submit"]},
        {"action": "type_submit", "ref": refs["t"], "text": "xyz"},
        {"action": "scroll", "ref": refs["d"]},
        {"action": "evaluate", "script": "({width: window.innerWidth, clicked: window.clicked})"},
        {"action": "key_chord", "keys": ["Control", "A"]},
        {"action": "hover", "ref": refs["b"]},
        {"action": "double_click", "ref": refs["b"]},
        {"action": "right_click", "ref": refs["b"]},
        {"action": "drag", "ref": refs["d"], "target_ref": refs["target"]},
        {"action": "wheel", "x": 200, "y": 200, "delta_y": 100},
        {"action": "keyboard", "key": "Escape"},
        {"action": "clipboard", "event_type": "paste", "text": "clip"},
        {"action": "set_viewport", "width": 1440, "height": 960},
        {"action": "select_option", "ref": refs["s"], "value": "b"},
        {"action": "set_checked", "ref": refs["c"], "checked": True},
        {"action": "upload_file", "ref": refs["u"], "path": str(upload)},
        {"action": "mouse", "event_type": "move", "x": 10, "y": 10},
        {
            "action": "multi",
            "calls": [{"action": "state"}, {"action": "evaluate", "script": "window.innerWidth"}],
        },
        {"action": "screenshot"},
        {
            "action": "navigate",
            "url": "data:text/html;charset=utf-8," + quote("<title>next</title>"),
        },
        {"action": "back"},
        {"action": "forward"},
        {"action": "reload"},
        {"action": "set_active"},
        {"action": "close"},
        {"action": "open", "url": "about:blank"},
        {"action": "close_all"},
    ]
    last_response = None
    for kwargs in calls:
        last_response = await call(**kwargs)
        if kwargs.get("action") == "type":
            value_response = await call(
                action="evaluate", script="document.querySelector('#t').value"
            )
            assert json.loads(value_response.message)["result"] == "abc"
        if kwargs.get("action") in {"type_submit", "typesubmit"}:
            value_response = await call(
                action="evaluate", script="document.querySelector('#t').value"
            )
            value = json.loads(value_response.message)["result"]
            assert value in {"xyz", "abcxyz"}
    close_all_result = json.loads(last_response.message)
    assert close_all_result == {
        "browsers": [],
        "last_interacted_browser_id": None,
    }, close_all_result
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/browser-tool-results.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    runtime = await browser_runtime.get_runtime(agent.context.id, create=False)
    if runtime:
        await runtime.call("close", delete_profile=False)
        runtime._closed = True
        with browser_runtime._runtime_lock:
            browser_runtime._runtimes.pop(agent.context.id, None)
    await asyncio.sleep(0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
