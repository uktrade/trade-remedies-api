from core.services.base import TradeRemediesApiView, ResponseSuccess
from content.models import Content
from django.db import transaction
from rest_framework import status
from cases.models import Case
from core.utils import update_object_from_request


class ContentAPIView(TradeRemediesApiView):
    """
    Get or create content pages

    `GET /api/v1/case/{CASE_ID}/content/`
        Get the content structure for the case

    `GET /api/v1/case/{CASE_ID}/content/{CONTENT_ID}/`
        Get a single content data block

    `POST /api/v1/case/{CASE_ID}/content/`
        Create a new content item for this case

    `POST /api/v1/case/{CASE_ID}/content/{CONTENT_ID}/`
        Update a content item for this case

    """

    def get(self, request, case_id, content_id=None, *args, **kwargs):
        """
        Return a single content item or a full tree
        """
        case = Case.objects.get(id=case_id)
        if content_id:
            content = Content.objects.get(case=case, id=content_id)
            return ResponseSuccess({"result": content.to_dict()})
        else:
            content = Content.objects.content_branch(case=case, root=None)
            return ResponseSuccess({"results": [node.to_embedded_dict() for node in content]})

    def post(self, request, case_id, content_id=None, *args, **kwargs):
        """
        Create or update content
        """
        case = Case.objects.get(id=case_id)

        if content_id:
            content = Content.objects.get(id=content_id, case=case)
        else:
            content = Content(case=case, created_by=request.user)

        update_object_from_request(content, request.data, ["name", "short_name", "content"])
        parent_id = request.data.get("parent_id")
        if parent_id:
            content.parent = Content.objects.get(id=parent_id, case=case)
        content.save()
        return ResponseSuccess({"result": content.to_dict()}, http_status=status.HTTP_201_CREATED)
