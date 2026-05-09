#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CloakBrowser Agent Zero plugin maintenance")
    parser.add_argument("command", nargs="?", default="status", choices=["setup", "status", "repair", "uninstall"])
    parser.add_argument("--noninteractive", action="store_true")
    parser.add_argument("--skip-system-deps", action="store_true")
    parser.add_argument("--remove-extensions", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "status":
        from plugin_imports import plugin_import

        collect_status = plugin_import("helpers.diagnostics").collect_status

        print(json.dumps(collect_status(), indent=2, sort_keys=True))
        return 0
    if args.command in {"setup", "repair"}:
        from plugin_imports import plugin_import

        setup_plugin = plugin_import("helpers.setup").setup_plugin

        result = setup_plugin(
            noninteractive=args.noninteractive,
            skip_system_deps=args.skip_system_deps,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1
    if args.command == "uninstall":
        from plugin_imports import plugin_import

        uninstall = plugin_import("helpers.uninstall").uninstall

        result = uninstall(remove_extensions=args.remove_extensions)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
