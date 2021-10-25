from django.contrib import admin
from .models import Organisation
from security.models import OrganisationUser, OrganisationCaseRole


class OrganisationCaseRoleInline(admin.TabularInline):
    model = OrganisationCaseRole
    search_fields = ["organisation", "case", "role"]


class OrganisationUserInline(admin.TabularInline):
    model = OrganisationUser


class OrganisationAdmin(admin.ModelAdmin):
    inlines = [OrganisationUserInline, OrganisationCaseRoleInline]
    search_fields = ["name"]


admin.site.register(Organisation, OrganisationAdmin)
