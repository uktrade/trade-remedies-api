import boto3
from contextlib import closing
from logging import getLogger

import requests
from django.conf import settings
from django.utils.timezone import now
from django_pglocks import advisory_lock
from requests_toolbelt.multipart.encoder import MultipartEncoder
from .utils import s3_client
from .models import Document

logger = getLogger(__name__)


class S3StreamingBodyWrapper:
    """S3 Object wrapper that plays nice with streamed multipart/form-data."""

    def __init__(self, s3_obj, name):
        """Init wrapper, and grab interesting bits from s3 object."""
        self._obj = s3_obj
        self._body = s3_obj["Body"]
        self.total_length = self._remaining_bytes = s3_obj["ContentLength"]
        self.name = name
        self.logged = set()
        logger.info(f"Streaming {self.name}: {self.total_length} bytes")

    def read(self, amt=-1):
        """Read given amount of bytes, and decrease remaining len."""
        content = self._body.read(amt)
        self._remaining_bytes -= len(content)
        self.log_progress()
        return content

    def log_progress(self):
        completed_pct = int(100 - (self._remaining_bytes/self.total_length * 100))
        if completed_pct % 10:
            return
        if completed_pct not in self.logged:
            self.logged.add(completed_pct)
            logger.info(f"{self.name}: AV check {completed_pct}% complete")

    def __len__(self):
        """Return remaining bytes, that have not been read yet.
        requests-toolbelt expects this to return the number of unread bytes (rather than
        the total length of the stream).
        """
        return self._remaining_bytes


# TODO - Remove cruft
def get_s3_client():
    # DEPRECATED
    s3 = boto3.client("s3")
    return s3


def virus_scan_document(document_pk: str):
    """Virus scans an uploaded document.
    This is intended to be run in the thread pool executor. The file is streamed from S3 to the
    anti-virus service.
    Any errors are logged and sent to Sentry.
    """
    try:
        with advisory_lock(f"av-scan-{document_pk}"):
            _process_document(document_pk)
    except VirusScanException as e:
        logger.critical(f"{e}")
    except Document.DoesNotExist:
        logger.error(f"Cannot AV scan nonexistent document with id: {document_pk}")


def _process_document(document_pk: str):
    """Virus scans an uploaded document."""
    if not settings.AV_SERVICE_URL:
        raise VirusScanException(
            f"Cannot scan document with ID {document_pk}; AV service URL not" f"configured"
        )
    doc = Document.objects.get(pk=document_pk)
    if doc.virus_scanned_at is not None and doc.safe is not None:
        logger.info(
            f"Skipping scan of doc:{document_pk}, already performed " f"on {doc.virus_scanned_at}"
        )
        return
    try:
        is_file_clean = _scan_s3_object(doc.name, doc.s3_bucket, doc.s3_key)
        if is_file_clean is not None:
            doc.virus_scanned_at = now()
            doc.safe = is_file_clean
            doc.save()
    except Exception as e:
        logger.critical(f"Failed to AV scan document: {e}")
        doc.safe = None
        doc.virus_scanned_at = None
        doc.save()


def _scan_s3_object(original_filename, bucket, key):
    """Virus scans a file stored in S3."""
    _client = s3_client()
    response = _client.get_object(Bucket=bucket, Key=key)
    with closing(response["Body"]):
        return _scan_raw_file(
            original_filename,
            S3StreamingBodyWrapper(response, original_filename),
            response["ContentType"],
        )


def _scan_raw_file(filename, file_object, content_type):
    """Virus scans a file-like object."""
    multipart_fields = {
        "file": (
            filename,
            file_object,
            content_type,
        )
    }
    encoder = MultipartEncoder(fields=multipart_fields)

    response = requests.post(
        # Assumes HTTP Basic auth in URL
        # see: https://github.com/uktrade/dit-clamav-rest
        settings.AV_SERVICE_URL,
        data=encoder,
        auth=(settings.AV_SERVICE_USERNAME, settings.AV_SERVICE_PASSWORD),
        headers={"Content-Type": encoder.content_type},
    )
    response.raise_for_status()
    report = response.json()
    if "malware" not in report:
        raise VirusScanException(f"File identified as malware: {response.text}")
    return not report.get("malware")


# TODO - Move to top
class VirusScanException(Exception):
    """Exceptions raised when scanning documents for viruses."""
