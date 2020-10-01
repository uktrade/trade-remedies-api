from django.contrib import admin
from .models import Contact


class ContactAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "address", "country", "phone"]


class ContactInlineAdmin(admin.StackedInline):
    model = Contact


admin.site.register(Contact, ContactAdmin)
