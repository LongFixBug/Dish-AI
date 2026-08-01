"""Sync image datasets between local disk and S3-compatible storage.

Intended use:
    - Push local training data to S3/MinIO for durable storage.
    - Pull it back to a training machine before running ``ml.training.train``.

The script preserves the relative directory layout under a chosen root.
Example:
    data/images/train/pho_bo/a.jpg  ->  s3://bucket/datasets/train/pho_bo/a.jpg

Usage:
    uv run python scripts/sync_image_dataset.py push --root data/images/train
    uv run python scripts/sync_image_dataset.py pull --root data/images/train
    uv run python scripts/sync_image_dataset.py push --create-bucket
"""

from __future__ import annotations

import argparse
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import boto3
from botocore.exceptions import ClientError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = PROJECT_ROOT / "data" / "images" / "train"
DEFAULT_BUCKET = os.environ.get("DATASET_S3_BUCKET", "foodai-datasets")
DEFAULT_PREFIX = os.environ.get("DATASET_S3_PREFIX", "datasets/train")
DEFAULT_REGION = os.environ.get("DATASET_S3_REGION", "us-east-1")
DEFAULT_ENDPOINT_URL = os.environ.get("DATASET_S3_ENDPOINT_URL", "")
DEFAULT_ACCESS_KEY = os.environ.get("DATASET_S3_ACCESS_KEY_ID", "")
DEFAULT_SECRET_KEY = os.environ.get("DATASET_S3_SECRET_ACCESS_KEY", "")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass(frozen=True)
class SyncStats:
    uploaded: int = 0
    downloaded: int = 0
    skipped: int = 0


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def to_s3_key(prefix: str, root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    return str(PurePosixPath(prefix) / PurePosixPath(relative))


def iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def ensure_bucket(client, bucket: str, region: str, create_bucket: bool) -> None:
    try:
        client.head_bucket(Bucket=bucket)
        return
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code not in {"404", "NoSuchBucket", "NotFound"} or not create_bucket:
            raise
    kwargs: dict[str, object] = {"Bucket": bucket}
    if region != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {
            "LocationConstraint": region
        }
    client.create_bucket(**kwargs)


def push(root: Path, bucket: str, prefix: str, client, dry_run: bool) -> SyncStats:
    stats = SyncStats()
    for path in iter_files(root):
        key = to_s3_key(prefix, root, path)
        if dry_run:
            print(f"PUT  s3://{bucket}/{key}  <-  {path}")
            stats = SyncStats(uploaded=stats.uploaded + 1)
            continue
        client.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type_for(path)},
        )
        stats = SyncStats(uploaded=stats.uploaded + 1)
    return stats


def pull(root: Path, bucket: str, prefix: str, client, dry_run: bool) -> SyncStats:
    paginator = client.get_paginator("list_objects_v2")
    stats = SyncStats()
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix.rstrip('/')}/"):
        for entry in page.get("Contents", []):
            key = entry["Key"]
            rel = PurePosixPath(key).relative_to(PurePosixPath(prefix)).as_posix()
            target = root / Path(*PurePosixPath(rel).parts)
            if dry_run:
                print(f"GET  s3://{bucket}/{key}  ->  {target}")
                stats = SyncStats(downloaded=stats.downloaded + 1)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(target))
            stats = SyncStats(downloaded=stats.downloaded + 1)
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync image datasets with S3/MinIO")
    parser.add_argument("direction", choices={"push", "pull"})
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Local dataset root to sync",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=DEFAULT_BUCKET,
        help="S3 bucket name",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=DEFAULT_PREFIX,
        help="S3 prefix inside the bucket",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=DEFAULT_REGION,
        help="S3 region",
    )
    parser.add_argument(
        "--endpoint-url",
        type=str,
        default=DEFAULT_ENDPOINT_URL or None,
        help="S3-compatible endpoint for MinIO/local",
    )
    parser.add_argument(
        "--access-key-id",
        type=str,
        default=DEFAULT_ACCESS_KEY or None,
        help="Access key for the S3-compatible storage",
    )
    parser.add_argument(
        "--secret-access-key",
        type=str,
        default=DEFAULT_SECRET_KEY or None,
        help="Secret key for the S3-compatible storage",
    )
    parser.add_argument(
        "--create-bucket",
        action="store_true",
        help="Create the bucket if it does not exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned transfers without changing storage",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    client_options: dict[str, object] = {
        "region_name": args.region,
    }
    if args.endpoint_url:
        client_options["endpoint_url"] = args.endpoint_url
    if args.access_key_id:
        client_options["aws_access_key_id"] = args.access_key_id
    if args.secret_access_key:
        client_options["aws_secret_access_key"] = args.secret_access_key

    client = boto3.client("s3", **client_options)
    if args.create_bucket:
        ensure_bucket(client, args.bucket, args.region, create_bucket=True)

    root = args.root if args.root.is_absolute() else PROJECT_ROOT / args.root
    if args.direction == "push" and not root.exists():
        raise SystemExit(f"Local root does not exist: {root}")

    if args.direction == "push":
        stats = push(root, args.bucket, args.prefix, client, args.dry_run)
        print(f"Uploaded {stats.uploaded} files")
    else:
        root.mkdir(parents=True, exist_ok=True)
        stats = pull(root, args.bucket, args.prefix, client, args.dry_run)
        print(f"Downloaded {stats.downloaded} files")


if __name__ == "__main__":
    main()
