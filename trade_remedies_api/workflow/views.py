from django.shortcuts import render
from django.views.generic import TemplateView
from .models import WorkflowTemplate


class WorkflowEditorView(TemplateView):
    """
    A view into TRA uploaded system documents
    """

    template_name = "editor.html"

    def get(self, request, document_id=None, *args, **kwargs):
        all_templates = WorkflowTemplate.objects.all().order_by("name")
        template_id = request.GET.get("template_id")
        if not template_id and len(all_templates) == 1:
            template_id = all_templates[0].id
        if template_id:
            template = WorkflowTemplate.objects.get(id=template_id)
        else:
            template = WorkflowTemplate(template={"root": []})
        return render(
            request,
            self.template_name,
            {
                "template_id": template_id,
                "all_templates": all_templates,
                "template": template,
                "workflow": template.workflow,
            },
        )
