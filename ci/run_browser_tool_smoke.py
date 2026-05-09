#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace


async def main() -> int:
    sys.path.insert(0, "/git/agent-zero")
    from usr.plugins.cloakbrowser.tools.browser import Browser

    class Log:
        def log(self, **kwargs):
            return kwargs

    agent = SimpleNamespace(context=SimpleNamespace(id="cloakbrowser-ci", log=Log()), agent_name="CI")
    tool = Browser(agent=agent, name="browser", method=None, args={})
    results = []
    upload = Path("/tmp/cloakbrowser-upload.txt")
    upload.write_text("upload", encoding="utf-8")
    html = """data:text/html,
    <title>CloakBrowser CI</title>
    <form id=f onsubmit="window.submitted=1; return false">
      <a id=a href="#next">link</a>
      <button id=b type=button onclick="window.clicked=(window.clicked||0)+1">Click</button>
      <input id=t name=t>
      <input id=c type=checkbox>
      <select id=s><option value=a>A</option><option value=b>B</option></select>
      <input id=u type=file>
      <div id=e contenteditable=true>edit</div>
      <div id=d draggable=true style="width:60px;height:30px;background:#ddd">drag</div>
      <div id=target style="width:80px;height:40px;background:#bbb">target</div>
      <button id=submit type=submit>Submit</button>
    </form>
    <script>window.submitted=0;</script>
    """
    calls = [
        {"action": "open", "url": html},
        {"action": "state"},
        {"action": "list"},
        {"action": "content"},
        {"action": "detail", "ref": 1},
        {"action": "click", "ref": 2},
        {"action": "type", "ref": 3, "text": "abc"},
        {"action": "submit", "ref": 10},
        {"action": "type_submit", "ref": 3, "text": "xyz"},
        {"action": "scroll", "ref": 8},
        {"action": "evaluate", "script": "({width: window.innerWidth, clicked: window.clicked})"},
        {"action": "key_chord", "keys": ["Control", "A"]},
        {"action": "hover", "ref": 2},
        {"action": "double_click", "ref": 2},
        {"action": "right_click", "ref": 2},
        {"action": "drag", "ref": 8, "target_ref": 9},
        {"action": "wheel", "x": 200, "y": 200, "delta_y": 100},
        {"action": "keyboard", "key": "Escape"},
        {"action": "clipboard", "event_type": "paste", "text": "clip"},
        {"action": "set_viewport", "width": 1920, "height": 1080},
        {"action": "select_option", "ref": 5, "value": "b"},
        {"action": "set_checked", "ref": 4, "checked": True},
        {"action": "upload_file", "ref": 6, "path": str(upload)},
        {"action": "mouse", "event_type": "move", "x": 10, "y": 10},
        {"action": "multi", "calls": [{"action": "state"}, {"action": "evaluate", "script": "window.innerWidth"}]},
        {"action": "screenshot"},
        {"action": "navigate", "url": "data:text/html,<title>next</title>"},
        {"action": "back"},
        {"action": "forward"},
        {"action": "reload"},
        {"action": "set_active"},
        {"action": "close"},
        {"action": "open", "url": "about:blank"},
        {"action": "close_all"},
    ]
    for kwargs in calls:
        response = await tool.execute(**kwargs)
        results.append({"call": kwargs, "message": response.message, "break_loop": response.break_loop})
        if response.message.startswith("Browser ") and " failed:" in response.message:
            raise AssertionError(response.message)
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/browser-tool-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
