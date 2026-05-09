from __future__ import annotations

import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from .chrome_store import extension_metadata, safe_extract_zip
from .config import BPC_SOURCE_URL


def install_bypass_paywalls_clean(target_dir: Path, source_url: str = BPC_SOURCE_URL) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cloakbrowser-bpc-") as tmp:
        tmpdir = Path(tmp)
        archive = tmpdir / "bypass-paywalls-clean.zip"
        extracted = tmpdir / "extracted"
        _download(source_url, archive)
        safe_extract_zip(archive, extracted)
        root = _find_extension_root(extracted)
        if not root:
            raise ValueError("Bypass Paywalls Clean archive did not contain manifest.json")
        _replace_atomically(root, target_dir)

    metadata = extension_metadata(target_dir, source=source_url)
    metadata["install_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    metadata["source_url"] = source_url
    return metadata


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
