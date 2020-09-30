from django.contrib import admin
from .models import Content


class ContentAdmin(admin.ModelAdmin):
    pass


admin.site.register(Content, ContentAdmin)
