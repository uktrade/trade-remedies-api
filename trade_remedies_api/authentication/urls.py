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
    path("login/", AuthenticationView.as_view()),
    path("two-factor/", TwoFactorView.as_view()),
    path("two-factor/resend/", TwoFactorResendView.as_view()),
    path("verify/", EmailVerifyView.as_view()),
    path("email-availability/", EmailAvailableView.as_view()),
]

router = routers.DefaultRouter()
router.register("users", UserView, "users")
