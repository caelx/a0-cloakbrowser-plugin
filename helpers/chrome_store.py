from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

EXTENSION_ID_RE = re.compile(r"^[a-p]{32}$")
CHROME_VERSION_RE = re.compile(r"(\d+(?:\.\d+){0,3})")
DEFAULT_CHROME_PRODVERSION = "140.0.0.0"
WEB_STORE_DOWNLOAD_URL = (
    "https://clients2.google.com/service/update2/crx"
    "?response=redirect"
    "&prod=chromecrx"
    "&prodversion={prodversion}"
    "&acceptformat=crx2,crx3"
    "&x=id%3D{extension_id}%26installsource%3Dondemand%26uc"
)


def install_chrome_web_store_extension(extension_id: str, target_dir: Path) -> dict[str, Any]:
    extension_id = str(extension_id or "").strip()
    if not EXTENSION_ID_RE.fullmatch(extension_id):
        raise ValueError(f"Invalid Chrome Web Store extension id: {extension_id}")

    with tempfile.TemporaryDirectory(prefix="cloakbrowser-crx-") as tmp:
        tmpdir = Path(tmp)
        archive_path = tmpdir / f"{extension_id}.crx"
        payload_path = tmpdir / f"{extension_id}.zip"
        extracted_path = tmpdir / "extracted"
        _download_crx(extension_id, archive_path)
        payload_path.write_bytes(crx_zip_payload(archive_path.read_bytes()))
        safe_extract_zip(payload_path, extracted_path)
        if not (extracted_path / "manifest.json").is_file():
            raise ValueError("Downloaded extension did not contain manifest.json")
        _replace_dir(extracted_path, target_dir)

    return extension_metadata(target_dir, source=f"chrome-web-store:{extension_id}")


def crx_zip_payload(data: bytes) -> bytes:
    if data.startswith(b"PK"):
        return data
    if data[:4] != b"Cr24":
        raise ValueError("Downloaded package is not a CRX or ZIP archive")
    version = int.from_bytes(data[4:8], "little")
    if version == 2:
        public_key_len = int.from_bytes(data[8:12], "little")
        signature_len = int.from_bytes(data[12:16], "little")
        offset = 16 + public_key_len + signature_len
    elif version == 3:
        header_len = int.from_bytes(data[8:12], "little")
        offset = 12 + header_len
    else:
        raise ValueError(f"Unsupported CRX version: {version}")
    payload = data[offset:]
    if not payload.startswith(b"PK"):
        raise ValueError("CRX payload did not contain a ZIP archive")
    return payload


def safe_extract_zip(archive_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    root = target_dir.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            destination = (target_dir / member.filename).resolve()
            if destination != root and root not in destination.parents:
                raise ValueError(f"Unsafe path in extension archive: {member.filename}")
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)


def extension_metadata(extension_dir: Path, *, source: str = "") -> dict[str, Any]:
    import json

    manifest_path = extension_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "source": source,
        "path": str(extension_dir),
        "manifest_name": manifest.get("name") or "",
        "manifest_version": manifest.get("version") or "",
        "manifest_manifest_version": manifest.get("manifest_version") or "",
        "permissions": manifest.get("permissions") or [],
        "host_permissions": manifest.get("host_permissions") or [],
    }


def _download_crx(extension_id: str, archive_path: Path) -> None:
    prodversion = _detect_chrome_prodversion()
    url = WEB_STORE_DOWNLOAD_URL.format(extension_id=extension_id, prodversion=prodversion)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{prodversion} Safari/537.36"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Chrome Web Store download failed with HTTP {exc.code}") from exc
    if not data:
        raise ValueError("Chrome Web Store returned an empty extension package")
    archive_path.write_bytes(data)


def _detect_chrome_prodversion() -> str:
    for command in (("google-chrome", "--version"), ("chromium", "--version"), ("chromium-browser", "--version")):
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            continue
        match = CHROME_VERSION_RE.search(" ".join([result.stdout, result.stderr]))
        if match:
            parts = match.group(1).split(".")
            return ".".join((parts + ["0", "0", "0", "0"])[:4])
    return DEFAULT_CHROME_PRODVERSION


def _replace_dir(source: Path, target: Path) -> None:
    tmp_target = target.with_name(f".{target.name}.tmp")
    if tmp_target.exists():
        shutil.rmtree(tmp_target)
    if target.exists():
        shutil.copytree(target, tmp_target)
        shutil.rmtree(target)
        shutil.rmtree(tmp_target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
