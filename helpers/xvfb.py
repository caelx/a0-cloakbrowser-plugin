from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

SUPERVISOR_CONF = Path("/etc/supervisor/conf.d/cloakbrowser_xvfb.conf")


def ensure_display(config: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    runtime = config["runtime"]
    preferred = runtime["display"]
    if runtime["reuse_existing_display"]:
        current = os.environ.get("DISPLAY") or preferred
        if current and display_usable(current):
            os.environ["DISPLAY"] = current
            manifest["display"] = current
            return {"ok": True, "display": current, "reused": True}

    if not runtime["auto_start_xvfb"]:
        return {"ok": False, "display": os.environ.get("DISPLAY", ""), "reason": "auto_start_xvfb disabled"}

    display = preferred if preferred else ":99"
    if display_usable(display):
        os.environ["DISPLAY"] = display
        manifest["display"] = display
        return {"ok": True, "display": display, "reused": True}

    start_result = start_xvfb(display, runtime["display_width"], runtime["display_height"], runtime["display_depth"])
    if start_result["ok"]:
        os.environ["DISPLAY"] = display
        manifest["display"] = display
        manifest["xvfb"] = start_result
    return start_result


def display_usable(display: str) -> bool:
    if not display:
        return False
    env = os.environ.copy()
    env["DISPLAY"] = display
    if shutil.which("xdpyinfo"):
        result = subprocess.run(["xdpyinfo"], env=env, check=False, capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    return Path(f"/tmp/.X11-unix/X{display.lstrip(':').split('.')[0]}").exists()


def start_xvfb(display: str, width: int, height: int, depth: int) -> dict[str, Any]:
    if not shutil.which("Xvfb"):
        return {"ok": False, "display": display, "reason": "Xvfb not installed"}
    supervisor = start_xvfb_supervisor(display, width, height, depth)
    if supervisor["attempted"]:
        if supervisor["ok"]:
            return supervisor
        if supervisor.get("supervisor_present"):
            return supervisor

    return start_xvfb_process(display, width, height, depth)


def start_xvfb_supervisor(display: str, width: int, height: int, depth: int) -> dict[str, Any]:
    supervisorctl = shutil.which("supervisorctl")
    supervisor_present = bool(supervisorctl and Path("/etc/supervisor/conf.d").is_dir())
    if not supervisor_present:
        return {"attempted": False, "ok": False, "supervisor_present": False}
    command = f"/usr/bin/Xvfb {display} -screen 0 {width}x{height}x{depth} -nolisten tcp"
    SUPERVISOR_CONF.parent.mkdir(parents=True, exist_ok=True)
    SUPERVISOR_CONF.write_text(
        "\n".join(
            [
                "[program:cloakbrowser_xvfb]",
                f"command={command}",
                "autostart=true",
                "autorestart=true",
                "priority=90",
                "stdout_logfile=/tmp/cloakbrowser-xvfb.log",
                "stderr_logfile=/tmp/cloakbrowser-xvfb.err.log",
                "stopsignal=TERM",
                "",
            ]
        ),
        encoding="utf-8",
    )
    reread = subprocess.run([supervisorctl, "reread"], check=False, capture_output=True, text=True)
    update = subprocess.run([supervisorctl, "update"], check=False, capture_output=True, text=True)
    start = subprocess.run([supervisorctl, "start", "cloakbrowser_xvfb"], check=False, capture_output=True, text=True)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if display_usable(display):
            return {
                "attempted": True,
                "ok": True,
                "display": display,
                "managed_by": "supervisor",
                "supervisor_present": True,
                "supervisor_config": str(SUPERVISOR_CONF),
                "command": command,
            }
        time.sleep(0.25)
    return {
        "attempted": True,
        "ok": False,
        "display": display,
        "managed_by": "supervisor",
        "supervisor_present": True,
        "supervisor_config": str(SUPERVISOR_CONF),
        "reason": "supervisor-managed display did not become usable",
        "supervisor_output": {
            "reread": (reread.stdout + reread.stderr)[-1000:],
            "update": (update.stdout + update.stderr)[-1000:],
            "start": (start.stdout + start.stderr)[-1000:],
        },
    }


def start_xvfb_process(display: str, width: int, height: int, depth: int) -> dict[str, Any]:
    cmd = ["Xvfb", display, "-screen", "0", f"{width}x{height}x{depth}", "-nolisten", "tcp"]
    log_path = Path("/tmp/cloakbrowser-xvfb.log")
    with log_path.open("ab") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return {"ok": False, "display": display, "pid": proc.pid, "reason": "Xvfb exited"}
        if display_usable(display):
            return {
                "ok": True,
                "display": display,
                "pid": proc.pid,
                "command": cmd,
                "managed_by": "cloakbrowser",
                "log": str(log_path),
            }
        time.sleep(0.25)
    return {"ok": False, "display": display, "pid": proc.pid, "reason": "display did not become usable"}


def remove_supervisor_config_if_owned(manifest: dict[str, Any]) -> dict[str, Any]:
    recorded = manifest.get("xvfb", {})
    if recorded.get("supervisor_config") and SUPERVISOR_CONF.exists():
        SUPERVISOR_CONF.unlink()
        return {"removed": str(SUPERVISOR_CONF)}
    return {"removed": ""}
