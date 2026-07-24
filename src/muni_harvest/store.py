"""S3-compatible object storage (Cloudflare R2 / Backblaze B2).

Free egress makes R2/B2 the right home for the corpus (vs S3's re-read tax). Used by
the future gated download stage to persist documents; wired now so the bucket +
credentials are validated before we depend on them. Requires the `s3` extra.

Credentials come from .env / environment (never committed):
  S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET
"""

from __future__ import annotations

import os
from pathlib import Path

from .config import load_env


def _client():
    load_env()
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:  # noqa: BLE001
        raise SystemExit("[ERR] boto3 not installed. Run: pip install -e \".[s3]\"") from exc
    missing = [k for k in ("S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
               if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"[ERR] missing storage credentials: {', '.join(missing)} "
                         f"(set them in .env)")
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("S3_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def bucket_name() -> str:
    load_env()
    return os.environ.get("S3_BUCKET", "muni-harvest")


def ensure_bucket() -> str:
    """Create the bucket if it doesn't exist. Returns the bucket name."""
    cli = _client()
    name = bucket_name()
    existing = [b["Name"] for b in cli.list_buckets().get("Buckets", [])]
    if name not in existing:
        cli.create_bucket(Bucket=name)
        print(f"[OK] created bucket '{name}'")
    else:
        print(f"[OK] bucket '{name}' already exists")
    return name


def ping() -> bool:
    """Validate credentials + endpoint by listing buckets."""
    cli = _client()
    buckets = [b["Name"] for b in cli.list_buckets().get("Buckets", [])]
    print(f"[OK] connected to {os.environ['S3_ENDPOINT_URL']} "
          f"| buckets: {buckets or '(none yet)'} | target: {bucket_name()}")
    return True


def exists(key: str) -> bool:
    cli = _client()
    try:
        cli.head_object(Bucket=bucket_name(), Key=key)
        return True
    except Exception:  # noqa: BLE001
        return False


def put_file(local: Path, key: str) -> None:
    _client().upload_file(str(local), bucket_name(), key)


def get_file(key: str, local: Path) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    _client().download_file(bucket_name(), key, str(local))


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "ping"
    if cmd == "ping":
        ping()
    elif cmd == "ensure":
        ensure_bucket()
    else:
        raise SystemExit(f"[ERR] unknown store command '{cmd}' (ping|ensure)")
