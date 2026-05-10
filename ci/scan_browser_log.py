from __future__ import annotations

import argparse
import re
from pathlib import Path

CRASH_SIGNATURES: tuple[str, ...] = (
    r"Browser context closed unexpectedly",
    r"BaseSubprocessTransport",
    r"RuntimeError: Event loop is closed",
    r"TargetClosedError",
    r"Traceback \(most recent call last\):",
)


def find_crash_signatures(text: str) -> list[str]:
    matches: list[str] = []
    for pattern in CRASH_SIGNATURES:
        if re.search(pattern, text):
            matches.append(pattern)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    args = parser.parse_args()

    text = args.log.read_text(encoding="utf-8", errors="replace")
    matches = find_crash_signatures(text)
    if not matches:
        print(f"No browser crash signatures found in {args.log}")
        return 0

    print(f"Browser crash signatures found in {args.log}:")
    for match in matches:
        print(f"- {match}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
