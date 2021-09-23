"""Client functions for accessing S3."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_request_signer import AwsRequestSigner

from .config import config

if TYPE_CHECKING:
    import httpx


class Bucket:
    """Interface for an S3 bucket.

    This class uses the AWS Signature Version 4 to authenticate the GET
    requests to the bucket. See
    https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-auth-using-authorization-header.html
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key

    def build_request(
        self, http_client: httpx.AsyncClient, key: str
    ) -> httpx.Request:
        url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
        signer = AwsRequestSigner(
            self.region, self.access_key_id, self.secret_access_key, "s3"
        )
        headers = signer.sign_with_headers("GET", url)
        return http_client.build_request("GET", url, headers=headers)

    async def get_object(
        self, http_client: httpx.AsyncClient, key: str
    ) -> httpx.Response:
        """Send an authorized GET request for an S3 object."""
        return await http_client.send(self.build_request(http_client, key))

    async def stream_object(
        self, http_client: httpx.AsyncClient, key: str
    ) -> httpx.Response:
        """Stream a response to a GET request for an S3 object."""
        return await http_client.send(
            self.build_request(http_client, key), stream=True
        )


class BucketDependency:
    def __init__(self) -> None:
        self.bucket = Bucket(
            bucket=config.s3_bucket,
            region=config.aws_region,
            access_key_id=config.aws_access_key_id.get_secret_value(),
            secret_access_key=config.aws_secret_access_key.get_secret_value(),
        )

    def __call__(self) -> Bucket:
        return self.bucket


bucket_dependency = BucketDependency()
