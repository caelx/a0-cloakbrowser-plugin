from __future__ import annotations

import shutil
import subprocess
import importlib.util

PACKAGE_GROUPS = [
    (
        "Fonts",
        [
            "fonts-freefont-ttf",
            "fonts-ipafont-gothic",
            "fonts-unifont",
            "fonts-liberation",
            "fonts-noto-color-emoji",
            "fonts-tlwg-loma-otf",
            "fonts-wqy-zenhei",
            "fontconfig",
        ],
    ),
    ("Display", ["xvfb", "x11-utils"]),
    (
        "Browser libraries",
        [
            "libatk-bridge2.0-0",
            "libatk1.0-0",
            "libatspi2.0-0",
            "libcairo2",
            "libcups2",
            "libdbus-1-3",
            "libdrm2",
            "libgbm1",
            "libgtk-3-0",
            "libnspr4",
            "libnss3",
            "libpango-1.0-0",
            "libx11-6",
            "libxcb1",
            "libxcomposite1",
            "libxdamage1",
            "libxext6",
            "libxfixes3",
            "libxkbcommon0",
            "libxrandr2",
            "libxrender1",
            "libxshmfence1",
        ],
    ),
]

ADAPTIVE_PACKAGES = [("libasound2", "libasound2t64")]
BASE_PACKAGES = [package for _, packages in PACKAGE_GROUPS for package in packages]


def install_system_dependencies(noninteractive: bool = True) -> dict:
    if not shutil.which("apt-get"):
        return {"ok": False, "skipped": True, "reason": "apt-get not available"}
    env = None
    update = subprocess.run(["apt-get", "update"], check=False, text=True, capture_output=True, env=env)
    groups: list[dict] = []
    installed_packages: list[str] = []
    failed_packages: list[str] = []
    stderr_chunks: list[str] = [update.stderr or ""]
    for group_name, packages in PACKAGE_GROUPS:
        group = _install_package_group(group_name, packages, env=env)
        groups.append(group)
        installed_packages.extend(group["installed"])
        failed_packages.extend(group["failed"])
        stderr_chunks.append(group.get("stderr_tail", ""))
    adaptive_results = []
    for candidates in ADAPTIVE_PACKAGES:
        result = _install_first_available(candidates, env=env)
        adaptive_results.append(result)
        if result.get("installed"):
            installed_packages.append(result["installed"])
        else:
            failed_packages.append("/".join(candidates))
        stderr_chunks.append(result.get("stderr_tail", ""))
    subprocess.run(["ldconfig"], check=False, capture_output=True, text=True)
    return {
        "ok": update.returncode == 0 and not failed_packages,
        "packages": [*BASE_PACKAGES, *["/".join(item) for item in ADAPTIVE_PACKAGES]],
        "installed_packages": installed_packages,
        "failed_packages": failed_packages,
        "groups": groups,
        "adaptive_packages": adaptive_results,
        "apt_update_returncode": update.returncode,
        "apt_install_returncode": 0 if not failed_packages else 1,
        "stderr_tail": "\n".join(chunk for chunk in stderr_chunks if chunk)[-4000:],
    }


def install_python_dependencies(
    requirement: str | None = None,
    *,
    auto_update_cloakbrowser: bool = True,
    repair_playwright: bool = True,
) -> dict:
    import sys
    from .config import plugin_dir

    if requirement is None:
        requirements_path = plugin_dir() / "ci" / "requirements-cloakbrowser.txt"
        requirement = (
            requirements_path.read_text(encoding="utf-8").strip()
            if requirements_path.is_file()
            else "cloakbrowser[geoip]>=0.3.28"
        )
    cmd = [sys.executable, "-m", "pip", "install"]
    actions = []
    if auto_update_cloakbrowser:
        cmd.append("--upgrade")
        actions.append("cloakbrowser_upgrade")
    else:
        actions.append("cloakbrowser_install")
    cmd.append(requirement)
    playwright_installed = importlib.util.find_spec("playwright") is not None
    if not playwright_installed and repair_playwright:
        cmd.append("playwright")
        actions.append("playwright_install_missing")
    elif playwright_installed:
        actions.append("playwright_preserved")
    result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    return {
        "ok": result.returncode == 0,
        "command": cmd,
        "actions": actions,
        "playwright_installed": playwright_installed,
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-4000:],
        "stderr_tail": (result.stderr or "")[-4000:],
    }


def _install_package_group(group_name: str, packages: list[str], *, env) -> dict:
    result = _apt_install(packages, env=env)
    if result.returncode == 0:
        return {
            "name": group_name,
            "ok": True,
            "installed": list(packages),
            "failed": [],
            "fallback": False,
            "stderr_tail": (result.stderr or "")[-1000:],
        }
    installed: list[str] = []
    failed: list[str] = []
    stderr = [result.stderr or ""]
    for package in packages:
        item_result = _apt_install([package], env=env)
        stderr.append(item_result.stderr or "")
        if item_result.returncode == 0:
            installed.append(package)
        else:
            failed.append(package)
    return {
        "name": group_name,
        "ok": not failed,
        "installed": installed,
        "failed": failed,
        "fallback": True,
        "stderr_tail": "\n".join(stderr)[-1000:],
    }


def _install_first_available(candidates: tuple[str, ...], *, env) -> dict:
    attempts = []
    for package in candidates:
        result = _apt_install([package], env=env)
        attempts.append({"package": package, "returncode": result.returncode})
        if result.returncode == 0:
            return {
                "ok": True,
                "installed": package,
                "candidates": list(candidates),
                "attempts": attempts,
                "stderr_tail": (result.stderr or "")[-1000:],
            }
    return {
        "ok": False,
        "installed": "",
        "candidates": list(candidates),
        "attempts": attempts,
        "stderr_tail": "",
    }


def _apt_install(packages: list[str], *, env) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["apt-get", "install", "-y", "--no-install-recommends", *packages],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
