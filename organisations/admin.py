from django.contrib import admin
from .models import Organisation
from security.models import OrganisationUser, OrganisationCaseRole


class OrganisationCaseRoleInline(admin.TabularInline):
    model = OrganisationCaseRole


class OrganisationUserInline(admin.TabularInline):
    model = OrganisationUser


class OrganisationAdmin(admin.ModelAdmin):
    inlines = [OrganisationUserInline, OrganisationCaseRoleInline]


admin.site.register(Organisation, OrganisationAdmin)
