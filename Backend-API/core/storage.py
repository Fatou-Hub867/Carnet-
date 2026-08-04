import uuid
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError

from core.config import settings

# Objects are private by default: we store the object key in the database
# and always hand out short-lived presigned URLs on read, never a public URL.
_s3_client = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint_url,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
)


def upload_file(file_bytes: bytes, filename: str, content_type: str) -> str:
    key = f"{uuid.uuid4()}-{filename}"
    _s3_client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key


def _content_disposition(filename: str) -> str:
    """RFC 6266: an ASCII fallback for old clients plus a UTF-8 filename* for
    everyone else, so accented filenames (fréquent in this app) still work."""
    filename = filename.replace("\r", "").replace("\n", "").replace('"', "")
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "document"
    return (
        f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"
    )


def get_file_url(
    key: str, expires_in: int = 3600, download_filename: str | None = None
) -> str:
    """A plain URL renders inline when the browser supports the content type
    (PDF, images). Passing `download_filename` adds a presigned
    Content-Disposition override so the same stored object can also be
    fetched as a forced download with a human-readable name — no need to
    store the file twice."""
    params = {"Bucket": settings.s3_bucket_name, "Key": key}
    if download_filename:
        params["ResponseContentDisposition"] = _content_disposition(download_filename)
    return _s3_client.generate_presigned_url(
        "get_object", Params=params, ExpiresIn=expires_in
    )


def original_filename_from_key(key: str) -> str:
    """upload_file() always prefixes with a 36-char uuid4() + '-' (fixed
    width, RFC 4122), so the original filename is recoverable by position
    even if the filename itself contains hyphens — unlike a naive split()."""
    return key[37:]


def delete_file(key: str) -> None:
    _s3_client.delete_object(Bucket=settings.s3_bucket_name, Key=key)


def ensure_bucket_exists() -> None:
    """Create the storage bucket if it isn't there yet. Idempotent, called once
    at app startup so a fresh MinIO/S3 target works without manual provisioning.

    If the bucket already exists (including when it's pre-provisioned and we lack
    CreateBucket rights), head_bucket succeeds and we do nothing. A 403 or any
    error other than 'missing' is re-raised so a real misconfiguration surfaces.
    """
    try:
        _s3_client.head_bucket(Bucket=settings.s3_bucket_name)
        return
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code not in ("404", "NoSuchBucket"):
            raise

    # us-east-1 must not be passed as a LocationConstraint (AWS quirk); MinIO and
    # the default region take the plain form.
    if settings.s3_region and settings.s3_region != "us-east-1":
        _s3_client.create_bucket(
            Bucket=settings.s3_bucket_name,
            CreateBucketConfiguration={"LocationConstraint": settings.s3_region},
        )
    else:
        _s3_client.create_bucket(Bucket=settings.s3_bucket_name)
