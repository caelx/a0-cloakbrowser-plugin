#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


PLUGIN_NAME = "cloakbrowser"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CloakBrowser Agent Zero plugin maintenance")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=[
            "run",
            "reconcile",
            "install",
            "setup",
            "update",
            "status",
            "verify",
            "repair",
            "enable",
            "disable",
            "uninstall",
        ],
    )
    parser.add_argument("--noninteractive", action="store_true")
    parser.add_argument("--skip-system-deps", action="store_true")
    parser.add_argument("--remove-extensions", action="store_true")
    parser.add_argument("--force", action="store_true", help="Run setup even if this plugin is disabled")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    args = parser.parse_args(argv)

    if args.command == "status":
        from plugin_imports import plugin_import

        collect_status = plugin_import("helpers.diagnostics").collect_status

        status = collect_status()
        if args.json:
            status.update(_lifecycle_state())
        _print_result(status if args.json else format_status(status))
        return 0
    if args.command == "verify":
        from plugin_imports import plugin_import

        verify_browser_launch = plugin_import("helpers.verify").verify_browser_launch

        try:
            result = verify_browser_launch()
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        _print_result(json.dumps(result, indent=2, sort_keys=True) if args.json else format_verify(result))
        return 0 if result.get("ok") else 1
    if args.command in {"enable", "disable"}:
        from plugin_imports import plugin_import

        collect_status = plugin_import("helpers.diagnostics").collect_status

        _set_plugin_enabled(args.command == "enable")
        status = collect_status()
        payload = {
            "ok": True,
            "command": args.command,
            "status": status,
            **_lifecycle_state(),
        }
        _print_result(json.dumps(payload, indent=2, sort_keys=True) if args.json else format_lifecycle(payload))
        return 0
    if args.command in {"run", "reconcile"} and not args.force and not _is_plugin_enabled():
        from plugin_imports import plugin_import

        uninstall = plugin_import("helpers.uninstall").uninstall

        result = uninstall(remove_extensions=False)
        payload = {
            "ok": bool(result.get("ok")),
            "command": args.command,
            "disabled": True,
            "uninstall": result,
            **_lifecycle_state(),
        }
        _print_result(json.dumps(payload, indent=2, sort_keys=True) if args.json else format_uninstall(result))
        return 0 if result.get("ok") else 1
    if args.command in {"run", "reconcile", "install", "setup", "update", "repair"}:
        from plugin_imports import plugin_import

        collect_status = plugin_import("helpers.diagnostics").collect_status
        setup_plugin = plugin_import("helpers.setup").setup_plugin

        started = dt.datetime.now(dt.timezone.utc)
        monotonic_start = time.monotonic()
        result = setup_plugin(
            noninteractive=True if args.command == "run" else args.noninteractive,
            skip_system_deps=args.skip_system_deps,
        )
        finished = dt.datetime.now(dt.timezone.utc)
        status = collect_status()
        readiness = setup_readiness(status, setup_result=result)
        payload = {
            "ok": bool(result.get("ok")) and (readiness["ok"] or readiness.get("restart_scheduled")),
            "command": args.command,
            "started": _iso(started),
            "finished": _iso(finished),
            "elapsed_seconds": round(time.monotonic() - monotonic_start, 2),
            "setup": result,
            "status": status,
            "readiness": readiness,
            **_lifecycle_state(),
        }
        _print_result(json.dumps(payload, indent=2, sort_keys=True) if args.json else format_setup(payload))
        return 0 if payload["ok"] else 1
    if args.command == "uninstall":
        from plugin_imports import plugin_import

        uninstall = plugin_import("helpers.uninstall").uninstall

        result = uninstall(remove_extensions=args.remove_extensions)
        _print_result(json.dumps(result, indent=2, sort_keys=True) if args.json else format_uninstall(result))
        return 0 if result.get("ok") else 1
    return 2


def setup_readiness(
    status: dict[str, Any],
    *,
    setup_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    invariants = status.get("invariants") or {}
    checks = {
        "setup_complete": bool(status.get("setup", {}).get("installed")),
        "cloakbrowser_installed": bool(status.get("cloakbrowser", {}).get("installed")),
        "upstream_browser_available": bool(status.get("browser", {}).get("upstream_available")),
        "source_patch_current": bool(invariants.get("source_patch_current")),
        "extension_config_reconciled": bool(invariants.get("extension_config_reconciled")),
        "last_launch_used_cloakbrowser": bool(invariants.get("last_launch_used_cloakbrowser")),
    }
    if status.get("config", {}).get("runtime", {}).get("headed"):
        display = status.get("display", {})
        checks["display_usable"] = bool(display.get("usable_current") or display.get("usable_configured"))
    failed = [name for name, ok in checks.items() if not ok]
    restart_scheduled = bool((setup_result or {}).get("restart_scheduled"))
    return {
        "ok": not failed,
        "checks": checks,
        "failed": failed,
        "restart_scheduled": restart_scheduled,
        "restart_message": (setup_result or {}).get("restart_message", ""),
    }


def _is_plugin_enabled() -> bool:
    root = Path(__file__).resolve().parent
    try:
        from plugin_imports import ensure_agent_zero_path

        ensure_agent_zero_path(root)
        with _without_local_helpers(root):
            from helpers import plugins

            enabled = plugins.get_enabled_plugins(None)
    except Exception:
        return True

    if enabled is None:
        return True
    for item in enabled:
        if item == PLUGIN_NAME:
            return True
        if isinstance(item, dict):
            name = item.get("name") or item.get("id") or item.get("plugin_name")
            if name == PLUGIN_NAME:
                return True
        else:
            name = getattr(item, "name", None) or getattr(item, "id", None)
            if name == PLUGIN_NAME:
                return True

    return False


def _set_plugin_enabled(enabled: bool) -> None:
    root = Path(__file__).resolve().parent
    from plugin_imports import ensure_agent_zero_path

    ensure_agent_zero_path(root)
    with _without_local_helpers(root):
        from helpers import plugins

        plugins.toggle_plugin(PLUGIN_NAME, enabled)


def _lifecycle_state() -> dict[str, Any]:
    enabled = _is_plugin_enabled()
    return {
        "enabled": enabled,
        "toggle_state": "enabled" if enabled else "disabled",
        "desired_state": "enabled" if enabled else "disabled",
    }


@contextmanager
def _without_local_helpers(root: Path):
    previous_sys_path = list(sys.path)
    previous_helpers = {
        name: module
        for name, module in sys.modules.items()
        if name == "helpers" or name.startswith("helpers.")
    }
    removed_entries: list[tuple[int, str]] = []
    removed_modules: dict[str, Any] = {}
    for name, module in list(sys.modules.items()):
        if name != "helpers" and not name.startswith("helpers."):
            continue
        module_file = Path(getattr(module, "__file__", "") or "")
        if not module_file:
            continue
        try:
            if not module_file.resolve().is_relative_to(root):
                continue
        except Exception:
            continue
        removed_modules[name] = module
        sys.modules.pop(name, None)

    for index, entry in reversed(list(enumerate(sys.path))):
        try:
            matches_root = Path(entry or ".").resolve() == root
        except Exception:
            matches_root = False
        if entry == str(root) or matches_root:
            removed_entries.append((index, entry))
            sys.path.pop(index)

    try:
        yield
    finally:
        sys.path[:] = previous_sys_path
        for name in list(sys.modules):
            if name == "helpers" or name.startswith("helpers."):
                sys.modules.pop(name, None)
        sys.modules.update(previous_helpers)


def format_setup(payload: dict[str, Any]) -> str:
    setup = payload["setup"]
    status = payload["status"]
    readiness = payload["readiness"]
    lines = [
        "CloakBrowser setup",
        f"Started:  {payload['started']}",
        f"Finished: {payload['finished']}",
        f"Elapsed:  {payload['elapsed_seconds']}s",
        "",
        _format_system_dependencies(setup.get("system", {})),
        _format_python_dependencies(setup.get("python", {})),
        _format_cloakbrowser(status.get("cloakbrowser", {}), status.get("config", {})),
        _format_display(setup.get("display", {}), status.get("display", {})),
        _format_effective_location(status.get("effective_location", {})),
        _format_extensions(setup.get("extension_actions") or setup.get("manifest", {}).get("extension_actions", []), status),
        _format_setup_lifecycle(setup.get("lifecycle") or setup.get("manifest", {}).get("lifecycle", {})),
        "",
        _format_readiness(readiness),
    ]
    if not setup.get("ok") and setup.get("error"):
        lines.extend(["", f"Failure: {setup['error']}"])
    if not readiness["ok"]:
        lines.extend(["Next action: click Execute again after fixing the failed item above."])
    return "\n".join(line for line in lines if line is not None)


def format_status(status: dict[str, Any]) -> str:
    readiness = setup_readiness(status)
    return "\n".join(
        [
            "CloakBrowser status",
            f"Setup: {_yes_no(status.get('setup', {}).get('installed'))} ({status.get('setup', {}).get('status', 'unknown')})",
            _format_cloakbrowser(status.get("cloakbrowser", {}), status.get("config", {})),
            _format_display({}, status.get("display", {})),
            _format_effective_location(status.get("effective_location", {})),
            _format_patch_status(status),
            _format_extensions([], status),
            _format_last_launch(status),
            "",
            _format_readiness(readiness),
        ]
    )


def format_uninstall(result: dict[str, Any]) -> str:
    lines = [
        "CloakBrowser uninstall",
        f"Result: {'complete' if result.get('ok') else 'failed'}",
        f"Disabled extension paths: {len(result.get('disabled_extension_paths') or [])}",
        f"Playwright masquerade removed: {_yes_no(result.get('masquerade_removed'))}",
        f"Restart required: {_yes_no(result.get('restart_required'))}",
    ]
    if result.get("removed_extensions"):
        lines.append(f"Removed extension directories: {len(result['removed_extensions'])}")
    return "\n".join(lines)


def format_lifecycle(payload: dict[str, Any]) -> str:
    status = payload.get("status", {})
    return "\n".join(
        [
            "CloakBrowser lifecycle",
            f"Command: {payload.get('command', 'unknown')}",
            f"Toggle: {payload.get('toggle_state', 'unknown')}",
            "",
            format_status(status),
        ]
    )


def format_verify(result: dict[str, Any]) -> str:
    if result.get("ok"):
        return "CloakBrowser verification: ready"
    return f"CloakBrowser verification failed: {result.get('error') or ', '.join(result.get('failed') or ['unknown'])}"


def _format_system_dependencies(system: dict[str, Any]) -> str:
    if not system:
        return "System dependencies: not run"
    if system.get("skipped"):
        return f"System dependencies: skipped ({system.get('reason', 'no reason recorded')})"
    installed = len(system.get("installed_packages") or [])
    failed = system.get("failed_packages") or []
    status = "ready" if system.get("ok") else "warnings"
    line = f"System dependencies: {status}; {installed} package checks installed or already present"
    if failed:
        line += f"; failed: {', '.join(failed)}"
    return line


def _format_python_dependencies(python: dict[str, Any]) -> str:
    if not python:
        return "Python dependencies: not run"
    status = "ready" if python.get("ok") else "failed"
    command = " ".join(str(item) for item in python.get("command", [])[-4:])
    return f"Python dependencies: {status}" + (f" ({command})" if command else "")


def _format_cloakbrowser(cloakbrowser: dict[str, Any], config: dict[str, Any]) -> str:
    cache = config.get("runtime", {}).get("cloakbrowser_cache_dir", "")
    if not cloakbrowser.get("installed"):
        return f"CloakBrowser binary/cache: not ready ({cloakbrowser.get('error', 'package not installed')})"
    binary = cloakbrowser.get("binary_path") or cloakbrowser.get("binary_error") or "unknown"
    version = cloakbrowser.get("version") or "unknown version"
    return f"CloakBrowser binary/cache: ready; {version}; binary={binary}; cache={cache}"


def _format_display(setup_display: dict[str, Any], status_display: dict[str, Any]) -> str:
    display = setup_display.get("display") or status_display.get("current") or status_display.get("configured") or ""
    usable = status_display.get("usable_current") or status_display.get("usable_configured") or setup_display.get("ok")
    detail = "reused" if setup_display.get("reused") else setup_display.get("managed_by", "")
    suffix = f"; {detail}" if detail else ""
    return f"Display/Xvfb: {'ready' if usable else 'not ready'}; display={display or 'unset'}{suffix}"


def _format_effective_location(location: dict[str, Any]) -> str:
    if not location:
        return "Effective location: not recorded yet"
    timezone = location.get("timezone") or "unset"
    locale = location.get("locale") or "unset"
    exit_ip = location.get("exit_ip") or "unset"
    source = "proxy" if location.get("proxy") else "public"
    return f"Effective location: timezone={timezone}; locale={locale}; exit_ip={exit_ip}; source={source}"


def _format_extensions(actions: list[dict[str, Any]], status: dict[str, Any]) -> str:
    if not actions:
        items = status.get("extensions", {}).get("items", [])
        if not items:
            return "Extensions: no managed extensions found"
        actions = [
            {
                "name": item.get("name"),
                "action": "enabled" if item.get("enabled") else "disabled",
                "installed": item.get("installed"),
                "enabled": item.get("enabled"),
            }
            for item in items
        ]
    lines = ["Extensions:"]
    for item in actions:
        installed = "installed" if item.get("installed") else "not installed"
        enabled = "enabled" if item.get("enabled") else "disabled"
        lines.append(f"- {item.get('name') or item.get('key')}: {item.get('action')}; {installed}; {enabled}")
    active_paths = status.get("extensions", {}).get("active_paths") or []
    lines.append(f"Active extension paths synced: {len(active_paths)}")
    reconciliation = status.get("extension_reconciliation") or {}
    if reconciliation:
        lines.append("Reconciliation: " + ("ready" if reconciliation.get("ok") else "failed"))
    return "\n".join(lines)


def _format_patch_status(status: dict[str, Any]) -> str:
    validation = status.get("runtime_patch_validation") or {}
    if not validation:
        return "Required patches: not checked"
    if validation.get("ok"):
        return "Required patches: ready"
    return "Required patches: failed (" + ", ".join(validation.get("failed") or ["unknown"]) + ")"


def _format_last_launch(status: dict[str, Any]) -> str:
    last_launch = status.get("last_launch") or {}
    if not last_launch:
        return "Last launch: not recorded"
    backend = "CloakBrowser" if "cloakbrowser" in str(last_launch.get("binary", "")).lower() else "unknown"
    return f"Last launch: {backend}"


def _format_setup_lifecycle(lifecycle: dict[str, Any]) -> str:
    if not lifecycle:
        return "Lifecycle: not recorded"
    stopped = lifecycle.get("browser_processes_stopped") or {}
    restart = lifecycle.get("agent_zero_restart") or {}
    matched = len(stopped.get("matched") or [])
    terminated = len(stopped.get("terminated") or [])
    killed = len(stopped.get("killed") or [])
    if restart.get("needed"):
        if restart.get("scheduled"):
            restart_text = restart.get("message") or "restart scheduled"
        else:
            restart_text = "restarted" if restart.get("restarted") else "restart required"
    else:
        restart_text = "not needed"
    return (
        "Lifecycle: "
        f"stale browser processes matched={matched}, terminated={terminated}, killed={killed}; "
        f"Agent Zero restart={restart_text}"
    )


def _format_readiness(readiness: dict[str, Any]) -> str:
    if readiness.get("restart_scheduled"):
        message = readiness.get("restart_message") or "Agent Zero restart scheduled after Execute returns."
        return f"Final readiness: pending restart. {message}"
    if readiness["ok"]:
        return "Final readiness: ready. The Browser tool can use CloakBrowser."
    failed = ", ".join(readiness.get("failed") or ["unknown"])
    return f"Final readiness: not ready. Failed checks: {failed}."


def _iso(value: dt.datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def _yes_no(value: Any) -> str:
    return "yes" if value else "no"


def _print_result(text: str | dict[str, Any]) -> None:
    if isinstance(text, str):
        print(text)
    else:
        print(json.dumps(text, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
