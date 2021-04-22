"""Perform AV Scan of a document stored in S3.

Invoke a virus scan of a document stored as an S3 object using this module's
interface method  `virus_scan_document`, providing a document ID, e.g:

    from documents.av_scan import virus_scan_document
    virus_scan_document('fb5fafa4-c9e8-4a75-92a0-5ecd4eb54164')

This module uses `S3StreamingBodyWrapper` to arbitrate the scan of an object
on S3 using an AV Service specified by the Django setting `AV_SERVICE_URL`. We
stream chunks of the specified S3 object to the service and updated the Document
model depending on the result.

There are a few things that can happen when a document is AV scanned:
- Scan passes, all is well:
  `Document.virus_scanned_at` date set to now, `Document.safe` flag set to True.

- Document has already been scanned:
  Identified by `Document.virus_scanned_at` date already set. Log and ignore.

- Scan fails because document does not exist:
  Log that the document could not be found.

- Scan fails because the AV service is not configured or failed to respond:
  Log that scan attempt failed. No Document attributes are set, this will
  ensure a rescan is invoked when TR is reconfigured/restarted or the AV
  service becomes available again.

- Scan fails because document contains malware or document is a password
  protected archive:
  Log that the scan identified malware, `Document.virus_scanned_at` date
  set to now, `Document.safe` flag set to False and `Document.av_reason`
  set to th AV response reason e.g. `Eicar-Test-Signature`.

- Scan fails because document is too large
  Log that the scan failed due HTTP 413, `Document.virus_scanned_at` date
  set to now, `Document.safe` flag set to False and `Document.av_reason`
  set to 'File Too Large'
"""
from contextlib import closing
from logging import getLogger

from botocore.exceptions import ClientError
import requests
from django.conf import settings
from django.utils.timezone import now
from django_pglocks import advisory_lock
from requests_toolbelt.multipart.encoder import MultipartEncoder
from .utils import s3_client
from .models import Document

logger = getLogger(__name__)


class AlreadyScannedError(Exception):
    """Raised when document has already been scanned."""


class BadConfigError(Exception):
    """Raised when AV service not configured."""


class MalwareDetectedError(Exception):
    """Raised when AV service detects malware or password protected archive."""
    av_reason = "unknown"


class S3StreamingBodyWrapper:
    """S3 Object wrapper.

    S3 Object wrapper that plays nice with streamed multipart/form-data.
    """
    def __init__(self, s3_obj, name):
        """Init wrapper

        Get S3 object body and content size from s3 object.

        :param (dict) s3_obj: S3 client response object.
        :param (str) name: File name.
        """
        self.name = name
        self.body = s3_obj["Body"]
        self.content_type = s3_obj["ContentType"]
        self.total_length = self._remaining_bytes = s3_obj["ContentLength"]
        self.logged = set()
        logger.info(f"Streaming {self.name}: {self.total_length} bytes")

    def read(self, amt=-1):
        """Read specified number of bytes.

        Read specified number of bytes and decrease remaining bytes to read.

        :param (int) amt: Amount of bytes to read. If not specified, boto
          default bytes read (typically 8192).
        :returns (bytes): content bytes read.
        """
        content = self.body.read(amt)
        self._remaining_bytes -= len(content)
        self.log_progress()
        return content

    def log_progress(self):
        """Log progress.

        Log progress for each 10% increment of self.total_length read.
        """
        completed_pct = int(100 - (self._remaining_bytes/self.total_length * 100))
        if completed_pct % 10:
            return
        if completed_pct not in self.logged:
            self.logged.add(completed_pct)
            logger.info(f"{self.name}: AV check {completed_pct}% complete")

    def __len__(self):
        """Return remaining bytes.

        Returns remaining bytes yet to be read. Requests library expects this to
        return the number of unread bytes (rather than the total length of the
        stream).

        :returns (int): Remaining bytes to read.
        """
        return self._remaining_bytes


def virus_scan_document(document_pk: str):
    """Virus scans an uploaded document.

    Instigate virus scan of a document with the AV Service. This is intended
    to be invoked from a Celery worker/beat asynchronously (in a local dev
    environment will be run synchronously within the Django process). We use a
    django_pglocks.advisory_lock context manager to soft-lock the document.

    This task will arbitrate the streaming of the document from S3 to the
    anti-virus service and on completion update the document model accordingly.

    :param (str) document_pk: Document primary key.
    """
    with advisory_lock(f"av-scan-{document_pk}"):
        try:
            document = Document.objects.get(pk=document_pk)
            _process_document(document)
        except Document.DoesNotExist:
            logger.error(f"AV scan failed: nonexistent document '{document_pk}'")
        except (BadConfigError, ClientError) as e:
            logger.error(f"AV scan failed: {e}")
        except AlreadyScannedError as e:
            logger.info(f"{e}")
        except MalwareDetectedError as e:
            document.virus_scanned_at = now()
            document.safe = False
            document.av_reason = e.av_reason
            document.save()
        except requests.exceptions.RequestException as e:
            logger.error(f"AV scan failed for '{document_pk}': {e}")
            document.av_reason = e
            if e.response is not None and e.response.status_code == 413:
                # Object too big, mark as scanned and give up
                document.virus_scanned_at = now()
                document.safe = False
            # If not 413 it's some other connectivity issue which could be
            # ephemeral, we will let beat processing have another try
            document.save()
        else:
            # All good
            document.virus_scanned_at = now()
            document.safe = True
            document.av_reason = "passed"
            document.save()


def _process_document(document):
    """Process virus scan.

    Invokes `_scan_s3_object` to arbitrate the scan of a document on S3 using
    the AV Service. `_scan_s3_object` may raise for status or request connection
    issues, which must be handled by caller of this method.

    :param (Document) document: Document model.
    :raises (BadConfigError): If AV service not configured.
    :raises (AlreadyScannedError): If document already scanned.
    """
    if not settings.AV_SERVICE_URL:
        raise BadConfigError(
            f"Cannot scan document with ID {document.id}, "
            "AV_SERVICE_URL not set"
        )
    if document.virus_scanned_at:
        msg = (f"Document scan already performed for '{document.id}' "
               f"on {document.virus_scanned_at}"
               )
        raise AlreadyScannedError(msg)
    _scan_s3_object(document.name, document.s3_bucket, document.s3_key)


def _scan_s3_object(name, bucket, key):
    """Virus scan an S3 object.

    Given a document name, S3 bucket and S3 object key invoke a scan
    of the S3 object's response body. Uses `contextlib.closing` to close
    response body implicitly on completion.

    :param (str) name: document name.
    :param (str) bucket: S3 bucket name.
    :param (str) key: S3 key.
    :raises (ClientError): If any s3_client issues.
    """
    response = s3_client().get_object(Bucket=bucket, Key=key)
    with closing(response["Body"]):
        _scan_raw_file(S3StreamingBodyWrapper(response, name))


def _scan_raw_file(file_object):
    """Virus scan using S3StreamingBodyWrapper object.

    Given a S3StreamingBodyWrapper object invokes a request to the AV Service
    using HTTP Basic Auth. See https://github.com/uktrade/dit-clamav-rest for
    AV Service details.

    :param (S3StreamingBodyWrapper) file_object: file like object.
    """
    multipart_fields = {
        "file": (
            file_object.name,
            file_object,
            file_object.content_type,
        )
    }
    encoder = MultipartEncoder(fields=multipart_fields)
    response = requests.post(
        settings.AV_SERVICE_URL,
        data=encoder,
        auth=(settings.AV_SERVICE_USERNAME, settings.AV_SERVICE_PASSWORD),
        headers={"Content-Type": encoder.content_type},
    )
    response.raise_for_status()
    report = response.json()
    if report.get("malware", True):
        reason = report.get("reason", "not specified")
        exc = MalwareDetectedError(f"File identified as malware: {reason}")
        exc.reason = reason
        raise exc
