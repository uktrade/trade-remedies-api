from django.contrib import admin
from .models import WorkflowTemplate


class WorkflowTemplateAdmin(admin.ModelAdmin):
    pass


admin.site.register(WorkflowTemplate, WorkflowTemplateAdmin)
