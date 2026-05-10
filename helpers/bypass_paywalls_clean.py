from __future__ import annotations

import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from .chrome_store import extension_metadata, safe_extract_zip
from .config import BPC_SOURCE_URL, get_config


def install_bypass_paywalls_clean(
    target_dir: Path,
    source_url: str = BPC_SOURCE_URL,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = get_config({"bypass_paywalls_clean": config or {}})["bypass_paywalls_clean"]
    with tempfile.TemporaryDirectory(prefix="cloakbrowser-bpc-") as tmp:
        tmpdir = Path(tmp)
        archive = tmpdir / "bypass-paywalls-clean.zip"
        extracted = tmpdir / "extracted"
        _download(source_url, archive)
        safe_extract_zip(archive, extracted)
        root = _find_extension_root(extracted)
        if not root:
            raise ValueError("Bypass Paywalls Clean archive did not contain manifest.json")
        _configure_bpc(root, cfg)
        _replace_atomically(root, target_dir)

    metadata = extension_metadata(target_dir, source=source_url)
    metadata["install_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    metadata["source_url"] = source_url
    return metadata


def _configure_bpc(root: Path, config: dict[str, Any]) -> None:
    if config["opt_in_custom_sites"]:
        custom_manifest = root / "custom" / "manifest.json"
        if custom_manifest.is_file():
            shutil.copy2(custom_manifest, root / "manifest.json")
    background = root / "background.js"
    if background.is_file():
        _patch_background_defaults(
            background,
            opt_in_setcookie=config["opt_in_setcookie"],
            opt_in_update=config["opt_in_update"],
            suppress_optin_tab=all(
                [
                    config["opt_in_setcookie"],
                    config["opt_in_custom_sites"],
                    config["opt_in_update"],
                ]
            ),
        )


def _patch_background_defaults(
    background: Path,
    *,
    opt_in_setcookie: bool,
    opt_in_update: bool,
    suppress_optin_tab: bool,
) -> None:
    text = background.read_text(encoding="utf-8")
    text = _replace_once(text, "  optIn: false,\n", f"  optIn: {_js_bool(opt_in_setcookie)},\n")
    text = _replace_once(
        text, "  optInUpdate: true\n", f"  optInUpdate: {_js_bool(opt_in_update)}\n"
    )
    if suppress_optin_tab:
        text = _replace_once(
            text,
            "  if (!result.optInShown || !result.customShown || (!ext_chromium && !result.fetchShown)) {\n",
            "  if (false && (!result.optInShown || !result.customShown || (!ext_chromium && !result.fetchShown))) {\n",
        )
    background.write_text(text, encoding="utf-8")


def _replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected one BPC patch target, found {count}")
    return text.replace(old, new, 1)


def _js_bool(value: bool) -> str:
    return "true" if value else "false"


def _find_extension_root(extracted: Path) -> Path | None:
    expected = extracted / "bypass-paywalls-chrome-clean-master"
    if (expected / "manifest.json").is_file():
        return expected
    manifests = sorted(extracted.glob("**/manifest.json"))
    return manifests[0].parent if manifests else None


def _download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "cloakbrowser-agent-zero-plugin"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if not data:
        raise ValueError("Bypass Paywalls Clean download was empty")
    target.write_bytes(data)


def _replace_atomically(source: Path, target: Path) -> None:
    tmp_target = target.with_name(f".{target.name}.new")
    old_target = target.with_name(f".{target.name}.old")
    for path in (tmp_target, old_target):
        if path.exists():
            shutil.rmtree(path)
    shutil.copytree(source, tmp_target)
    if target.exists():
        target.rename(old_target)
    tmp_target.rename(target)
    if old_target.exists():
        shutil.rmtree(old_target)
