import uuid
import mimetypes
import logging
from django.utils import timezone
from django.db import models
from django.db.models import Q
from django.conf import settings
from opensearchpy.exceptions import NotFoundError
from core.base import BaseModel, SimpleBaseModel
from functools import singledispatch
from core.opensearch import get_open_search, OSWrapperError
from cases.models import get_case
from organisations.models import get_organisation
from .constants import (
    INVALID_FILE_EXTENSIONS,
    SEARCH_FIELD_MAP,
    INDEX_STATE_NOT_INDEXED,
    INDEX_STATE_UNKNOWN_TYPE,
    INDEX_STATE_INDEX_FAIL,
    INDEX_STATE_FULL_INDEX,
    INDEX_STATES,
)
from .utils import s3_client
from .exceptions import InvalidFile
from .fields import S3FileField
from .tasks import checksum_document, index_document
from .parsers import parsers

# initialise the mimetypes module
mimetypes.init()

logger = logging.getLogger(__name__)


@singledispatch
def get_document(document):
    """
    A single dispatch to return a document from either a document instance or
    the document id.
    """
    return document


@get_document.register(str)
@get_document.register(uuid.UUID)  # noqa
def _(document):
    return Document.objects.get(id=document)


class DocumentManager(models.Manager):
    @staticmethod
    def open_search(
        query,
        case=None,
        confidential_status=None,
        organisation=None,
        user_type=None,
        **kwargs,  # noqa
    ):
        case = get_case(case)
        organisation = get_organisation(organisation)
        if isinstance(query, dict):
            _query = query
        else:
            _query = {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["name^2", "content"],
                                "type": "phrase_prefix",
                            }
                        }
                    ]
                }
            }
            if case:
                _query["bool"].setdefault("filter", [])
                _query["bool"]["filter"].append({"match": {"case_id": case.id}})
            if confidential_status is not None:
                _query["bool"].setdefault("filter", [])
                _query["bool"]["filter"].append({"term": {"confidential": confidential_status}})
            if organisation:
                _query["bool"].setdefault("filter", [])
                _query["bool"]["filter"].append(
                    {"match": {"organisation": {"id": str(organisation.id)}}}
                )
            if user_type in ("TRA", "PUB"):
                _query["bool"].setdefault("filter", [])
                _query["bool"]["filter"].append({"match": {"user_type": user_type}})
        try:
            client = get_open_search()
        except OSWrapperError as e:
            logger.error(e)
            return None
        else:
            search_results = client.search(
                index=settings.OPENSEARCH_INDEX["document"],
                body={"query": _query, "highlight": {"fields": {"content": {}}}},
            )
            return search_results

    @staticmethod
    def search(*, case_id=None, query=None, confidential_status=None, fields=None):
        """
        Search documents:
        Requires all arguments as kwargs
            - case_id: filter within a specific case
            - query: search term to include
            - confidential_stats: True = Conf, False=Non-Conf, None=All
            - fields: defaults to filter using name, file name and organisation name.
                 A list of allowed search term filters
        """
        if not fields:
            fields = ["name", "file", "organisation"]
            # include the case name and reference in the search if not filtering by case
            if not case_id:
                fields += ["case", "ref", "case_type"]

        if case_id:
            documents = Document.objects.filter(
                Q(submissiondocument__submission__case_id=case_id) | Q(note__case_id=case_id)
            )
        else:
            documents = Document.objects.filter()
        if confidential_status is not None:
            documents = documents.filter(confidential=confidential_status)
        if query:
            query_args = None
            for field_key in fields:
                field = SEARCH_FIELD_MAP[field_key]
                _q = Q(**{f"{field}__icontains": query})
                if not query_args:
                    query_args = _q
                else:
                    query_args |= _q
            documents = documents.filter(query_args)
        return documents

    @staticmethod
    def create_document(
        file,
        user,
        confidential=True,
        system=False,
        document=None,
        parent=None,
        case=None,
        index_and_checksum=True,
    ):
        """
        Create a document record from a file.
        If a document record is provided, it will be updated
        """
        file_name = file.get("name") if isinstance(file, dict) else file.name
        doc_name = file.get("document_name") if isinstance(file, dict) else file_name
        extension = file_name.split(".")[-1].lower()
        if extension in INVALID_FILE_EXTENSIONS:
            raise InvalidFile(f"This file type ({extension}) is not allowed.")
        document = document or Document(created_by=user, user_context=user)
        document.file = file.get("name") if isinstance(file, dict) else file
        document.name = doc_name
        document.size = file.get("size") if isinstance(file, dict) else file.size
        document.system = system
        document.confidential = confidential
        if parent:
            document.parent = parent
        document.save()
        if index_and_checksum:
            if settings.RUN_ASYNC:
                index_document.delay(str(document.id), case_id=case.id if case else None)
                checksum_document.delay(str(document.id))
            else:
                index_document(str(document.id), case_id=case.id if case else None)
                checksum_document(str(document.id))
        return document


class Document(BaseModel):
    name = models.CharField(max_length=1000, null=False, blank=False)
    file = S3FileField(max_length=1000)
    size = models.IntegerField(null=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    system = models.BooleanField(default=False)  # TRA Document
    checksum = models.CharField(max_length=64, null=True, blank=True)
    confidential = models.BooleanField(default=True)
    index_state = models.SmallIntegerField(default=INDEX_STATE_NOT_INDEXED, choices=INDEX_STATES)
    block_from_public_file = models.BooleanField(default=False)
    block_reason = models.CharField(max_length=128, null=True, blank=True)
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="documents_blocked_by",
        on_delete=models.SET_NULL,
    )
    blocked_at = models.DateTimeField(null=True, blank=True)

    objects = DocumentManager()

    def __str__(self):
        return self.name

    def delete(self, delete_file=False, purge=False):
        if delete_file and self.file:
            self.file.delete()
        if purge:
            Document.objects.filter(parent=self).update(parent=None)
            super().delete(purge=True)
        else:
            self.deleted_at = timezone.now()
            self.save()
        self.delete_opensearch_document()

    @property
    def file_extension(self):
        if self.file:
            return self.file.name.split(".")[-1]
        return None

    def _to_dict(self, case=None, submission=None):
        # include submissions
        _dict = self.to_embedded_dict(case=case, submission=submission)
        if submission and not case:
            case = submission.case
        _dict["submissions"] = ([sub.to_embedded_dict() for sub in self.submissions(case)],)
        return _dict

    def delete_opensearch_document(self):
        """Delete an OpenSearch representation of this document.
        Using quite a broad exception handling to prevent any failure that will
        cause the delete to fail.
        """
        try:
            client = get_open_search()
        except OSWrapperError as e:
            logger.error(e)
        else:
            try:
                result = client.delete(
                    index=settings.OPENSEARCH_INDEX["document"],
                    id=str(self.id),
                )
                return result.get("result") == "deleted"
            except NotFoundError as exc:
                # OpenSearch document not found, probably uploaded before opensearch was activated
                pass
            except Exception as exc:
                logger.error(f"cannot delete OpenSearch document: {self.id} - {exc}")
        return False

    def to_embedded_dict(self, submission=None, case=None):
        # if submission is provided, enhance with SubmissionDocument attributes
        _dict = self.to_minimal_dict()
        _dict.update(
            {
                "is_tra": self.created_by.is_tra(),
                "created_by": self.created_by.to_embedded_dict(),
                "created_at": self.created_at.strftime(settings.API_DATETIME_FORMAT),
                "parent_id": str(self.parent.id) if self.parent else None,
                "checksum": self.checksum,
            }
        )
        # enhance with submission context if available
        if submission:
            case = case or submission.case
            subdoc = (
                self.submissiondocument_set.select_related(
                    "issued_by", "document", "submission", "submission__type", "submission__status"
                )
                .filter(submission=submission)
                .first()
            )
            _dict.update(
                {
                    "deficient": subdoc.deficient,
                    "downloads": subdoc.downloads,
                    "issued": bool(subdoc.issued_at),
                    "issued_at": subdoc.issued_at.strftime(settings.API_DATETIME_FORMAT)
                    if subdoc.issued_at
                    else None,
                }
            )
        if case:
            _dict["submission_count"] = len(self.submissions(case))
        return _dict

    def to_minimal_dict(self):
        result = {
            "id": str(self.id),
            "name": self.name,
            "size": self.size,
            "confidential": self.confidential,
            "block_from_public_file": self.block_from_public_file,
            "block_reason": self.block_reason,
            "index_state": self.index_state,
        }

        if self.blocked_at:
            result["blocked_at"] = self.blocked_at

        if self.blocked_by:
            result["blocked_by"] = {
                "id": self.blocked_by.id,
                "name": self.blocked_by.name,
            }

        return result

    def submissions(self, case=None):
        submissions = self.submissiondocument_set.select_related(
            "issued_by", "document", "submission", "submission__type", "submission__status"
        ).filter(submission__deleted_at__isnull=True)
        if case:
            submissions = submissions.filter(submission__case=case)
        return [subdoc.submission for subdoc in submissions]

    @property
    def current_submissions(self):
        submissions = self.submission_set.all()
        return submissions

    @property
    def mime_type(self):
        """
        Returns the mime type for this file, based on a the mimetypes module's guess_type call
        :return: string: mime type
        """
        return mimetypes.guess_type(self.file.path, False)[0]

    @property
    def download_url(self):
        """
        Return a self expiring download link for a document stored on S3
        """
        s3 = s3_client()
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.s3_bucket, "Key": self.file.name},
            ExpiresIn=settings.S3_DOWNLOAD_LINK_EXPIRY_SECONDS,
        )
        return url

    @property
    def s3_bucket(self):
        return self.file.storage.bucket_name

    @property
    def s3_key(self):
        return self.file.name

    def set_md5_checksum(self):
        """Update document checksum.

        Populates the S3 document's etag value
        """
        if self.file:
            obj = self.file.storage.bucket.Object(self.file.name)
            self.checksum = obj.e_tag.replace('"', "").replace("'", "")
            self.save()

    def extract_content(self):
        """
        Based on the type of document, extract all textual content.
        """
        try:
            file_type = self.file_extension
            if file_type not in parsers:
                return "", INDEX_STATE_UNKNOWN_TYPE
            text = parsers[file_type]["parse"](self)
            return text, INDEX_STATE_FULL_INDEX
        except Exception as exc:
            logger.error("Error extracting text: %s: %s / %s", str(exc), str(self.id), str(self))
            return "", INDEX_STATE_INDEX_FAIL

    def open_search_doc(self):
        """
        Return the OpenSearch document for this record
        """
        try:
            client = get_open_search()
        except OSWrapperError as e:
            logger.error(e)
        else:
            try:
                return client.get(
                    index=settings.OPENSEARCH_INDEX["document"],
                    id=self.id,
                )
            except NotFoundError:
                logger.warning("Could not find document in OpenSearch index")
        return None

    def open_search_index(self, submission=None, case=None, **kwargs):  # noqa
        """
        Create an OpenSearch indexed document for this record
        """
        try:
            client = get_open_search()
        except OSWrapperError as e:
            logger.error(e)
            return None
        content, index_state = self.extract_content()
        case = get_case(case)
        organisation = None

        doc = {
            "id": self.id,
            "name": self.name,
            "case_id": case.id if case else None,
            "file_type": self.file_extension,
            "all_case_ids": [],
            "created_at": self.created_at.strftime(settings.API_DATETIME_FORMAT),
            "created_by": {
                "id": self.created_by.id,
                "name": self.created_by.name,
            },
            "user_type": "TRA" if self.created_by.is_tra() else "PUB",
            "confidential": self.confidential,
            "checksum": self.checksum,
            "content": content,
        }
        if submission:
            sub_doc = self.submissiondocument_set.get(submission=submission)
        else:
            try:
                sub_doc = self.submissiondocument_set.exclude(submission__archived=True).get(
                    document=self
                )
            except self.submissiondocument_set.model.DoesNotExist:
                sub_doc = None
            except self.submissiondocument_set.model.MultipleObjectsReturned:
                doc["all_case_ids"] = list(
                    self.submissiondocument_set.exclude(submission__archived=True).values_list(
                        "submission__case__id", flat=True
                    )
                )
                sub_doc = None

        # check if related to submission
        if sub_doc:
            if not doc.get("case_id"):
                doc["case_id"] = sub_doc.submission.case.id
            organisation = sub_doc.submission.organisation
            doc.update(
                {
                    "submission": {
                        "name": sub_doc.submission.name,
                        "type_id": sub_doc.submission.type.id,
                        "type": sub_doc.submission.type.name,
                        "deficient": sub_doc.deficient,
                        "sufficient": sub_doc.sufficient,
                        "archived": sub_doc.submission.archived,
                        "version": sub_doc.submission.version,
                        "organisation_name_at_submission": sub_doc.submission.organisation_name,
                    },
                }
            )
        # check if this is a note document
        note = self.note_set.first()
        if note:
            if not doc.get("case_id") and note.case:
                doc["case_id"] = note.case.id
            doc.update(
                {
                    "note": {
                        "content": note.note,
                    }
                }
            )

        if organisation:
            doc.update(
                {
                    "organisation": {
                        "id": organisation.id,
                        "name": organisation.name,
                        "company_number": organisation.companies_house_id,
                        "country": organisation.country and organisation.country.name,
                    }
                }
            )
        result = client.index(index=settings.OPENSEARCH_INDEX["document"], id=self.id, body=doc)
        if result and result.get("result") in ("created", "updated"):
            self.index_state = index_state
            self.save()
        return result


class DocumentBundle(SimpleBaseModel):
    """
    Document bundles are a versioned collection of documents which can be used for various
    purposes, e.g., as a template for providing douments to new case applications.
    A bundle is associated with either a case type,
    or a combination of case_id and submission type.
    Only one live version is availabe per case type. Once a bundle is set to live, all
    previous version of it are ensured to be set to archived.
    """

    case_type = models.ForeignKey("cases.CaseType", null=True, blank=True, on_delete=models.PROTECT)
    case = models.ForeignKey("cases.Case", null=True, blank=True, on_delete=models.PROTECT)
    submission_type = models.ForeignKey(
        "cases.SubmissionType", null=True, blank=True, on_delete=models.PROTECT
    )
    version = models.SmallIntegerField(default=1)
    status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=(
            ("DRAFT", "Draft"),
            ("LIVE", "Live"),
            ("ARCHIVED", "Archived"),
        ),
    )
    description = models.TextField(null=True, blank=True)
    documents = models.ManyToManyField(Document)
    finalised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="finalised_by",
        on_delete=models.SET_NULL,
    )
    finalised_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        doc_bundle_type = self.case_type or self.submission_type
        level = "unknown"
        if self.case:
            level = "Case"
        elif self.case_type_id:
            level = "Case type"
        elif self.submission_type:
            level = "Submission type"
        return f"{level} : {doc_bundle_type} (v {self.version})"

    @property
    def versions(self):
        """
        Return all previous versions by this grouping (case_type or submission_type)
        """
        if self.case_id:
            return (
                DocumentBundle.objects.filter(
                    case_id=self.case_id,
                    submission_type_id=self.submission_type_id,
                )
                .exclude(id=self.id)
                .order_by("version")
            )
        bundles = DocumentBundle.objects.exclude(id=self.id).filter(case__isnull=True)
        if self.case_type:
            bundles = bundles.filter(case_type=self.case_type)
        elif self.submission_type:
            bundles = bundles.filter(submission_type=self.submission_type, case_type__isnull=True)
        bundles = bundles.order_by("version")
        return bundles

    @property
    def name(self):
        if self.case_type:
            return self.case_type.name
        elif self.submission_type:
            return f"Submission type: {self.submission_type.name}"
        return "Document bundle"

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "documents": [document.to_embedded_dict() for document in self.documents.all()],
            "case_type": self.case_type and self.case_type.to_embedded_dict(),
            "submission_type": self.submission_type and self.submission_type.to_dict(),
            "status": self.status,
            "version": self.version,
            "description": self.description,
            "versions": [
                {"id": str(version.id), "version": version.version} for version in self.versions
            ],
            "finalised_by": self.finalised_by and self.finalised_by.to_embedded_dict(),
            "finalised_at": self.finalised_at,
            "created_at": self.created_at,
            "created_by": self.created_by and self.created_by.to_embedded_dict(),
        }

    def make_live(self, user):
        self.status = "LIVE"
        self.finalised_at = timezone.now()
        self.finalised_by = user
        self.save()
        for old_version in self.versions.filter(status__in=(["LIVE"])):
            old_version.status = "ARCHIVED"
            old_version.save()

    def new_version(self):
        """
        Create a new version for this bundle.
        New version will be a copy of this one, set to DRAFT
        """

        if self.status == "LIVE":
            # We only need to create a new version if this one is live -
            # otherwise, just return this
            self.id = None
            self.description = None
            self.version += 1
            self.status = "DRAFT"
            self.save()
        return self
