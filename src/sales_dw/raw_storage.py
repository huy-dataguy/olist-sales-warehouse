"""Content-addressed raw preservation with a real read-back checksum."""
import hashlib
import json
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from .config import ROOT, connect, settings, save_context


def client():
    cfg = settings()["s3"]
    return Minio(cfg["endpoint"], access_key=cfg["access_key"], secret_key=cfg["secret_key"], secure=False)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def preserve(run_id, *, local_artifact=None):
    manifest = json.loads((ROOT / "data/source-manifest.json").read_text())
    expected = manifest["sha256"]
    path = Path(local_artifact) if local_artifact is not None else ROOT / manifest["local_artifact"]
    cfg = settings()["s3"]
    key = f"source=olist/version=v2/sha256={expected}/brazilian-ecommerce-v2.zip"
    s3 = client()
    if not path.is_file():
        path = ROOT / "var" / "source-cache" / (expected + ".zip")
        path.parent.mkdir(parents=True, exist_ok=True)
        s3.fget_object(cfg["bucket"], key, str(path))
    actual = digest(path)
    if actual != expected:
        raise ValueError("Source checksum differs from pinned manifest")
    with connect() as conn:
        conn.execute("INSERT INTO ops.artifacts(artifact_sha256,source_system,source_version,object_bucket,object_key,content_bytes,state) VALUES(%s,'olist','v2',%s,%s,%s,'discovered') ON CONFLICT DO NOTHING",
                     (expected, cfg["bucket"], key, path.stat().st_size))
    try:
        stat = s3.stat_object(cfg["bucket"], key)
    except S3Error as exc:
        if exc.code not in {"NoSuchKey", "NoSuchObject"}:
            raise
        s3.fput_object(cfg["bucket"], key, str(path), metadata={"sha256": expected}, content_type="application/zip")
        stat = s3.stat_object(cfg["bucket"], key)
    if stat.size != path.stat().st_size:
        raise ValueError("Existing immutable object size mismatch")
    response = s3.get_object(cfg["bucket"], key)
    h = hashlib.sha256()
    try:
        for block in response.stream(1024 * 1024):
            h.update(block)
    finally:
        response.close()
        response.release_conn()
    if h.hexdigest() != expected:
        raise ValueError("Immutable raw GET checksum mismatch")
    with connect() as conn:
        conn.execute("UPDATE ops.artifacts SET state='preserved',preserved_at=coalesce(preserved_at,clock_timestamp()) WHERE artifact_sha256=%s", (expected,))
    save_context(run_id, archive=str(path), artifact_sha256=expected, object_key=key)
    return {"artifact_sha256": expected, "put_get_verified": True, "bytes": stat.size}
