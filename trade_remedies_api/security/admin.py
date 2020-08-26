from django.contrib import admin
from .models import OrganisationUser, CaseAction, CaseRole, OrganisationCaseRole, UserCase


class OrganisationUserAdmin(admin.ModelAdmin):
    pass


class OrganisationCaseRoleAdmin(admin.ModelAdmin):
    pass


class CaseActionAdmin(admin.ModelAdmin):
    pass


class CaseRoleAdmin(admin.ModelAdmin):
    pass


class UserCaseAdmin(admin.ModelAdmin):
    pass


admin.site.register(OrganisationUser, OrganisationUserAdmin)
admin.site.register(OrganisationCaseRole, OrganisationCaseRoleAdmin)
admin.site.register(UserCase, UserCaseAdmin)
admin.site.register(CaseAction, CaseActionAdmin)
admin.site.register(CaseRole, CaseRoleAdmin)
