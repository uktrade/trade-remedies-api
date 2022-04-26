import logging
import json
from time import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.parsers import BaseParser, DataAndFiles
from rest_framework.exceptions import ParseError
from security.utils import validate_user_organisation, validate_user_case
from security.constants import SECURITY_GROUP_SUPER_USER
from organisations.models import get_organisation
from config.version import __version__
from django.contrib.auth.models import Group
from django.conf import settings
from django.http.multipartparser import (
    MultiPartParser as DjangoMultiPartParser,
    MultiPartParserError,
)
from core.feature_flags import FeatureFlags
from .exceptions import AccessDenied

logger = logging.getLogger(__name__)


class GroupPermission(BasePermission):
    @staticmethod
    def _user_in_group(user, group):
        """Check is a user is in a group.

        :param (User) user: User to check.
        :param (Group) group: Group to check membership of.
        :returns (bool): True if the user is in a given group, False otherwise.
        """
        try:
            return Group.objects.get(name=group).user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False

    def has_permission(self, request, view):
        """Check user's permission override.

        Check if the user in this request is in an allowed group for the request
        method invoked on the view (or is a superuser, or the view doesn't specify
        allowed groups).
        :param (HTTPRequest) request: API request.
        :param (TradeRemediesApiView) view: View to check permission for.

        :returns (bool): True
        """
        allowed_groups_mapping = getattr(view, "allowed_groups", {})
        allowed_groups = allowed_groups_mapping.get(request.method, [])
        if request.user.is_superuser or not allowed_groups:
            return True
        return any([self._user_in_group(request.user, group) for group in allowed_groups])


class TradeRemediesApiView(APIView):
    """Base class for all Trade Remedies API Views.

    Api responses should always return ResponseSuccess objects if successful, or
    raise an API Exception otherwise.

    The base API class assigns some instance attributes to the
    APIView instance and the response data, in order to conform
    to a standard:

        `start` and `limit` are provided in the response data if
        a queryset attribute is set. In addition _start & _limit
        attributes are set in the APIView object itself.

        _search is set if a `q` query parameter is provided

        `process_time` is set in the response to provide a measure
        of time it took to process this request

        `feature_flags` provides a `FeatureFlag` instance which can be used
        to fetch flags from the SystemParameters. Flag values will be cached
        on the request object, so it can be called multiple times without
        performing multiple queries to the database or cache.
    """

    permission_classes = (IsAuthenticated, GroupPermission)
    allowed_groups = {}

    def __init__(self, *args, **kwargs):
        self.case_id = None
        self.user = None
        self.organisation = None
        self._start = 0
        self._limit = settings.DEFAULT_QUERYSET_PAGE_SIZE
        self._search = None
        self._order_by = ""
        self._order_dir = "asc"
        self.feature_flags = None
        super().__init__(*args, **kwargs)

    def initial(self, request, *args, **kwargs):
        """Initial override.

        Override initial to collect some standard
        request parameters into the API View Object.
        :param (HttpRequest) request: Request object.
        """
        super().initial(request, *args, **kwargs)
        organisation_id = kwargs.get("organisation_id")
        self.case_id = kwargs.get("case_id")
        self.user = request.user
        self.organisation = get_organisation(organisation_id)
        if self.organisation:
            self.organisation.set_user_context(request.user)
        if self.allowed_groups:
            self.raise_on_invalid_access()
        self._start = int(request.query_params.get("start", 0))
        self._limit = int(request.query_params.get("limit", settings.DEFAULT_QUERYSET_PAGE_SIZE))
        self._search = request.query_params.get("q")
        self._order_by = request.query_params.get("order_by")
        self._order_dir = request.query_params.get("order_dir", "asc")

    def raise_on_invalid_access(self):
        """Check user organisation authorisation.

        Raise an AccessDenied API exception if the user is not allowed to
        access the organisation.
        """
        is_valid = False
        org_id = self.organisation.id if self.organisation else None
        if self.user.has_group(SECURITY_GROUP_SUPER_USER):
            is_valid = True
        elif self.allowed_groups.get(self.request.method) and self.user.has_groups(
            self.allowed_groups[self.request.method]
        ):
            is_valid = True
        elif self.case_id and org_id:
            is_valid = validate_user_case(self.user, self.case_id, org_id)
        elif org_id:
            is_valid = validate_user_organisation(self.user, org_id)
        if not is_valid:
            raise AccessDenied("User does not have access to organisation")

    def dispatch(self, request, *args, **kwargs):
        """Dispatch override.

        :param (HttpRequest) request: Request object.
        """
        time_recv = time()
        self.feature_flags = FeatureFlags()
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(response, "data"):
            if response.exception is True:
                response["error"] = True
                if settings.DEBUG:
                    logger.error(f"Error: {response.data}")
            else:
                response.data["version"] = __version__
                response.data["process_time"] = time() - time_recv
                if hasattr(self, "queryset"):
                    response.data["start"] = self._start
                    response.data["limit"] = self._limit
        return response

    def validate_required_fields(self, request):
        if hasattr(self, "required_keys"):
            missing_keys = [key for key in self.required_keys if not request.data.get(key)]
            return missing_keys
        return []

    @property
    def sort_spec(self):
        if self._order_by and self._order_dir:
            order_dir_indicator = "-" if self._order_dir == "desc" else ""
            return [f"{order_dir_indicator}{self._order_by}"]
        return None


class ResponseSuccess(Response):
    """Common response object.

    Manages a standard response format for all API calls.
    """

    def __init__(self, data=None, http_status=None, content_type=None):
        _status = http_status or status.HTTP_200_OK
        data = data or {}
        reply = {"response": {"success": True}}
        reply["response"]["version"] = __version__
        if "result" not in data or "results" not in data:
            reply["response"]["result"] = data
        else:
            reply["response"].update(data)
        super().__init__(data=reply, status=_status, content_type=content_type)


class ResponseError(Response):
    """Common error response object.

    When an exception is not sufficient and a response can still be returned
    (e.g. certain errors to correct) we can use ResponseError to standardise
    this response format.
    """

    def __init__(
        self,
        error,
        error_code=None,
        http_status=status.HTTP_400_BAD_REQUEST,
        content_type=None,
        detail=None,
    ):
        reply = {
            "response": {
                "success": False,
                "error": error,
                "error_code": error_code,
                "detail": detail,
            }
        }
        super().__init__(data=reply, status=http_status, content_type=content_type)


class MultiPartJSONParser(BaseParser):
    """Parser for multipart form data.

    Parser for multipart form data which might contain JSON values in some fields
    as well as file data. This is a variation of MultiPartJSONParser, which goes
    through submitted fields and attempts to decode them as JSON where a value exists.
    It is not to be used as a replacement for MultiPartParser, only in cases where
    MultiPart AND JSON data are expected.
    """

    media_type = "multipart/form-data"

    def parse(self, stream, media_type=None, parser_context=None):
        """Parse the incoming bytestream.

        Parses the incoming bytestream as a multipart encoded form and returns a
        DataAndFiles object.

        `.data` will be a `QueryDict` containing all the form parameters,
        and JSON decoded where available.
        `.files` will be a `QueryDict` containing all the form files.

        :param (bytes) stream: Incoming byte stream.
        :param (str) media_type: Media Type.
        :param (dict) parser_context: Context.
        """
        parser_context = parser_context or {}
        request = parser_context["request"]
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)
        meta = request.META.copy()
        meta["CONTENT_TYPE"] = media_type
        upload_handlers = request.upload_handlers

        try:
            parser = DjangoMultiPartParser(meta, stream, upload_handlers, encoding)
            data, files = parser.parse()
            # get a dict of data to make it mutable
            _data = data.dict()
            for key in _data:
                if _data[key]:
                    try:
                        _data[key] = json.loads(_data[key])
                    except ValueError:
                        pass
            return DataAndFiles(_data, files)
        except MultiPartParserError as exc:
            raise ParseError("Multipart form parse error - %s" % str(exc))
