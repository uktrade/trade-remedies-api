import logging
import os

import boto3
from django.conf import settings
from django.http import StreamingHttpResponse


logger = logging.getLogger(__name__)


class S3Wrapper(object):
    _s3_client = None

    @classmethod
    def get_client(cls):
        if not cls._s3_client:
            logger.info("Instantiating S3 client")
            cls._s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
        return cls._s3_client


def s3_client():
    return S3Wrapper.get_client()


def upload_document_to(instance, filename):
    """NOT USED.

    This method was originally referenced in a migration and as such has to kept around.
    See https://docs.djangoproject.com/en/2.2/topics/migrations/#historical-models
    """


def stream_s3_file_download(s3_bucket, s3_key, filename=None):
    """
    Send a file back from s3 as a streamed response
    :param s3_bucket: S3 Bucket name
    :param s3_key: Bucket key (path/filename)
    :param filename: Optional name of file to return. Will be derived from key if not provided
    :return: A StreamingHttpResponse streaming the file
    """

    def generate_file(result):
        for chunk in iter(lambda: result["Body"].read(settings.STREAMING_CHUNK_SIZE), b""):
            yield chunk

    s3 = s3_client()
    s3_response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
    if filename is None:
        _, filename = os.path.split(s3_key)
    _kwargs = {}
    if s3_response.get("ContentType"):
        _kwargs["content_type"] = s3_response["ContentType"]
    response = StreamingHttpResponse(generate_file(s3_response), **_kwargs)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
