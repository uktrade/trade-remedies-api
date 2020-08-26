from django.contrib import admin
from .models import Invitation


class InvitationAdmin(admin.ModelAdmin):
    pass


admin.site.register(Invitation, InvitationAdmin)
