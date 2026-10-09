import asyncio
from urllib.parse import urlsplit

import boto3
from botocore.config import Config

from app.core.config import Settings


class ObjectStorage:
    def __init__(self, settings: Settings):
        endpoint = urlsplit(settings.AWS_ENDPOINT_URL_S3)
        if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username:
            raise ValueError("An HTTPS storage endpoint is required")
        self.bucket = settings.S3_BUCKET_NAME
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_ENDPOINT_URL_S3,
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID.get_secret_value(),
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY.get_secret_value(),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=min(2, settings.DEPENDENCY_TIMEOUT_SECONDS / 4),
                read_timeout=min(2, settings.DEPENDENCY_TIMEOUT_SECONDS / 4),
                retries={"mode": "standard", "total_max_attempts": 2},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    async def check(self) -> None:
        await asyncio.to_thread(self.client.head_bucket, Bucket=self.bucket)

    async def close(self) -> None:
        await asyncio.to_thread(self.client.close)


def create_storage(settings: Settings) -> ObjectStorage | None:
    if not all((
        settings.AWS_ENDPOINT_URL_S3,
        settings.AWS_REGION,
        settings.AWS_ACCESS_KEY_ID.get_secret_value(),
        settings.AWS_SECRET_ACCESS_KEY.get_secret_value(),
        settings.S3_BUCKET_NAME,
    )):
        return None
    return ObjectStorage(settings)