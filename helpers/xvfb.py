from __future__ import annotations

import os
import signal
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

    attempts: list[dict[str, Any]] = []
    for display in candidate_displays(preferred):
        if display_usable(display):
            os.environ["DISPLAY"] = display
            manifest["display"] = display
            return {"ok": True, "display": display, "reused": True, "attempts": attempts}
        if display_socket_exists(display):
            attempts.append({"display": display, "ok": False, "reason": "display socket exists but is unusable"})
            continue
        start_result = start_xvfb(
            display,
            runtime["display_width"],
            runtime["display_height"],
            runtime["display_depth"],
        )
        attempts.append(start_result)
        if start_result["ok"]:
            os.environ["DISPLAY"] = display
            manifest["display"] = display
            manifest["xvfb"] = {**start_result, "attempts": list(attempts)}
            return start_result
    return {
        "ok": False,
        "display": preferred,
        "reason": "no candidate display became usable",
        "attempts": attempts,
    }


def display_usable(display: str) -> bool:
    if not display:
        return False
    env = os.environ.copy()
    env["DISPLAY"] = display
    if shutil.which("xdpyinfo"):
        result = subprocess.run(["xdpyinfo"], env=env, check=False, capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    return Path(f"/tmp/.X11-unix/X{display.lstrip(':').split('.')[0]}").exists()


def display_socket_exists(display: str) -> bool:
    if not display:
        return False
    return Path(f"/tmp/.X11-unix/X{display.lstrip(':').split('.')[0]}").exists()


def candidate_displays(preferred: str | None) -> list[str]:
    candidates: list[str] = []
    for display in [preferred or ":99", ":99", ":98", ":100", ":97", ":101"]:
        if display and display not in candidates:
            candidates.append(display)
    return candidates


def start_xvfb(display: str, width: int, height: int, depth: int) -> dict[str, Any]:
    if not shutil.which("Xvfb"):
        return {"ok": False, "display": display, "reason": "Xvfb not installed"}
    supervisor = start_xvfb_supervisor(display, width, height, depth)
    if supervisor["attempted"]:
        if supervisor["ok"]:
            return supervisor
        direct = start_xvfb_process(display, width, height, depth)
        direct["supervisor_attempt"] = supervisor
        return direct

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


def remove_direct_xvfb_if_owned(manifest: dict[str, Any]) -> dict[str, Any]:
    recorded = manifest.get("xvfb", {})
    if recorded.get("managed_by") != "cloakbrowser":
        return {"removed": False, "reason": "not cloakbrowser-managed direct Xvfb"}
    pid = int(recorded.get("pid") or 0)
    display = str(recorded.get("display") or "")
    if not pid:
        return {"removed": False, "reason": "no recorded pid"}
    if not _pid_matches_xvfb(pid, display):
        return {"removed": False, "pid": pid, "display": display, "reason": "pid did not match recorded Xvfb"}
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return {"removed": True, "pid": pid, "display": display, "already_exited": True}
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not _pid_exists(pid):
            return {"removed": True, "pid": pid, "display": display, "signal": "TERM"}
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return {"removed": True, "pid": pid, "display": display, "signal": "TERM"}
    return {"removed": True, "pid": pid, "display": display, "signal": "KILL"}


def _pid_matches_xvfb(pid: int, display: str) -> bool:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False
    cmdline = raw.replace(b"\0", b" ").decode("utf-8", "replace")
    return "Xvfb" in cmdline and bool(display) and display in cmdline


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
