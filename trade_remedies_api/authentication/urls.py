"""Auth App URLs."""
from django.urls import path
from rest_framework import routers

from .views import (
    AuthenticationView,
    TwoFactorView,
    TwoFactorResendView,
    EmailVerifyView,
    EmailAvailableView,
    UserView,
)

urlpatterns = [
    path(f"login/", AuthenticationView.as_view()),
#     path(f"two-factor/", TwoFactorView, name="two-factor"),
#     path(f"two-factor/resend/", TwoFactorResendView, name="two-factor-resend"),
#     path(f"verify/", EmailVerifyView, name="email-verify"),
#     path(f"email-availability/", EmailAvailableView, name="email-availability"),
]

router = routers.DefaultRouter()
router.register(f"users", UserView, "users")
