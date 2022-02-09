from django.contrib import admin
from authentication.models import User, TwoFactorAuth, EmailVerification


class UserAdmin(admin.ModelAdmin):
    search_fields = ["name", "email", "address", "country", "phone"]
    list_display = ["name", "email", "address", "country", "phone"]


class TwoFactorAuthAdmin(admin.ModelAdmin):
    search_fields = [
        "user",
    ]
    readonly_fields = ("generated_at",)


class EmailVerificationAdmin(admin.ModelAdmin):
    search_fields = [
        "user",
    ]


admin.site.register(User, UserAdmin)
admin.site.register(TwoFactorAuth, TwoFactorAuthAdmin)
admin.site.register(EmailVerification, EmailVerificationAdmin)
