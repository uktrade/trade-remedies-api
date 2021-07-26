from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from core.models import (
    UserProfile,
    User,
    SystemParameter,
    TwoFactorAuth,
    JobTitle,
)


class UserCreationForm(forms.ModelForm):
    """
    A form that creates a user, with no privileges, from the given email and
    password.
    """

    error_messages = {
        "password_mismatch": "The two password fields didn't match.",
    }
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput,
        help_text="Enter the same password as above, for verification.",
    )

    class Meta:
        model = User
        fields = ("email",)

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                self.error_messages["password_mismatch"], code="password_mismatch",
            )
        return password2

    def save(self, commit=True):
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text="""Raw passwords are not stored, so there is no way to see
                                         this user's password, but you can change the password
                                         using <a href=\"../password/\">this form</a>.""",
    )

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        f = self.fields.get("user_permissions")
        if f is not None:
            f.queryset = f.queryset.select_related("content_type")

    def clean_password(self):
        # Regardless of what the user provides, return the initial value.
        # This is done here, rather than on the field, because the
        # field does not have access to the initial value
        return self.initial["password"]


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "user profiles"


# Define a new User admin
class UserAdmin(UserAdmin):  # noqa
    form = UserChangeForm
    add_form = UserCreationForm
    list_display = ("email", "name", "country", "timezone", "phone", "is_staff")
    search_fields = ("userprofile__contact__country", "name", "email")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "deleted_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2"), }),
    )
    ordering = ("email",)
    inlines = (UserProfileInline,)


class SystemParameterAdmin(admin.ModelAdmin):
    list_display = ("key", "value")


class TwoFactorAuthAdmin(admin.ModelAdmin):
    readonly_fields = ("generated_at", )


class JobTitleAdmin(admin.ModelAdmin):
    pass


# Re-register UserAdmin
admin.site.register(User, UserAdmin)
admin.site.register(SystemParameter, SystemParameterAdmin)
admin.site.register(TwoFactorAuth, TwoFactorAuthAdmin)
admin.site.register(JobTitle, JobTitleAdmin)
