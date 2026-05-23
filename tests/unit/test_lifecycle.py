from pathlib import Path
from types import SimpleNamespace

from helpers import lifecycle


def test_stop_managed_browser_processes_targets_agent_zero_browser_paths(monkeypatch, tmp_path):
    proc_root = tmp_path / "proc"
    _proc(proc_root, 101, ["/opt/chrome", "--user-data-dir=/a0/tmp/browser/sessions/demo"])
    _proc(proc_root, 102, ["/opt/chrome", "--user-data-dir=/home/user/profile"])
    _proc(proc_root, 103, ["/opt/cloakbrowser/chrome", "--flag"])

    signals = []
    live = {101: True, 103: True}

    def fake_kill(pid, sig):
        signals.append((pid, sig))
        if sig == 0:
            if not live.get(pid, False):
                raise ProcessLookupError
            return
        live[pid] = False

    monkeypatch.setattr(lifecycle.os, "getpid", lambda: 999)
    monkeypatch.setattr(lifecycle.os, "kill", fake_kill)

    result = lifecycle.stop_managed_browser_processes(
        {"runtime": {"cloakbrowser_cache_dir": "/opt/cloakbrowser"}},
        proc_root=proc_root,
        timeout=0,
    )

    assert {item["pid"] for item in result["matched"]} == {101, 103}
    assert set(result["terminated"]) == {101, 103}
    assert result["killed"] == []
    assert (102, lifecycle.signal.SIGTERM) not in signals


def test_stock_agent_zero_playwright_browser_is_flagged(monkeypatch, tmp_path):
    proc_root = tmp_path / "proc"
    _proc(
        proc_root,
        101,
        [
            "/a0/tmp/playwright/chromium-1169/chrome-linux/chrome",
            "--load-extension=/a0/usr/plugins/cloakbrowser/.cloakbrowser/extensions/ublock-origin-lite",
            "--user-data-dir=/a0/tmp/browser/sessions/demo",
        ],
    )
    _proc(
        proc_root,
        102,
        [
            "/srv/changedetection/playwright/chromium-1169/chrome-linux/chrome",
            "--user-data-dir=/tmp/browser/sessions/demo",
        ],
    )
    monkeypatch.setattr(lifecycle.os, "getpid", lambda: 999)

    matches = lifecycle._managed_browser_processes({}, proc_root=proc_root)

    assert {item["pid"] for item in matches} == {101}
    stock = [item for item in matches if item["stock_playwright_browser"]]
    assert [item["pid"] for item in stock] == [101]


def test_restart_agent_zero_is_skipped_when_runtime_patch_did_not_change(monkeypatch):
    calls = []
    monkeypatch.setattr(lifecycle.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    result = lifecycle.restart_agent_zero_if_needed(False)

    assert result == {"needed": False, "restarted": False, "restart_required": False}
    assert calls == []


def test_restart_agent_zero_uses_discovered_supervisor_program(monkeypatch):
    commands = []
    schedules = []
    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/bin/supervisorctl")

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["/usr/bin/supervisorctl", "status"]:
            return SimpleNamespace(returncode=0, stdout="agent-zero RUNNING pid 1\n", stderr="")

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)
    monkeypatch.setattr(
        lifecycle,
        "_schedule_supervisor_restart",
        lambda supervisorctl, program, delay_seconds: schedules.append(
            (supervisorctl, program, delay_seconds)
        )
        or {"scheduled": True, "message": "scheduled"},
    )

    result = lifecycle.restart_agent_zero_if_needed(True)

    assert commands == [["/usr/bin/supervisorctl", "status"]]
    assert schedules == [("/usr/bin/supervisorctl", "agent-zero", 10)]
    assert result["scheduled"] is True
    assert result["restarted"] is False
    assert result["restart_required"] is False


def test_restart_agent_zero_discovers_run_ui_by_pid_cmdline(monkeypatch, tmp_path):
    proc_root = tmp_path / "proc"
    _proc(proc_root, 27, ["/opt/venv-a0/bin/python", "/a0/run_ui.py", "--port=80"])
    commands = []
    schedules = []
    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/bin/supervisorctl")

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["/usr/bin/supervisorctl", "status"]:
            return SimpleNamespace(
                returncode=0,
                stdout="run_cron RUNNING pid 23\nrun_ui RUNNING pid 27\n",
                stderr="",
            )

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)
    monkeypatch.setattr(
        lifecycle,
        "_schedule_supervisor_restart",
        lambda supervisorctl, program, delay_seconds: schedules.append(
            (supervisorctl, program, delay_seconds)
        )
        or {"scheduled": True, "message": "scheduled"},
    )
    original_program_lookup = lifecycle._agent_zero_supervisor_program
    monkeypatch.setattr(
        lifecycle,
        "_agent_zero_supervisor_program",
        lambda output: original_program_lookup(output, proc_root=proc_root),
    )

    result = lifecycle.restart_agent_zero_if_needed(True)

    assert commands == [["/usr/bin/supervisorctl", "status"]]
    assert schedules == [("/usr/bin/supervisorctl", "run_ui", 10)]
    assert result["program"] == "run_ui"
    assert result["scheduled"] is True


def test_restart_agent_zero_discovers_run_ui_child_process(monkeypatch, tmp_path):
    proc_root = tmp_path / "proc"
    _proc(proc_root, 27, ["python", "/exe/self_update_manager.py", "docker-run-ui"])
    _proc(proc_root, 209, ["/opt/venv-a0/bin/python", "/a0/run_ui.py", "--port=80"], ppid=27)
    commands = []
    schedules = []
    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/bin/supervisorctl")

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["/usr/bin/supervisorctl", "status"]:
            return SimpleNamespace(returncode=0, stdout="run_ui RUNNING pid 27\n", stderr="")

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)
    monkeypatch.setattr(
        lifecycle,
        "_schedule_supervisor_restart",
        lambda supervisorctl, program, delay_seconds: schedules.append(
            (supervisorctl, program, delay_seconds)
        )
        or {"scheduled": True, "message": "scheduled"},
    )
    original_program_lookup = lifecycle._agent_zero_supervisor_program
    monkeypatch.setattr(
        lifecycle,
        "_agent_zero_supervisor_program",
        lambda output: original_program_lookup(output, proc_root=proc_root),
    )

    result = lifecycle.restart_agent_zero_if_needed(True)

    assert commands[-1] == ["/usr/bin/supervisorctl", "status"]
    assert schedules == [("/usr/bin/supervisorctl", "run_ui", 10)]
    assert result["program"] == "run_ui"


def test_restart_agent_zero_parses_status_stdout_when_supervisor_returns_nonzero(monkeypatch):
    commands = []
    schedules = []
    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/bin/supervisorctl")

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["/usr/bin/supervisorctl", "status"]:
            return SimpleNamespace(
                returncode=3,
                stdout="agent-zero RUNNING pid 1\nworker STOPPED not started\n",
                stderr="worker stopped",
            )

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)
    monkeypatch.setattr(
        lifecycle,
        "_schedule_supervisor_restart",
        lambda supervisorctl, program, delay_seconds: schedules.append(
            (supervisorctl, program, delay_seconds)
        )
        or {"scheduled": True, "message": "scheduled"},
    )

    result = lifecycle.restart_agent_zero_if_needed(True)

    assert commands == [["/usr/bin/supervisorctl", "status"]]
    assert schedules == [("/usr/bin/supervisorctl", "agent-zero", 10)]
    assert result["scheduled"] is True
    assert result["restart_required"] is False


def test_restart_agent_zero_detects_agent_zero_when_program_is_stopped(monkeypatch):
    commands = []
    schedules = []
    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/bin/supervisorctl")

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["/usr/bin/supervisorctl", "status"]:
            return SimpleNamespace(returncode=0, stdout="agent-zero STOPPED not started\n", stderr="")

    monkeypatch.setattr(lifecycle.subprocess, "run", fake_run)
    monkeypatch.setattr(
        lifecycle,
        "_schedule_supervisor_restart",
        lambda supervisorctl, program, delay_seconds: schedules.append(
            (supervisorctl, program, delay_seconds)
        )
        or {"scheduled": True, "message": "scheduled"},
    )

    result = lifecycle.restart_agent_zero_if_needed(True)

    assert commands == [["/usr/bin/supervisorctl", "status"]]
    assert schedules == [("/usr/bin/supervisorctl", "agent-zero", 10)]
    assert result["scheduled"] is True


def test_scheduled_restart_falls_back_to_start(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(lifecycle, "_lifecycle_log_path", lambda: tmp_path / "lifecycle.log")

    class Process:
        pid = 123

    def fake_popen(command, **kwargs):
        commands.append(command)
        return Process()

    monkeypatch.setattr(lifecycle.subprocess, "Popen", fake_popen)

    result = lifecycle._schedule_supervisor_restart(
        "/usr/bin/supervisorctl",
        "run_ui",
        delay_seconds=10,
    )

    assert result["scheduled"] is True
    assert result["scheduler_pid"] == 123
    script = commands[0][2]
    assert "sleep 10" in script
    assert "supervisorctl' restart 'run_ui'" in script
    assert "supervisorctl' start 'run_ui'" in script
    assert "supervisorctl' status 'run_ui'" in script


def test_restart_agent_zero_reports_manual_restart_when_program_missing(monkeypatch):
    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/bin/supervisorctl")
    monkeypatch.setattr(
        lifecycle.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="cloakbrowser_xvfb RUNNING pid 2\nother RUNNING pid 3\n",
            stderr="",
        ),
    )

    result = lifecycle.restart_agent_zero_if_needed(True)

    assert result["restarted"] is False
    assert result["restart_required"] is True
    assert result["reason"] == "agent_zero_program_not_found"


def test_restart_agent_zero_does_not_select_unrelated_web_sidecar(monkeypatch):
    monkeypatch.setattr(lifecycle.shutil, "which", lambda name: "/usr/bin/supervisorctl")
    monkeypatch.setattr(
        lifecycle.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="websocket RUNNING pid 2\napi-server RUNNING pid 3\n",
            stderr="",
        ),
    )

    result = lifecycle.restart_agent_zero_if_needed(True)

    assert result["restarted"] is False
    assert result["restart_required"] is True
    assert result["reason"] == "agent_zero_program_not_found"


def test_reconcile_restarts_when_source_patch_changed_or_stock_browser_detected(monkeypatch):
    restarts = []
    stop_calls = []
    matched_calls = [
        [
            {
                "pid": 101,
                "reason": "/a0/tmp/browser/sessions",
                "cmdline": ["/a0/tmp/playwright/chromium-1169/chrome", "--user-data-dir=/a0/tmp/browser/sessions/a"],
                "stock_playwright_browser": True,
            }
        ],
        [],
    ]
    monkeypatch.setattr(
        lifecycle,
        "stop_managed_browser_processes",
        lambda config, **kwargs: stop_calls.append((config, kwargs.get("matches")))
        or {"matched": [], "terminated": [], "killed": [], "failed": []},
    )
    monkeypatch.setattr(
        lifecycle,
        "_managed_browser_processes",
        lambda config: matched_calls.pop(0),
    )
    monkeypatch.setattr(
        lifecycle,
        "restart_agent_zero_if_needed",
        lambda needed: restarts.append(needed)
        or {"needed": needed, "restarted": needed, "restart_required": False},
    )

    lifecycle.reconcile_after_setup({}, {"applied": True, "already_patched": True})
    lifecycle.reconcile_after_setup({}, {"applied": True, "already_patched": False})

    assert restarts == [True, True]
    assert stop_calls[0][1][0]["pid"] == 101
    assert stop_calls[1][1] == []


def test_reconcile_skips_cleanup_when_live_runtime_is_current(monkeypatch):
    restart_calls = []
    stop_calls = []
    monkeypatch.setattr(
        lifecycle,
        "_managed_browser_processes",
        lambda config: [
            {
                "pid": 201,
                "reason": "/opt/cloakbrowser",
                "cmdline": ["/opt/cloakbrowser/chrome"],
                "stock_playwright_browser": False,
            }
        ],
    )
    monkeypatch.setattr(
        lifecycle,
        "stop_managed_browser_processes",
        lambda config, **kwargs: stop_calls.append((config, kwargs)),
    )
    monkeypatch.setattr(
        lifecycle,
        "restart_agent_zero_if_needed",
        lambda needed: restart_calls.append(needed)
        or {"needed": needed, "restarted": False, "restart_required": False},
    )

    result = lifecycle.reconcile_after_setup({}, {"applied": True, "already_patched": True})

    assert restart_calls == [False]
    assert stop_calls == []
    assert result["browser_processes_stopped"]["skipped"] is True
    assert result["browser_processes_stopped"]["matched"][0]["pid"] == 201


def _proc(proc_root: Path, pid: int, cmdline: list[str], *, ppid: int = 1) -> None:
    path = proc_root / str(pid)
    path.mkdir(parents=True)
    (path / "cmdline").write_bytes(b"\0".join(item.encode() for item in cmdline) + b"\0")
    (path / "status").write_text(f"Name:\ttest\nPPid:\t{ppid}\n", encoding="utf-8")
