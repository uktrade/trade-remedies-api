from django.contrib import admin
from security.models import OrganisationCaseRole
from .models import (
    Case,
    Submission,
    Sector,
    Product,
    SubmissionType,
    SubmissionStatus,
    CaseWorkflow,
    CaseStage,
    SubmissionDocument,
    CaseWorkflowState,
)


class SectorAdmin(admin.ModelAdmin):
    pass


class SubmissionDocumentInline(admin.TabularInline):
    model = SubmissionDocument


class SubmissionAdmin(admin.ModelAdmin):
    inlines = [SubmissionDocumentInline]
    list_display = ("case", "name", "type", "created_at", "created_by")


class SubmissionTypeAdmin(admin.ModelAdmin):
    pass


class SubmissionStatusAdmin(admin.ModelAdmin):
    pass


class ProductAdmin(admin.ModelAdmin):
    pass


class SubmissionInline(admin.TabularInline):
    model = Submission


class OrganisationCaseRoleInline(admin.TabularInline):
    model = OrganisationCaseRole


class CaseAdmin(admin.ModelAdmin):
    inlines = [SubmissionInline, OrganisationCaseRoleInline]


class CaseWorkflowAdmin(admin.ModelAdmin):
    pass


class CaseWorkflowStateAdmin(admin.ModelAdmin):
    list_display = ("case", "key", "value", "due_date")
    list_filter = ("case",)
    search_fields = ("key",)


class CaseStageAdmin(admin.ModelAdmin):
    pass


admin.site.register(Sector, SectorAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Case, CaseAdmin)
admin.site.register(Submission, SubmissionAdmin)
admin.site.register(SubmissionType, SubmissionTypeAdmin)
admin.site.register(SubmissionStatus, SubmissionStatusAdmin)
admin.site.register(CaseWorkflow, CaseWorkflowAdmin)
admin.site.register(CaseWorkflowState, CaseWorkflowStateAdmin)
admin.site.register(CaseStage, CaseStageAdmin)
