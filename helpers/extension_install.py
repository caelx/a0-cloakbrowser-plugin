from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from time import gmtime, strftime
from typing import Any


def atomic_install_extension(
    source: Path,
    target: Path,
    *,
    source_name: str,
    config: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not (source / "manifest.json").is_file():
        raise ValueError(f"{source_name} manifest missing before install")
    new_target = target.with_name(f".{target.name}.new")
    old_target = target.with_name(f".{target.name}.old")
    for path in (new_target, old_target):
        if path.exists():
            shutil.rmtree(path)
    try:
        shutil.copytree(source, new_target)
        if not (new_target / "manifest.json").is_file():
            raise ValueError(f"{source_name} manifest missing after staging")
        if target.exists():
            target.rename(old_target)
        new_target.rename(target)
        metadata = extension_metadata_with_hashes(
            target,
            source=source_name,
            config=config,
            extra=extra,
        )
        if old_target.exists():
            shutil.rmtree(old_target)
        return metadata
    except Exception:
        if target.exists() and not (target / "manifest.json").is_file():
            shutil.rmtree(target)
        if old_target.exists() and not target.exists():
            old_target.rename(target)
        if new_target.exists():
            shutil.rmtree(new_target)
        raise


def extension_metadata_with_hashes(
    extension_dir: Path,
    *,
    source: str,
    config: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_path = extension_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = {
        "source": source,
        "path": str(extension_dir),
        "manifest_name": manifest.get("name") or "",
        "manifest_version": manifest.get("version") or "",
        "manifest_manifest_version": manifest.get("manifest_version") or "",
        "permissions": manifest.get("permissions") or [],
        "host_permissions": manifest.get("host_permissions") or [],
        "sha256": hash_tree(extension_dir),
        "config_hash": hash_json(config or {}),
        "installed_at": strftime("%Y-%m-%dT%H:%M:%SZ", gmtime()),
    }
    payload.update(extra or {})
    return payload


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def hash_json(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()
