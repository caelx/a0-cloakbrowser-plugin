from helpers.dependency_install import BASE_PACKAGES
from helpers import dependency_install


class Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_system_dependencies_include_xdpyinfo_provider():
    assert "x11-utils" in BASE_PACKAGES


def test_system_dependencies_fall_back_to_individual_packages(monkeypatch):
    monkeypatch.setattr(dependency_install.shutil, "which", lambda name: "/usr/bin/apt-get")

    def fake_run(cmd, **kwargs):
        if cmd == ["apt-get", "update"]:
            return Result()
        if cmd[0:3] == ["apt-get", "install", "-y"] and "fonts-freefont-ttf" in cmd and len(cmd) > 5:
            return Result(returncode=1, stderr="group failed")
        return Result()

    monkeypatch.setattr(dependency_install.subprocess, "run", fake_run)

    result = dependency_install.install_system_dependencies()

    assert result["groups"][0]["fallback"] is True
    assert "fonts-freefont-ttf" in result["installed_packages"]
    assert result["ok"] is True


def test_system_dependencies_use_t64_audio_fallback(monkeypatch):
    monkeypatch.setattr(dependency_install.shutil, "which", lambda name: "/usr/bin/apt-get")

    def fake_run(cmd, **kwargs):
        if cmd == ["apt-get", "update"]:
            return Result()
        if cmd[0:3] == ["apt-get", "install", "-y"] and cmd[-1] == "libasound2":
            return Result(returncode=1)
        return Result()

    monkeypatch.setattr(dependency_install.subprocess, "run", fake_run)

    result = dependency_install.install_system_dependencies()

    assert result["adaptive_packages"][0]["installed"] == "libasound2t64"
    assert "libasound2t64" in result["installed_packages"]


def test_python_dependencies_preserve_existing_playwright(monkeypatch):
    commands = []
    monkeypatch.setattr(dependency_install.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        dependency_install.subprocess,
        "run",
        lambda cmd, **kwargs: commands.append(cmd) or Result(),
    )

    result = dependency_install.install_python_dependencies("cloakbrowser[geoip]>=0.3.28")

    assert result["ok"] is True
    assert "playwright" not in commands[0]
    assert "playwright_preserved" in result["actions"]


def test_python_dependencies_install_playwright_only_when_missing(monkeypatch):
    commands = []
    monkeypatch.setattr(dependency_install.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(
        dependency_install.subprocess,
        "run",
        lambda cmd, **kwargs: commands.append(cmd) or Result(),
    )

    result = dependency_install.install_python_dependencies("cloakbrowser[geoip]>=0.3.28")

    assert result["ok"] is True
    assert commands[0][-1] == "playwright"
    assert "playwright_install_missing" in result["actions"]
