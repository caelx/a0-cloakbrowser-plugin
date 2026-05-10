#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CloakBrowser Agent Zero plugin maintenance")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "setup", "status", "repair", "uninstall"])
    parser.add_argument("--noninteractive", action="store_true")
    parser.add_argument("--skip-system-deps", action="store_true")
    parser.add_argument("--remove-extensions", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    args = parser.parse_args(argv)

    if args.command == "status":
        from plugin_imports import plugin_import

        collect_status = plugin_import("helpers.diagnostics").collect_status

        status = collect_status()
        _print_result(status if args.json else format_status(status))
        return 0
    if args.command in {"run", "setup", "repair"}:
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
        payload = {
            "ok": bool(result.get("ok")) and setup_readiness(status)["ok"],
            "command": args.command,
            "started": _iso(started),
            "finished": _iso(finished),
            "elapsed_seconds": round(time.monotonic() - monotonic_start, 2),
            "setup": result,
            "status": status,
            "readiness": setup_readiness(status),
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


def setup_readiness(status: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "setup_complete": bool(status.get("setup", {}).get("installed")),
        "cloakbrowser_installed": bool(status.get("cloakbrowser", {}).get("installed")),
        "upstream_browser_available": bool(status.get("browser", {}).get("upstream_available")),
    }
    if status.get("config", {}).get("runtime", {}).get("headed"):
        display = status.get("display", {})
        checks["display_usable"] = bool(display.get("usable_current") or display.get("usable_configured"))
    failed = [name for name, ok in checks.items() if not ok]
    return {"ok": not failed, "checks": checks, "failed": failed}


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
        _format_extensions(setup.get("extension_actions") or setup.get("manifest", {}).get("extension_actions", []), status),
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
            _format_extensions([], status),
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
    return "\n".join(lines)


def _format_readiness(readiness: dict[str, Any]) -> str:
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
