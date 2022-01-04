import json
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import (
    Q,
    Count,
)
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import JSONParser, FormParser

from audit import AUDIT_TYPE_ATTACH
from cases.models import (
    Case,
    Submission,
    SubmissionDocument,
    SubmissionDocumentType,
    SubmissionType,
    get_case,
)
from core.services.base import (
    TradeRemediesApiView,
    ResponseSuccess,
    MultiPartJSONParser,
)
from core.services.exceptions import (
    InvalidRequestParams,
    NotFoundApiExceptions,
    InvalidFileUpload,
)
from core.utils import key_by

from documents.constants import (
    SEARCH_CONFIDENTIAL_STATUS_MAP,
    INDEX_STATE_NOT_INDEXED,
    INDEX_STATE_UNKNOWN_TYPE,
    INDEX_STATE_INDEX_FAIL,
    INDEX_STATE_FULL_INDEX,
)
from documents.exceptions import InvalidFile
from documents.models import Document, DocumentBundle
from documents.utils import stream_s3_file_download
from notes.models import Note
from security.constants import SECURITY_GROUPS_TRA


logger = logging.getLogger(__name__)


class CaseDocumentCountAPI(TradeRemediesApiView):
    """
    Return full document count for a case
    """

    def get(self, request, case_id, *args, **kwargs):
        case = Case.objects.get(id=case_id)
        sub_documents = SubmissionDocument.objects.filter(
            submission__case=case,
            submission__deleted_at__isnull=True,
            document__deleted_at__isnull=True,
        ).distinct("document")
        sub_docs_cw = sub_documents.filter(
            document__created_by__groups__name__in=SECURITY_GROUPS_TRA
        ).count()
        sub_docs_pub = (
            sub_documents.exclude(document__created_by__groups__name__in=SECURITY_GROUPS_TRA)
            .exclude(submission__status__default=True)
            .exclude(submission__status__draft=True)
            .count()
        )
        note_documents = Note.objects.filter(
            case=case, documents__isnull=False, documents__submissiondocument__isnull=True
        ).count()
        return ResponseSuccess({"result": sub_docs_pub + sub_docs_cw + note_documents})


class CaseDocumentAPI(TradeRemediesApiView):
    """
    Return all documents for a case
    """

    def get(self, request, case_id, organisation_id=None, source=None):  # noqa: C901
        case = Case.objects.get(id=case_id)
        submission_id = request.query_params.get("submission_id")
        sub_documents = SubmissionDocument.objects.filter(
            submission__case=case,
            submission__deleted_at__isnull=True,
            document__deleted_at__isnull=True,
        )
        if organisation_id:
            sub_documents = sub_documents.filter(submission__organisation__id=organisation_id)
        if submission_id:
            submission = Submission.objects.get_submission(id=submission_id, case=case)
            sub_documents = sub_documents.filter(submission=submission)
        # get all note documents which are not already part of a submission
        _note_documents = Note.objects.filter(
            case=case, documents__isnull=False, documents__submissiondocument__isnull=True
        )
        bundle_documents = set([])
        # filter by source - respondent or investigator
        if source:
            if source == "public":
                sub_documents = sub_documents.filter(
                    document__confidential=False, issued_at__isnull=False
                )
                _note_documents = []
            elif source == "respondent":
                sub_documents = sub_documents.exclude(
                    document__created_by__groups__name__in=SECURITY_GROUPS_TRA
                )
                sub_documents = sub_documents.exclude(submission__status__default=True)
                sub_documents = sub_documents.exclude(submission__status__draft=True)
                _note_documents = _note_documents.exclude(
                    documents__created_by__groups__name__in=SECURITY_GROUPS_TRA
                )
            elif source == "investigator":
                sub_documents = sub_documents.filter(
                    document__created_by__groups__name__in=SECURITY_GROUPS_TRA
                )
                _note_documents = _note_documents.filter(
                    documents__created_by__groups__name__in=SECURITY_GROUPS_TRA
                )
                for bundle in DocumentBundle.objects.filter(case_id=case_id):
                    bundle_documents |= set(bundle.documents.all())
        sub_documents = sub_documents.distinct("document")
        note_documents = set([])
        for note in _note_documents:
            note_documents |= set(note.all_non_issued_documents)

        if organisation_id:
            sub_documents = sub_documents.filter(submission__organisation__id=organisation_id)
        if submission_id:
            submission = Submission.objects.get_submission(id=submission_id)
            sub_documents = sub_documents.filter(submission=submission)
        other_documents = list(note_documents.union(bundle_documents))
        response = {
            "results": self.make_docs(
                submission_documents=sub_documents,
                other_documents=other_documents
            )
        }
        return ResponseSuccess(response)

    @staticmethod
    def make_docs(submission_documents: list, other_documents: list = None) -> list:
        """Make a heterogeneous document list.

        TODO-V2:
        Suboptimal quick fix, fix properly. What's actually required is a decent DRF
        serializer, paginated results and the ability to filter (maybe using something
        like https://github.com/yezyilomo/django-restql/).
        """
        results = []
        for doc in submission_documents:
            doc_data = dict(
                id=doc.document.id,
                name=doc.document.name,
                created_at=doc.document.created_at.strftime(settings.API_DATETIME_FORMAT),
                created_by=doc.document.created_by.name,
                submission=CaseDocumentAPI.make_submission_data(doc),
            )
            results.append(doc_data)

        for doc in other_documents or []:
            doc_data = dict(
                id=doc.id,
                name=doc.name,
                created_at=doc.created_at.strftime(settings.API_DATETIME_FORMAT),
                created_by=doc.created_by.name,
                submission=None,
            )
            results.append(doc_data)
        return results

    @staticmethod
    def make_org_data(doc: SubmissionDocument) -> dict:
        return dict(
            id=doc.submission.organisation.id,
            name=doc.submission.organisation.name,
        ) if doc.submission.organisation else None

    @staticmethod
    def make_submission_data(doc: SubmissionDocument) -> dict:
        case_role = doc.submission.organisation_case_role()
        return dict(
            id=doc.submission.id,
            version=doc.submission.version,
            type_name=doc.submission.type.name,
            organisation=CaseDocumentAPI.make_org_data(doc),
            organisation_case_role=case_role and case_role.name,
        )


class DocumentAPIView(TradeRemediesApiView):
    """
    Get or create document records

    `GET /api/v1/documents/`
    `GET /api/v1/document/{DOCUMENT_ID}/`
    `GET /api/v1/document/download/{DOCUMENT_ID}/`
    `GET /api/v1/case/{CASE_ID}/documents/`
    `GET /api/v1/documents/system/`
    `POST /api/v1/document/`
    `POST /api/v1/document/{DOCUMENT_ID}/`

    """

    parser_classes = (MultiPartJSONParser, JSONParser, FormParser)
    system = None
    public = False

    def get(  # noqa: C901
        self,
        request,
        organisation_id=None,
        document_id=None,
        case_id=None,
        submission_id=None,
        *args,
        **kwargs,
    ):
        """
        Return all or a single document
        # TODO: no document edits
        """
        fields = request.query_params.get("fields", None)
        criteria = request.query_params.get("criteria", None)
        case = None
        collapse_identical = request.query_params.get("collapse", "false") in ("true", "1", "Y")
        if document_id:
            doc_kwargs = {"id": document_id, "deleted_at__isnull": True}
            if self.system:
                doc_kwargs["system"] = True
            if case_id:
                doc_kwargs["submissiondocument__submission__case"] = case_id
            if submission_id:
                doc_kwargs["submissiondocument__submission"] = submission_id
            document = Document.objects.select_related("parent", "created_by").get(**doc_kwargs)

            return ResponseSuccess({"result": document.to_dict()})
        documents = Document.objects.select_related(
            "parent",
            "created_by",
        ).filter(deleted_at__isnull=True)
        sort_spec = self.sort_spec
        if self.system:
            query = Q(system=True)
            if criteria:
                for key, value in json.loads(criteria).items():
                    query.add(Q(**{key: value}), Q.AND)
            documents = documents.filter(query)
        else:
            if case_id and not submission_id:
                case = Case.objects.get_case(id=case_id)
                documents = documents.filter(
                    Q(submissiondocument__submission__case=case) | Q(note__case=case)
                )
            if submission_id:
                documents = documents.filter(
                    submission__id=submission_id
                )  # submission.get_documents()
            if organisation_id:
                documents = documents.filter(submission__organisation__id=organisation_id)
            source = request.query_params.get("filter_by", documents)
            if source:
                if source == "respondent":
                    documents = documents.exclude(created_by__groups__name__in=SECURITY_GROUPS_TRA)
                elif source == "investigator":
                    documents = documents.filter(created_by__groups__name__in=SECURITY_GROUPS_TRA)
            if collapse_identical:
                documents = documents.distinct("id")
                # sort_spec.append('id')

        if sort_spec:
            documents = documents.order_by(*sort_spec)
        return ResponseSuccess(
            {"results": [doc.to_dict(case=case, fields=fields) for doc in documents]}
        )

    @transaction.atomic  # noqa: C901
    def post(
        self,
        request,
        document_id=None,
        case_id=None,
        organisation_id=None,
        submission_id=None,
        bundle_id=None,
        *args,
        **kwargs,
    ):
        if document_id is None:
            document_id = request.data.get("document_id", None)
        _files = request.FILES.getlist("file", None)
        _issued = request.data.get("issued") or False
        _case_document = request.data.get("case_document")
        _parent_id = request.data.get("parent_id") or False
        _replace_id = request.data.get("replace_id") or False
        _bundle_id = bundle_id or request.data.get("bundle_id")
        _system = request.data.get("system") or bool(_bundle_id)
        _confidential = request.data.get("confidential")
        _submission_document_type = request.data.get("submission_document_type")
        if _submission_document_type:
            submission_document_type = SubmissionDocumentType.objects.get(
                key=_submission_document_type
            )
        else:
            submission_document_type = SubmissionDocumentType.type_by_user(request.user)
        if _confidential is None:
            _confidential = True
        submission_type_id = request.data.get("submission_type_id")
        if (
            not _case_document
            and not _bundle_id
            and not submission_id
            and not submission_type_id
            and not _system
            and not document_id
        ):
            raise InvalidRequestParams("Submission id or type id are required")
        if not _files and not document_id and not request.data.get("file_name"):
            raise InvalidRequestParams("No file or documents provided")
        case = get_case(case_id)
        submission = None
        if submission_id:
            submission = Submission.objects.get_submission(id=submission_id, case=case)
        elif submission_type_id:
            submission_type = SubmissionType.objects.get(id=submission_type_id)
            submission = Submission.objects.create(
                name=submission_type.name,
                case=case,
                organisation=self.organisation,
                type=submission_type,
                status=submission_type.default_status,
                created_by=request.user,
                user_context=[request.user],
            )
        if not _files and request.data.get("file_name"):
            _files = [
                {
                    "name": request.data.get("file_name"),
                    "size": request.data.get("file_size"),
                    "document_name": request.data.get("document_name"),
                }
            ]
        if _files:
            result = []
            for _file in _files:
                _parent = None
                if _parent_id:
                    try:
                        _parent = Document.objects.get(id=_parent_id)
                    except Document.DoesNotExist:
                        raise NotFoundApiExceptions("Parent document is not found")
                try:
                    document = Document.objects.create_document(
                        file=_file,
                        user=request.user,
                        confidential=_confidential,
                        system=bool(_system),
                        parent=_parent,
                        document=Document.objects.get(id=document_id) if document_id else None,
                        case=case,
                    )
                except InvalidFile as e:
                    raise InvalidFileUpload(str(e))
                if _replace_id and submission:
                    # We are being asked to replace the given doc in this submission
                    try:
                        # Find the document to replace and get its child
                        _replace_doc = Document.objects.get(id=_replace_id)
                        _child_doc = Document.objects.filter(parent_id=_replace_id).first()
                        replace_submission_document = SubmissionDocument.objects.get(
                            submission=submission, document=_replace_doc
                        )
                        replace_submission_document.set_user_context(request.user)
                        if _child_doc:
                            child_submission_document = SubmissionDocument.objects.get(
                                submission=submission, document=_child_doc
                            )
                            child_submission_document.set_user_context(request.user)
                            # Clone the child doc and add link to parent
                            _child_doc.id = None
                            _child_doc.parent = document
                            _child_doc.save()
                            # Update submission_doc to point to new child doc.
                            child_submission_document.document = _child_doc
                            child_submission_document.save()
                        replace_submission_document.delete()
                    except (Document.DoesNotExist, SubmissionDocument.DoesNotExist) as e:
                        logger.warning(
                            f"Document to replace with id '{_replace_id}' was not found: {e}"
                        )
                if submission:
                    if _submission_document_type:
                        submission_document_type = SubmissionDocumentType.objects.get(
                            key=_submission_document_type
                        )
                    else:
                        submission_document_type = SubmissionDocumentType.type_by_user(request.user)
                    submission_document = submission.add_document(
                        document=document,
                        document_type=submission_document_type,
                        issued=_issued,
                        issued_by=request.user,
                    )
                    result_item = submission_document.to_dict()
                elif _bundle_id:
                    bundle = DocumentBundle.objects.get(id=_bundle_id)
                    bundle.documents.add(document)
                    document.generic_audit(
                        message=f"Attached to bundle {bundle.name}",
                        audit_type=AUDIT_TYPE_ATTACH,
                        id=str(document.id),
                    )
                    result_item = document.to_dict()
                else:
                    result_item = document.to_dict()
                result.append(result_item)
            return ResponseSuccess({"result": result}, http_status=status.HTTP_201_CREATED)
        elif document_id:
            # We just want to attach a document
            document = Document.objects.get(id=document_id)
            if submission_id:
                submission_document = submission.add_document(
                    document=document,
                    document_type=submission_document_type,
                    issued=_issued,
                    issued_by=request.user,
                )
                if not request.user.is_tra():
                    submission.received_at = timezone.now()
                    submission.status = submission.type.received_status
                submission.save()

                return ResponseSuccess(
                    {"result": submission_document.to_dict()}, http_status=status.HTTP_201_CREATED
                )
            document.confidential = _confidential
            document.save()
            return ResponseSuccess({"result": {"document": document.to_dict()}})

    def delete(
        self,
        request,
        document_id=None,
        case_id=None,
        organisation_id=None,
        submission_id=None,
        *args,
        **kwargs,
    ):
        response = None
        submission = Submission.objects.get_submission(id=submission_id)
        submission.set_user_context(request.user)
        if document_id:
            document = Document.objects.get(id=document_id)
            document.set_case_context(submission.case)
            # If we are deleting a document with a child, delete the child as well.
            # iterating a filter makes it a bit more robust in case a file has multiple children.
            for child in Document.objects.filter(parent=document_id):
                submission.remove_document(child, requested_by=request.user)
                if not Submission.document_exists(child):
                    response = child.delete()
            submission.remove_document(document, requested_by=request.user)
            if not Submission.document_exists(document):
                response = document.delete()

            return ResponseSuccess({"result": {"deleted": True, "result": response}})


class DocumentDownloadAPIView(TradeRemediesApiView):
    """
    Return download url for a file. The url has a life
    defined in env file then called in settings.S3_DOWNLOAD_LINK_EXPIRY_SECONDS
    """

    def get(self, request, document_id, submission_id=None, *args, **kwargs):
        document = Document.objects.get(id=document_id)
        if submission_id:
            submission = Submission.objects.get_submission(id=submission_id)
            doc_submission = SubmissionDocument.objects.get(
                submission=submission, document=document
            )
            doc_submission.downloads += 1
            doc_submission.save()
        return ResponseSuccess(
            {"result": {"id": str(document.id), "download_url": document.download_url}}
        )


class DocumentStreamDownloadAPIView(TradeRemediesApiView):
    def get(self, request, document_id, submission_id=None, *args, **kwargs):
        document = Document.objects.get(id=document_id)
        is_tra = request.user.is_tra()

        if (
            not is_tra
            and not submission_id
            and not request.user.email == settings.TRUSTED_USER_EMAIL
        ):
            raise InvalidRequestParams("Invalid request params")
        if submission_id:
            submission = Submission.objects.get_submission(id=submission_id)
            doc_submission = SubmissionDocument.objects.get(
                submission=submission, document=document
            )
            if not is_tra and not doc_submission.downloadable_by(request.user):
                raise NotFoundApiExceptions("Document not found or access is denied")
            doc_submission.downloads += 1
            doc_submission.save()
        return stream_s3_file_download(document.s3_bucket, document.s3_key, filename=document.name)


class DocumentIssueAPI(TradeRemediesApiView):
    """
    Issue a document to the case.
    If the document is part of a submission, it's issued flag is toggled to
    denote it being issued or removed from the case.
    If the document is standalone, a submisssion of a given type is created
    and assigned to the case. Optional submission name can be provided (or will
    default to the submission type name) as well as an organisation.
    Note: used by the Files page
    """

    @transaction.atomic
    def post(self, request, case_id, *args, **kwargs):
        response = {"submissions": [], "issued": [], "removed": []}
        submissions = set()
        if request.user.is_tra():
            case = Case.objects.get(id=case_id)
            submission_type_id = request.data.get("submission_type_id")
            document_ids = request.data.getlist("document_ids")
            documents = Document.objects.filter(id__in=document_ids)
            if documents:
                if submission_type_id:
                    submission = case.create_submission_for_documents(
                        documents=documents,
                        submission_type=submission_type_id,
                        name=request.data.get("name") or None,
                        organisation=request.data.get("organisation_id") or None,
                        created_by=request.user,
                        issued=True,
                    )
                    submissions.add(submission)
                else:
                    for document in documents:
                        submission_docs = document.submissiondocument_set.filter(
                            submission__case=case
                        )
                        for subdoc in submission_docs:
                            subdoc.issue_to_submission(user=request.user)
                            submissions.add(subdoc.submission)

                for sub in submissions:
                    response["submissions"].append(str(sub.id))
                    case.notify_all_participants(request.user, submission=sub)

        return ResponseSuccess({"result": response})


class DocumentConfidentialAPI(TradeRemediesApiView):
    """
    Change the confidential state of a document, toggling the value.
    This can be performed by a TRA user only and only for documents created BY the TRA.
    """

    def post(self, request, case_id, *args, **kwargs):
        if request.user.is_tra():
            case = Case.objects.get(id=case_id)
            document_ids = request.data.getlist("document_ids")
            documents = Document.objects.filter(
                id__in=document_ids, created_by__groups__name__in=SECURITY_GROUPS_TRA
            )
            report = {}
            for document in documents:
                document.set_case_context(case)
                report[str(document.id)] = {
                    "from": document.confidential,
                    "to": not document.confidential,
                }
                document.confidential = not document.confidential
                document.save()
        return ResponseSuccess(
            {
                "result": report,
            }
        )


class DocumentBundlesAPI(TradeRemediesApiView):
    """
    Get or creates document bundles.

    When creating a bundle, the case type is required. If a bundle already exists
    for this case type, a new version will be created based on the last version for that case type
    (live or draft). If none exist, a new one will be created as a draft.
    If a specific bundle id is provided to POST, that bundle will be updated.
    """

    single = None

    def get(self, request, case_type_id=None, status=None, bundle_id=None, *args, **kwargs):
        bundle_id = bundle_id or request.query_params.get("bundle_id")
        if bundle_id:
            bundle = DocumentBundle.objects.get(id=bundle_id)
            return ResponseSuccess({"result": bundle.to_dict()})
        case_id = request.query_params.get("case_id")
        status_in_url = status
        status = status or request.query_params.get("status")
        filter_kwargs = {}
        exclude_kwargs = {}
        if case_type_id:
            filter_kwargs["case_type"] = case_type_id
        if status:
            filter_kwargs["status"] = status
        if case_id:
            filter_kwargs["case_id"] = case_id
        else:
            exclude_kwargs["case_id__isnull"] = False
        # if status_in_url:
        #     filter_kwargs['case_type__isnull'] = False

        bundles = (
            DocumentBundle.objects.filter(**filter_kwargs)
            .exclude(status="ARCHIVED")
            .exclude(**exclude_kwargs)
        )
        if status_in_url:
            bundles = bundles.filter(Q(case_type__isnull=False) | Q(submission_type__isnull=False))

        bundles = bundles.order_by("case_type__name")
        return ResponseSuccess(
            {"result": bundles[0] and bundles[0].to_dict()}
            if self.single
            else {"results": [bundle.to_dict() for bundle in bundles]}
        )

    @transaction.atomic
    def post(
        self,
        request,
        case_type_id=None,
        submission_type_id=None,
        status=None,
        bundle_id=None,
        *args,
        **kwargs,
    ):
        case_id = None
        if bundle_id:
            bundle = DocumentBundle.objects.get(id=bundle_id)
        else:
            if case_type_id:
                bundle = (
                    DocumentBundle.objects.filter(case_type_id=case_type_id)
                    .order_by("-version")
                    .first()
                )
            elif submission_type_id:
                bundle = (
                    DocumentBundle.objects.filter(
                        submission_type_id=submission_type_id, case__isnull=True
                    )
                    .order_by("-version")
                    .first()
                )
            else:
                case_id = request.data.get("case_id")
                submission_type_id = request.data.get("submission_type_id")
                bundle = (
                    DocumentBundle.objects.filter(
                        case_id=case_id, submission_type_id=submission_type_id
                    )
                    .order_by("-version")
                    .first()
                )
            if bundle:
                bundle = bundle.new_version()
            else:
                bundle = DocumentBundle.objects.create(
                    case_type_id=case_type_id,
                    submission_type_id=submission_type_id,
                    case_id=case_id,
                    status="DRAFT",
                    user_context=self.user,
                )
            bundle.created_by = self.user
        bundle.set_user_context(self.user)
        if case_id:
            bundle.set_case_context(get_case(case_id))
        bundle.description = request.data.get("description", bundle.description)
        status = status or request.data.get("status")
        if status in ("LIVE", "DRAFT"):
            if status == "LIVE":
                bundle.make_live(request.user)
            else:
                bundle.status = status
        bundle.save()
        return ResponseSuccess({"result": bundle.to_dict()})

    def delete(self, request, bundle_id, *args, **kwargs):
        bundle = DocumentBundle.objects.get(id=bundle_id)
        bundle.set_user_context(self.user)
        bundle.delete()
        return ResponseSuccess({"result": True})


class BundleDocumentAPI(TradeRemediesApiView):
    def post(self, request, bundle_id, document_id):
        bundle = DocumentBundle.objects.get(id=bundle_id)
        document = Document.objects.get(id=document_id)
        bundle.set_user_context(self.user)
        if bundle.case:
            document.set_case_context(bundle.case)
        document.set_user_context(self.user)
        bundle.documents.add(document)
        document.generic_audit(
            message=f"Attached to bundle {bundle.name}",
            audit_type=AUDIT_TYPE_ATTACH,
            id=str(document.id),
        )
        return ResponseSuccess({"result": bundle.to_dict()})

    def delete(self, request, bundle_id, document_id, *args, **kwargs):
        bundle = DocumentBundle.objects.get(id=bundle_id)
        document = Document.objects.get(id=document_id)
        bundle.set_user_context(self.user)
        if bundle.case:
            document.set_case_context(bundle.case)
        document.set_user_context(self.user)
        bundle.documents.remove(document)
        return ResponseSuccess({"result": bundle.to_dict()})


class DocumentSearchAPI(TradeRemediesApiView):
    """
    Search documents across one or all cases.
    If case_id is provided the search is limited to a specific case, otherwise
    spans all cases.
    The standard `q` query param denotes a search term filter.
    The `conf` query param can be CONF, NON-CONF, or ALL to filter by the confidentiality status
    of documents.
    By default search includes
        - document title
        - ducment file name
        - organisation name
        - case name (if case id is not provided)
        - type of submission
    """

    def get(self, request, case_id=None):
        confidentiality = request.query_params.get("confidential_status", "NONCONF")
        organisation_id = request.query_params.get("organisation_id")
        user_type = request.query_params.get("user_type")
        confidential_status = SEARCH_CONFIDENTIAL_STATUS_MAP[confidentiality]
        case = Case.objects.get(id=case_id) if case_id else None

        documents = Document.objects.elastic_search(
            case=case,
            query=self._search,
            confidential_status=confidential_status,
            organisation=organisation_id,
            user_type=user_type,
        )
        hits = documents.get("hits", {})
        return ResponseSuccess(
            {
                "results": [
                    {
                        "score": doc.get("_score"),
                        "highlight": doc.get("highlight"),
                        **doc.get("_source"),
                    }
                    for doc in hits.get("hits", [])
                ],
                "query": self._search,
                "case_id": str(case_id) if case_id else None,
                "confidential_status": confidentiality,
                "total": hits.get("total") or 0,
                "max_score": hits.get("max_score"),
            }
        )


class DocumentSearchIndexAPI(TradeRemediesApiView):
    def get(self, request):
        documents = Document.objects.all()
        counts = Document.objects.values("index_state").annotate(total=Count("index_state"))
        count_index = key_by(counts, "index_state")
        return ResponseSuccess(
            {
                "result": {
                    "total": documents.count(),
                    "full_index": count_index.get(INDEX_STATE_FULL_INDEX, {}).get("total"),
                    "unknown_type": count_index.get(INDEX_STATE_UNKNOWN_TYPE, {}).get("total"),
                    "failed": count_index.get(INDEX_STATE_INDEX_FAIL, {}).get("total"),
                    "pending": count_index.get(INDEX_STATE_NOT_INDEXED, {}).get("total"),
                }
            }
        )
