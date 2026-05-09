import zipfile

import pytest

from helpers.chrome_store import crx_zip_payload, safe_extract_zip


def test_crx_zip_payload_accepts_plain_zip(tmp_path):
    archive = tmp_path / "plain.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.json", "{}")

    assert crx_zip_payload(archive.read_bytes()).startswith(b"PK")


def test_safe_extract_zip_blocks_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escape.txt", "bad")

    with pytest.raises(ValueError):
        safe_extract_zip(archive, tmp_path / "out")
