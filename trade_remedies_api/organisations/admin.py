from django.contrib import admin

from security.models import OrganisationCaseRole, OrganisationUser
from .models import DuplicateOrganisationMerge, Organisation, OrganisationMergeRecord


class OrganisationCaseRoleInline(admin.TabularInline):
    model = OrganisationCaseRole
    search_fields = ["organisation", "case", "role"]


class OrganisationUserInline(admin.TabularInline):
    model = OrganisationUser


class OrganisationAdmin(admin.ModelAdmin):
    inlines = [OrganisationUserInline, OrganisationCaseRoleInline]
    search_fields = ["name"]


admin.site.register(Organisation, OrganisationAdmin)
admin.site.register(OrganisationMergeRecord)
admin.site.register(DuplicateOrganisationMerge)
