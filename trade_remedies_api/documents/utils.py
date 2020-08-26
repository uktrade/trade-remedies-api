import logging
import os

import boto3
from pathlib import Path
from django.utils import timezone
from django.conf import settings
from django.http import StreamingHttpResponse
from wsgiref.util import FileWrapper


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
    """
    Derive the upload path into S3.
    This is made of the root directory, partitioned into the case id.
    Current upload time is appended to the file name.
    """
    filename_base, filename_ext = os.path.splitext(filename)
    _now = timezone.now().strftime("%Y%m%d%H%M%S")
    _filename = f"{filename_base}_{_now}{filename_ext}"
    path = Path(settings.S3_DOCUMENT_ROOT_DIRECTORY)
    if hasattr(instance, "case") and instance.case:
        path /= str(instance.case.id)
    path /= _filename
    return str(path)


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
