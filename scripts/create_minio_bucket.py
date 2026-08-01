#!/usr/bin/env python
import boto3
from botocore.exceptions import ClientError

from zeroi.config import settings


def main() -> None:
    if settings.artifact_backend != "s3":
        print("ARTIFACT_BACKEND is not s3; skipping bucket creation")
        return

    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )

    try:
        client.head_bucket(Bucket=settings.s3_bucket)
        print(f"bucket already exists: {settings.s3_bucket}")
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)
        print(f"created bucket: {settings.s3_bucket}")


if __name__ == "__main__":
    main()
