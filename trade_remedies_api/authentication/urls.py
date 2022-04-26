"""Auth App URLs."""
from django.urls import path
from rest_framework import routers

from .views import (
    AuthenticationView,
    TwoFactorView,
    TwoFactorResendView,
    EmailVerifyView,
    EmailVerifyResendView,
    UsernameAvailableView,
    UserView,
)

urlpatterns = [
    path("login/", AuthenticationView.as_view()),
    path("two-factor/", TwoFactorView.as_view()),
    path("two-factor/resend/", TwoFactorResendView.as_view()),
    path("verify/code/<str:code>/", EmailVerifyView.as_view()),
    path("verify/resend/", EmailVerifyResendView.as_view()),
    path("email-availability/", UsernameAvailableView.as_view()),
    path("password_reset/", UsernameAvailableView.as_view()),
]

router = routers.DefaultRouter()
router.register("users", UserView, "users")
