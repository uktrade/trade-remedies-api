from core.services.base import TradeRemediesApiView, ResponseSuccess
from rest_framework import status
from workflow.models import WorkflowTemplate, Workflow


class WorkflowTemplateAPI(TradeRemediesApiView):
    def get(self, request, template_id=None, *args, **kwargs):
        if template_id:
            template = WorkflowTemplate.objects.get(id=template_id)
            return ResponseSuccess({"result": template.to_dict()})
        else:
            templates = WorkflowTemplate.objects.all().order_by("name")
            return ResponseSuccess({"results": [template.to_dict() for template in templates]})

    def post(self, request, template_id=None, *args, **kwargs):
        if template_id:
            template = WorkflowTemplate.objects.get(id=template_id)
        else:
            template = WorkflowTemplate.objects.create(
                name=request.data.get("template_name", "Untitled"), template=Workflow.BOILERPLATE
            )
        item_type = request.data.get("name")
        item_id = request.data.get("value")
        index = int(request.data.get("index", -1))
        parent_id = request.data.get("parent_id")

        workflow = template.workflow
        _index = index if index > -1 else None
        workflow.set(item, parent_id, _index)  # noqa: F821
        template.template = workflow.shrink()
        template.save()
        return ResponseSuccess(
            {"template": template.to_dict()}, http_status=status.HTTP_201_CREATED
        )
