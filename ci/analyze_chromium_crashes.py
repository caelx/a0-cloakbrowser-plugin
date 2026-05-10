#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dump_dir", type=Path)
    parser.add_argument("--chrome", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("artifacts/chromium-crash-summary.json"))
    args = parser.parse_args()

    dumps = sorted(args.dump_dir.glob("*.dmp"))
    unique_dumps = [dump for dump in dumps if "-" in dump.stem]
    chrome = args.chrome or args.dump_dir / "chrome"
    symbol_dir = args.out.parent / "breakpad-symbols"
    summary = {
        "dump_dir": str(args.dump_dir),
        "chrome": str(chrome) if chrome.exists() else "",
        "tools": {
            "dump_syms": shutil.which("dump_syms") or "",
            "minidump_stackwalk": shutil.which("minidump_stackwalk") or "",
        },
        "dumps": [],
        "root_cause": "",
    }

    if summary["tools"]["dump_syms"] and chrome.exists():
        install_symbols(chrome, symbol_dir)

    for dump in unique_dumps:
        text = stackwalk(dump, symbol_dir if symbol_dir.exists() else None)
        summary["dumps"].append(parse_stackwalk(dump, text))

    summary["root_cause"] = infer_root_cause(summary["dumps"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "dumps": len(summary["dumps"]), "root_cause": summary["root_cause"]}, indent=2))
    return 0


def install_symbols(chrome: Path, symbol_dir: Path) -> None:
    symbol_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["dump_syms", str(chrome)],
        check=True,
        capture_output=True,
        text=True,
    )
    first = proc.stdout.splitlines()[0].split()
    if len(first) < 5 or first[0] != "MODULE":
        return
    module_name = first[4]
    module_id = first[3]
    target = symbol_dir / module_name / module_id
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{module_name}.sym").write_text(proc.stdout, encoding="utf-8")


def stackwalk(dump: Path, symbol_dir: Path | None) -> str:
    if not shutil.which("minidump_stackwalk"):
        return ""
    cmd = ["minidump_stackwalk", str(dump)]
    if symbol_dir:
        cmd.append(str(symbol_dir))
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return proc.stdout + "\n" + proc.stderr


def parse_stackwalk(dump: Path, text: str) -> dict[str, object]:
    frames = []
    crashed = False
    for line in text.splitlines():
        if re.match(r"Thread \d+ \(crashed\)", line):
            crashed = True
            continue
        if crashed and (line.startswith("Thread ") or line.startswith("Loaded modules:")):
            break
        if crashed and re.match(r"\s+\d+\s+", line):
            frames.append(line.strip())
        if len(frames) >= 12:
            break
    command_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("/opt/cloakbrowser/") and "--user-data-dir=" in line
    ]
    return {
        "dump": dump.name,
        "meta": dump.with_suffix(".meta").name if dump.with_suffix(".meta").exists() else "",
        "crash_reason": find_value(text, "Crash reason"),
        "crash_address": find_value(text, "Crash address"),
        "process_uptime": find_value(text, "Process uptime"),
        "operating_system": find_value(text, "Operating system"),
        "cpu": find_value(text, "CPU"),
        "top_frames": frames,
        "launch_command": command_lines[0] if command_lines else "",
        "has_oom_frame": "TerminateBecauseOutOfMemory" in text,
        "has_shared_image_frame": "CreateSharedMemoryRegionFromSIInfo" in text,
        "has_discardable_memory_frame": "DiscardableMemoryAllocator" in text,
    }


def find_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def infer_root_cause(dumps: list[dict[str, object]]) -> str:
    crash_dumps = [dump for dump in dumps if dump.get("crash_reason") == "SIGTRAP"]
    if not crash_dumps:
        return "No SIGTRAP crash dumps found."
    oom = [dump for dump in crash_dumps if dump.get("has_oom_frame")]
    shared = [
        dump for dump in oom
        if dump.get("has_shared_image_frame") or dump.get("has_discardable_memory_frame")
    ]
    if len(shared) == len(crash_dumps):
        return (
            "All SIGTRAP crashes terminate in Chromium partition_alloc out-of-memory "
            "during compositor shared-image or discardable image memory allocation."
        )
    return "SIGTRAP crashes are present, but top-frame signatures are mixed."


if __name__ == "__main__":
    raise SystemExit(main())
