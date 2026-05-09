from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

REPO_TAGS_URL = "https://api.github.com/repos/uBlockOrigin/uBOL-home/tags?per_page=1"
ARCHIVE_URL = "https://github.com/uBlockOrigin/uBOL-home/archive/refs/tags/{tag}.tar.gz"
REQUIRED_RULESETS = {"ublock-filters", "easylist", "easyprivacy", "ublock-badware", "urlhaus-full"}


def install_ublock_origin_lite(target_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    tag = _latest_tag()
    with tempfile.TemporaryDirectory(prefix="cloakbrowser-ubol-") as tmp:
        tmpdir = Path(tmp)
        archive = tmpdir / "ubol.tar.gz"
        source_root = tmpdir / "source"
        _download_archive(tag, archive)
        source_root.mkdir()
        with tarfile.open(archive, "r:gz") as tar:
            _safe_extract_tar(tar, source_root)
        children = [path for path in source_root.iterdir() if path.is_dir()]
        if len(children) != 1:
            raise ValueError("Could not locate unpacked uBOL source directory")
        source_extension = children[0] / "chromium"
        if not (source_extension / "manifest.json").is_file():
            raise ValueError("uBOL Chromium extension is missing manifest.json")
        _copy_replace(source_extension, target_dir)
        _patch_defaults(target_dir, config)
    return _metadata(target_dir, tag)


def _latest_tag() -> str:
    request = urllib.request.Request(
        REPO_TAGS_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "cloakbrowser-agent-zero-plugin"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("GitHub tags API returned no uBOL tags")
    tag = payload[0].get("name") if isinstance(payload[0], dict) else ""
    if not tag:
        raise ValueError("GitHub tags API returned an invalid uBOL tag")
    return str(tag)


def _download_archive(tag: str, destination: Path) -> None:
    request = urllib.request.Request(
        ARCHIVE_URL.format(tag=tag),
        headers={"User-Agent": "cloakbrowser-agent-zero-plugin"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        destination.write_bytes(response.read())


def _safe_extract_tar(archive: tarfile.TarFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"Refusing to extract path outside target: {member.name}")
    try:
        archive.extractall(destination, filter="data")
    except TypeError:
        archive.extractall(destination)


def _patch_defaults(target_dir: Path, config: dict[str, Any]) -> None:
    manifest_path = target_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("key", None)
    rulesets = manifest.get("declarative_net_request", {}).get("rule_resources", [])
    available = {ruleset.get("id") for ruleset in rulesets}
    missing = REQUIRED_RULESETS.difference(available)
    if missing:
        raise ValueError(f"Required uBOL rulesets missing: {sorted(missing)}")
    enabled_ids = set(config.get("enabled_rulesets") or [])
    for ruleset in rulesets:
        ruleset["enabled"] = ruleset.get("id") in enabled_ids
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    config_path = target_dir / "js" / "config.js"
    mode_path = target_dir / "js" / "mode-manager.js"
    if config_path.is_file():
        text = config_path.read_text(encoding="utf-8")
        enabled = "[\n" + "".join(f"        '{item}',\n" for item in enabled_ids if item in available) + "    ]"
        text = text.replace("    enabledRulesets: [],", f"    enabledRulesets: {enabled},", 1)
        if config.get("strict_block_mode", True):
            text = text.replace(
                "    strictBlockMode: webextFlavor !== 'safari',",
                "    strictBlockMode: true,",
                1,
            )
        config_path.write_text(text, encoding="utf-8")
    if mode_path.is_file() and config.get("filtering_mode") == "complete":
        text = mode_path.read_text(encoding="utf-8")
        text = text.replace("userModes = { optimal: [ 'all-urls' ] },", "userModes = { complete: [ 'all-urls' ] },", 1)
        text = text.replace("complete: [],", "complete: [ 'all-urls' ],", 1)
        text = text.replace("optimal: [ 'all-urls' ],", "optimal: [],", 1)
        mode_path.write_text(text, encoding="utf-8")


def _copy_replace(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def _metadata(target_dir: Path, tag: str) -> dict[str, Any]:
    manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))
    return {
        "source": "uBlockOrigin/uBOL-home",
        "tag": tag,
        "path": str(target_dir),
        "manifest_name": manifest.get("name") or "",
        "manifest_version": manifest.get("version") or "",
    }
