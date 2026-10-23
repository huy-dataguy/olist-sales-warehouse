"""Fetch the licensed public archive and enforce the reviewed immutable identity."""
import base64
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def auth_headers():
    """Kaggle requires authentication; credentials stay in the environment."""
    headers = {"User-Agent": "SalesDW-Portfolio/0.3 source-verification"}
    username, key = os.getenv("KAGGLE_USERNAME"), os.getenv("KAGGLE_KEY")
    if username and key:
        token = base64.b64encode(f"{username}:{key}".encode()).decode()
        headers["Authorization"] = "Basic " + token
    return headers


def main():
    manifest = json.loads((ROOT / "data/source-manifest.json").read_text())
    target = ROOT / manifest["local_artifact"]
    if target.exists():
        with target.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == manifest["sha256"], "Existing source differs; refusing overwrite"
        print("Pinned Olist archive already present; checksum verified.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".download")
    request = urllib.request.Request(manifest["download_url"], headers=auth_headers())
    try:
        response = urllib.request.urlopen(request, timeout=120)
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Kaggle returned HTTP {error.code} for the pinned archive. "
            "Export KAGGLE_USERNAME and KAGGLE_KEY from kaggle.com/settings before running `make source`."
        ) from error
    with response as source, temporary.open("xb") as output:
        digest, size = hashlib.sha256(), 0
        while part := source.read(1024*1024):
            output.write(part)
            digest.update(part)
            size += len(part)
            if size > manifest["bytes"]:
                raise RuntimeError("Unexpected source length; incomplete download retained for diagnosis")
    if digest.hexdigest() != manifest["sha256"] or size != manifest["bytes"]:
        raise RuntimeError("Source identity changed or access page returned. Review the publisher download; do not update checksum blindly.")
    temporary.rename(target)
    print("Pinned archive downloaded and verified:", size, "bytes")


if __name__ == "__main__":
    main()
