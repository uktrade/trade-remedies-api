from django.contrib import admin
from .models import Contact


class ContactAdmin(admin.ModelAdmin):
    search_fields = ["name", "email", "address", "country", "phone"]
    list_display = ["name", "email", "address", "country", "phone"]


class ContactInlineAdmin(admin.StackedInline):
    model = Contact


admin.site.register(Contact, ContactAdmin)
