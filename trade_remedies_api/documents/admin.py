from django.contrib import admin
from .models import Document, DocumentBundle


class DocumentAdmin(admin.ModelAdmin):
    list_display = ("name", "file", "system", "checksum", "size", "created_at")
    list_filter = ["system"]
    search_fields = ["name"]


class DocumentBundleAdmin(admin.ModelAdmin):
    pass


admin.site.register(Document, DocumentAdmin)
admin.site.register(DocumentBundle, DocumentBundleAdmin)
