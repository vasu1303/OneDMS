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

    async def upload_file(self, key: str, body: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    async def get_file_stream(self, key: str):
        response = await asyncio.to_thread(
            self.client.get_object,
            Bucket=self.bucket,
            Key=key
        )
        body = response["Body"]
        content_type = response.get("ContentType", "application/octet-stream")
        
        async def stream_generator():
            try:
                while True:
                    chunk = await asyncio.to_thread(body.read, 8192)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()
                
        return stream_generator(), content_type

    async def get_file_bytes(self, key: str) -> tuple[bytes, str]:
        response = await asyncio.to_thread(
            self.client.get_object,
            Bucket=self.bucket,
            Key=key,
        )
        body = response["Body"]
        content_type = response.get("ContentType", "application/octet-stream")
        try:
            data = await asyncio.to_thread(body.read)
            return data, content_type
        finally:
            body.close()

    async def delete_file(self, key: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.delete_object,
                Bucket=self.bucket,
                Key=key
            )
        except Exception:
            pass  # Best effort

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