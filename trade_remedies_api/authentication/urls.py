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
    path(f"two-factor/", TwoFactorView.as_view()),
    path(f"two-factor/resend/", TwoFactorResendView.as_view()),
    path(f"verify/", EmailVerifyView.as_view()),
    path(f"email-availability/", EmailAvailableView.as_view()),
]

router = routers.DefaultRouter()
router.register(f"users", UserView, "users")
