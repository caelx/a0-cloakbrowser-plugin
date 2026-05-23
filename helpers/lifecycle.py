from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any


def reconcile_after_setup(config: dict[str, Any], source_patch: dict[str, Any]) -> dict[str, Any]:
    matched = _managed_browser_processes(config)
    source_changed = bool(source_patch.get("applied")) and not bool(
        source_patch.get("already_patched")
    )
    stock_playwright_detected = any(
        bool(proc.get("stock_playwright_browser")) for proc in matched
    )
    restart_needed = source_changed or stock_playwright_detected
    if restart_needed:
        stopped = stop_managed_browser_processes(config, matches=matched)
    else:
        stopped = {
            "matched": matched,
            "terminated": [],
            "killed": [],
            "failed": [],
            "skipped": True,
            "reason": "live_runtime_already_current",
        }
    _log_event(
        "reconcile_after_setup",
        {
            "source_changed": source_changed,
            "stock_playwright_detected": stock_playwright_detected,
            "restart_needed": restart_needed,
            "matched_pids": [proc.get("pid") for proc in matched],
        },
    )
    agent_zero_restart = restart_agent_zero_if_needed(restart_needed)
    return {
        "browser_processes_stopped": stopped,
        "agent_zero_restart": agent_zero_restart,
        "restart_reason": _restart_reason(
            source_changed=source_changed,
            stock_playwright_detected=stock_playwright_detected,
        ),
        "restart_required": bool(agent_zero_restart.get("restart_required")),
    }


def inspect_live_browser_state(config: dict[str, Any]) -> dict[str, Any]:
    matched = _managed_browser_processes(config)
    stock = [proc for proc in matched if proc.get("stock_playwright_browser")]
    return {
        "matched": matched,
        "stock_playwright_browser_detected": bool(stock),
        "stock_playwright_browser_pids": [int(proc["pid"]) for proc in stock],
        "restart_required": bool(stock),
        "restart_reason": "stock_playwright_browser_detected" if stock else "not_required",
    }


def stop_managed_browser_processes(
    config: dict[str, Any],
    *,
    proc_root: Path = Path("/proc"),
    timeout: float = 3.0,
    matches: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    matches = matches if matches is not None else _managed_browser_processes(config, proc_root=proc_root)
    terminated: list[int] = []
    killed: list[int] = []
    failed: list[dict[str, Any]] = []

    for proc in matches:
        pid = int(proc["pid"])
        try:
            os.kill(pid, signal.SIGTERM)
            terminated.append(pid)
        except ProcessLookupError:
            continue
        except PermissionError as exc:
            failed.append({"pid": pid, "signal": "TERM", "error": str(exc)})

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        live = [proc for proc in matches if _pid_alive(int(proc["pid"]))]
        if not live:
            break
        time.sleep(0.1)

    for proc in matches:
        pid = int(proc["pid"])
        if not _pid_alive(pid):
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            killed.append(pid)
        except ProcessLookupError:
            continue
        except PermissionError as exc:
            failed.append({"pid": pid, "signal": "KILL", "error": str(exc)})

    return {
        "matched": matches,
        "terminated": terminated,
        "killed": killed,
        "failed": failed,
    }


def restart_agent_zero_if_needed(restart_needed: bool, *, delay_seconds: int = 10) -> dict[str, Any]:
    if not restart_needed:
        return {"needed": False, "restarted": False, "restart_required": False}

    supervisorctl = shutil.which("supervisorctl")
    if not supervisorctl:
        result = {
            "needed": True,
            "restarted": False,
            "restart_required": True,
            "reason": "supervisorctl_not_found",
        }
        _log_event("agent_zero_restart", result)
        return result

    status = subprocess.run(
        [supervisorctl, "status"],
        check=False,
        capture_output=True,
        text=True,
    )
    program = _agent_zero_supervisor_program(status.stdout)
    if not program:
        if status.returncode != 0:
            result = {
                "needed": True,
                "restarted": False,
                "restart_required": True,
                "reason": "supervisor_status_failed",
                "returncode": status.returncode,
                "stderr": status.stderr.strip(),
                "status": status.stdout.strip(),
            }
            _log_event("agent_zero_restart", result)
            return result
        result = {
            "needed": True,
            "restarted": False,
            "restart_required": True,
            "reason": "agent_zero_program_not_found",
            "status": status.stdout.strip(),
        }
        _log_event("agent_zero_restart", result)
        return result

    schedule = _schedule_supervisor_restart(supervisorctl, program, delay_seconds=delay_seconds)
    result = {
        "needed": True,
        "program": program,
        "restarted": False,
        "scheduled": bool(schedule.get("scheduled")),
        "restart_required": not bool(schedule.get("scheduled")),
        "restart_after_execute": bool(schedule.get("scheduled")),
        **schedule,
    }
    _log_event("agent_zero_restart", result)
    return result


def _schedule_supervisor_restart(
    supervisorctl: str,
    program: str,
    *,
    delay_seconds: int,
) -> dict[str, Any]:
    log_path = _lifecycle_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    quoted_log = _sh_quote(str(log_path))
    quoted_supervisorctl = _sh_quote(supervisorctl)
    quoted_program = _sh_quote(program)
    command = (
        f"sleep {int(delay_seconds)}; "
        f"printf '%s\\n' '[cloakbrowser] restarting {program}' >> {quoted_log}; "
        f"({quoted_supervisorctl} restart {quoted_program} "
        f"|| {quoted_supervisorctl} start {quoted_program}) >> {quoted_log} 2>&1; "
        f"{quoted_supervisorctl} status {quoted_program} >> {quoted_log} 2>&1"
    )
    try:
        process = subprocess.Popen(
            ["/bin/sh", "-c", command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception as exc:
        return {"scheduled": False, "reason": "restart_schedule_failed", "error": str(exc)}
    return {
        "scheduled": True,
        "delay_seconds": int(delay_seconds),
        "scheduler_pid": process.pid,
        "log_path": str(log_path),
        "message": f"Agent Zero {program} restart scheduled in {int(delay_seconds)} seconds.",
    }


def _sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _managed_browser_processes(
    config: dict[str, Any],
    *,
    proc_root: Path = Path("/proc"),
) -> list[dict[str, Any]]:
    current_pid = os.getpid()
    matches: list[dict[str, Any]] = []
    entries = (
        sorted(
            (entry for entry in proc_root.iterdir() if entry.name.isdigit()),
            key=lambda entry: int(entry.name),
        )
        if proc_root.exists()
        else ()
    )
    for entry in entries:
        pid = int(entry.name)
        if pid == current_pid:
            continue
        cmdline = _read_cmdline(entry / "cmdline")
        if not cmdline:
            continue
        text = " ".join(cmdline)
        reason = _managed_browser_match_reason(text, config)
        if not reason:
            continue
        matches.append(
            {
                "pid": pid,
                "reason": reason,
                "cmdline": cmdline,
                "stock_playwright_browser": _is_stock_agent_zero_playwright_browser(text),
            }
        )
    return matches


def _managed_browser_match_reason(cmdline: str, config: dict[str, Any]) -> str:
    cache_dir = str(config.get("runtime", {}).get("cloakbrowser_cache_dir") or "").strip()
    tokens = [
        "/a0/tmp/browser/sessions",
        "/git/agent-zero/tmp/browser/sessions",
        "/plugins/_browser/playwright/chromium-cloakbrowser",
        "/usr/plugins/_browser/playwright/chromium-cloakbrowser",
        "/usr/plugins/cloakbrowser/.cloakbrowser/playwright",
        "chromium-cloakbrowser",
    ]
    if cache_dir:
        tokens.append(cache_dir)
    lowered = cmdline.lower()
    for token in tokens:
        if token and token.lower() in lowered:
            return token
    return ""


def _is_stock_agent_zero_playwright_browser(cmdline: str) -> bool:
    lowered = cmdline.lower()
    return (
        "/a0/tmp/playwright/chromium-" in lowered
        and "/a0/tmp/browser/sessions" in lowered
        and "chromium-cloakbrowser" not in lowered
        and "/opt/cloakbrowser" not in lowered
    )


def _read_cmdline(path: Path) -> list[str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _agent_zero_supervisor_program(output: str, *, proc_root: Path = Path("/proc")) -> str:
    candidates: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0]
        lowered = name.lower()
        if "cloakbrowser_xvfb" in lowered:
            continue
        candidates.append(
            {
                "name": name,
                "state": parts[1],
                "pid": _supervisor_line_pid(line),
            }
        )
    for candidate in candidates:
        pid = candidate.get("pid")
        if not pid:
            continue
        if _pid_or_descendant_cmdline_contains(int(pid), proc_root, "/a0/run_ui.py"):
            return str(candidate["name"])
    exact_names = {"agent-zero", "agent_zero", "agentzero", "a0", "a0_server", "a0-server"}
    for candidate in candidates:
        name = str(candidate["name"])
        normalized = name.split(":", 1)[0].lower()
        if normalized in exact_names:
            return name
    for candidate in candidates:
        name = str(candidate["name"])
        normalized = name.split(":", 1)[0].lower()
        if normalized.startswith(("agent-zero", "agent_zero")):
            return name
    return ""


def _supervisor_line_pid(line: str) -> int | None:
    marker = " pid "
    if marker not in line:
        return None
    tail = line.split(marker, 1)[1].strip()
    value = tail.split(",", 1)[0].strip()
    try:
        return int(value)
    except ValueError:
        return None


def _pid_or_descendant_cmdline_contains(pid: int, proc_root: Path, needle: str) -> bool:
    descendants = {pid}
    changed = True
    while changed:
        changed = False
        for entry in proc_root.iterdir() if proc_root.exists() else ():
            if not entry.name.isdigit():
                continue
            child_pid = int(entry.name)
            if child_pid in descendants:
                continue
            parent = _read_ppid(entry / "status")
            if parent in descendants:
                descendants.add(child_pid)
                changed = True
    for candidate in descendants:
        text = " ".join(_read_cmdline(proc_root / str(candidate) / "cmdline"))
        if needle in text:
            return True
    return False


def _read_ppid(path: Path) -> int | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line.startswith("PPid:"):
            continue
        try:
            return int(line.split(":", 1)[1].strip())
        except ValueError:
            return None
    return None


def _restart_reason(*, source_changed: bool, stock_playwright_detected: bool) -> str:
    reasons = []
    if source_changed:
        reasons.append("runtime_source_patch_changed")
    if stock_playwright_detected:
        reasons.append("stock_playwright_browser_detected")
    return ",".join(reasons) if reasons else "not_required"


def _lifecycle_log_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".cloakbrowser" / "lifecycle.log"


def _log_event(event: str, payload: dict[str, Any]) -> None:
    try:
        path = _lifecycle_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"event": event, "timestamp": time.time(), **payload}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        return
