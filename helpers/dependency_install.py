from __future__ import annotations

import shutil
import subprocess

BASE_PACKAGES = [
    "fonts-freefont-ttf",
    "fonts-ipafont-gothic",
    "fonts-unifont",
    "fonts-liberation",
    "fonts-noto-color-emoji",
    "fonts-tlwg-loma-otf",
    "fonts-wqy-zenhei",
    "fontconfig",
    "xvfb",
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
]


def install_system_dependencies(noninteractive: bool = True) -> dict:
    if not shutil.which("apt-get"):
        return {"ok": False, "skipped": True, "reason": "apt-get not available"}
    env = None
    packages = list(BASE_PACKAGES)
    packages.append(_audio_package())
    update = subprocess.run(["apt-get", "update"], check=False, text=True, capture_output=True, env=env)
    install = subprocess.run(
        ["apt-get", "install", "-y", "--no-install-recommends", *packages],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(["ldconfig"], check=False, capture_output=True, text=True)
    return {
        "ok": update.returncode == 0 and install.returncode == 0,
        "packages": packages,
        "apt_update_returncode": update.returncode,
        "apt_install_returncode": install.returncode,
        "stderr_tail": (install.stderr or update.stderr or "")[-4000:],
    }


def install_python_dependencies(requirement: str | None = None) -> dict:
    import sys
    from .config import plugin_dir

    if requirement is None:
        requirements_path = plugin_dir() / "ci" / "requirements-cloakbrowser.txt"
        requirement = (
            requirements_path.read_text(encoding="utf-8").strip()
            if requirements_path.is_file()
            else "cloakbrowser[geoip]==0.3.27"
        )
    cmd = [sys.executable, "-m", "pip", "install", "playwright", requirement]
    result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    return {
        "ok": result.returncode == 0,
        "command": cmd,
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-4000:],
        "stderr_tail": (result.stderr or "")[-4000:],
    }


def _audio_package() -> str:
    policy = subprocess.run(
        ["apt-cache", "policy", "libasound2"],
        check=False,
        capture_output=True,
        text=True,
    )
    if "Candidate: (none)" not in policy.stdout and "Candidate:" in policy.stdout:
        return "libasound2"
    return "libasound2t64"
