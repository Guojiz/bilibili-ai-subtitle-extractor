"""Optional Backblaze B2 upload for extracted transcript artifacts.

The integration uses Backblaze's S3-compatible API through boto3.  boto3 is
loaded only when an upload is requested, so the subtitle extractor keeps its
stdlib-only default path.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class B2Config:
    endpoint_url: str
    bucket: str
    key_id: str
    application_key: str
    region: str = "us-west-004"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "B2Config":
        values = os.environ if env is None else env
        required = {
            "B2_ENDPOINT_URL": values.get("B2_ENDPOINT_URL", ""),
            "B2_BUCKET": values.get("B2_BUCKET", ""),
            "B2_KEY_ID": values.get("B2_KEY_ID", ""),
            "B2_APPLICATION_KEY": values.get("B2_APPLICATION_KEY", ""),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError("Missing Backblaze configuration: " + ", ".join(missing))
        return cls(
            endpoint_url=required["B2_ENDPOINT_URL"].rstrip("/"),
            bucket=required["B2_BUCKET"],
            key_id=required["B2_KEY_ID"],
            application_key=required["B2_APPLICATION_KEY"],
            region=values.get("B2_REGION", "us-west-004"),
        )


def object_key(prefix: str, filename: str, payload: bytes) -> str:
    """Create a stable, collision-resistant key without exposing the source URL."""
    clean_prefix = prefix.strip("/") or "transcripts"
    clean_name = Path(filename).name.replace(" ", "-") or "transcript.txt"
    digest = hashlib.sha256(payload).hexdigest()[:12]
    return f"{clean_prefix}/{digest}-{clean_name}"


def upload_bytes(
    payload: bytes,
    *,
    filename: str,
    content_type: str,
    metadata: Mapping[str, str],
    prefix: str = "transcripts",
    config: B2Config | None = None,
    client: Any | None = None,
) -> dict[str, str]:
    """Upload one artifact and return an inspectable receipt.

    ``client`` is injectable so tests never require credentials or network.
    """
    cfg = config or B2Config.from_env()
    if client is None:
        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Backblaze upload requires boto3: python -m pip install boto3"
            ) from exc
        client = boto3.client(
            "s3",
            endpoint_url=cfg.endpoint_url,
            aws_access_key_id=cfg.key_id,
            aws_secret_access_key=cfg.application_key,
            region_name=cfg.region,
        )

    key = object_key(prefix, filename, payload)
    safe_metadata = {str(k): str(v)[:2000] for k, v in metadata.items() if v is not None}
    client.put_object(
        Bucket=cfg.bucket,
        Key=key,
        Body=payload,
        ContentType=content_type,
        Metadata=safe_metadata,
    )
    return {
        "provider": "Backblaze B2",
        "bucket": cfg.bucket,
        "key": key,
        "endpoint": cfg.endpoint_url,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }

