from django.contrib import admin
from .models import Audit


class AuditAdmin(admin.ModelAdmin):
    search_fields = ["type", "case_id", "content_type__model", "milestone", "created_at"]
    list_display = ("type", "created_at", "case_id", "content_type", "milestone")
    list_filter = ["type", "case_id"]
    # Leave commented out until all environments have run migrations
    # for removal of audit.case foreign key.
    # list_display = ('type', 'created_at', 'case_id', 'content_type', 'milestone')
    # list_filter = ['type', 'case_id']


admin.site.register(Audit, AuditAdmin)
