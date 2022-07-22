"""trade_remedies_api URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from rest_framework import routers

from cases.services.v2.api import CaseViewSet
from rest_framework import routers

from core.services import api as core_api
from core.services.auth import views as auth_api
from core.services.registration import views as registration_api
from cases.services import api as cases_api

urlpatterns = [
    path(f"{settings.API_PREFIX}/health/", core_api.ApiHealthView.as_view()),
    path(f"{settings.API_PREFIX}/auth", auth_api.AuthenticationView.as_view()),
    path(f"{settings.API_PREFIX}/auth/email/available/", auth_api.EmailAvailabilityAPI.as_view()),
    path(
        f"{settings.API_PREFIX}/auth/2fa/",
        auth_api.TwoFactorRequestAPI.as_view(),
        name="two_factor_verify",
    ),
    path(
        f"{settings.API_PREFIX}/auth/2fa/<str:delivery_type>/",
        auth_api.TwoFactorRequestAPI.as_view(),
        name="two_factor_request",
    ),
    path(f"{settings.API_PREFIX}/auth/email/verify/", auth_api.VerifyEmailAPI.as_view()),
    path(f"{settings.API_PREFIX}/auth/email/verify/<str:code>/", auth_api.VerifyEmailAPI.as_view()),
    path(
        f"{settings.API_PREFIX}/accounts/password/request_reset/",
        auth_api.RequestPasswordReset.as_view(),
    ),
    path(
        f"{settings.API_V2_PREFIX}/accounts/password/request_reset/",
        auth_api.RequestPasswordResetV2.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/accounts/password/reset_form/", auth_api.PasswordResetForm.as_view()
    ),
    path(
        f"{settings.API_V2_PREFIX}/accounts/password/reset_form/",
        auth_api.PasswordResetFormV2.as_view(),
    ),
    path(f"{settings.API_PREFIX}/register/", auth_api.RegistrationAPIView.as_view()),
    path(f"{settings.API_PREFIX}/security/groups/", core_api.SecurityGroupsView.as_view()),
    path(
        f"{settings.API_PREFIX}/security/groups/<str:user_group>/",
        core_api.SecurityGroupsView.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/team/<uuid:organisation_id>/users/",
        core_api.PublicUserApiView.as_view(),
    ),
    # user case assignment
    path(
        f"{settings.API_PREFIX}/team/<uuid:organisation_id>/users/assign/",
        core_api.AssignUserToCaseView.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/team/<uuid:organisation_id>/users/assign/<uuid:user_id>/case/<uuid:case_id>/",
        # noqa: E501
        core_api.AssignUserToCaseView.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/team/<uuid:organisation_id>/users/assign/<uuid:user_id>/"
        f"case/<uuid:case_id>/submission/<uuid:submission_id>/",
        core_api.AssignUserToCaseView.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/team/<uuid:organisation_id>/users/assign/<uuid:user_id>/"
        f"case/<uuid:case_id>/representing/<uuid:representing_id>/",
        core_api.AssignUserToCaseView.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/team/<uuid:organisation_id>/users/assign/<uuid:user_id>/"
        f"case/<uuid:case_id>/submission/<uuid:submission_id>/representing/<uuid:representing_id>/",
        core_api.AssignUserToCaseView.as_view(),
    ),
    path(f"{settings.API_PREFIX}/team/users/", core_api.PublicUserApiView.as_view()),
    path(
        f"{settings.API_PREFIX}/team/<uuid:organisation_id>/user/<uuid:user_id>/",
        core_api.PublicUserApiView.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/team/<uuid:organisation_id>/user/",
        core_api.PublicUserApiView.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/team/<uuid:organisation_id>/user/invite/<uuid:invitation_id>/",
        core_api.PublicUserApiView.as_view(),
    ),
    path(f"{settings.API_PREFIX}/users/", core_api.UserApiView.as_view()),
    path(f"{settings.API_PREFIX}/users/<str:user_group>/", core_api.UserApiView.as_view()),
    path(f"{settings.API_PREFIX}/user/<uuid:user_id>/", core_api.UserApiView.as_view()),
    path(
        f"{settings.API_PREFIX}/user/get_user_by_email/<str:user_email>/",
        core_api.GetUserEmailAPIView.as_view(),
    ),
    path(f"{settings.API_PREFIX}/user/create/", core_api.UserApiView.as_view()),
    path(
        f"{settings.API_PREFIX}/user/organisation/<uuid:organisation_id>/create/pending/",
        core_api.CreatePendingUserAPI.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/user/organisation/<uuid:organisation_id>/update/pending/<uuid:invitation_id>/",
        # noqa: E501
        core_api.CreatePendingUserAPI.as_view(),
    ),
    path(
        f"{settings.API_PREFIX}/user/organisation/<uuid:organisation_id>/delete/pending/<uuid:invitation_id>/",
        # noqa: E501
        core_api.CreatePendingUserAPI.as_view(),
    ),
    path(f"{settings.API_PREFIX}/my-account/", core_api.MyAccountView.as_view()),
    path(f"{settings.API_PREFIX}/core/", include("core.services.urls")),
    path(f"{settings.API_PREFIX}/case/", include("cases.services.urls")),
    path(f"{settings.API_PREFIX}/cases/", include("cases.services.urls")),
    path(f"{settings.API_PREFIX}/case/<uuid:case_id>/content/", include("content.services.urls")),
    path(f"{settings.API_PREFIX}/document/", include("documents.services.urls")),
    path(f"{settings.API_PREFIX}/documents/", include("documents.services.urls")),
    path(f"{settings.API_PREFIX}/organisations/", include("organisations.services.urls")),
    path(f"{settings.API_PREFIX}/sectors/", cases_api.SectorsAPIView.as_view()),
    path(f"{settings.API_PREFIX}/audit/", include("audit.services.urls")),
    path(f"{settings.API_PREFIX}/note/", include("notes.services.urls")),
    path(f"{settings.API_PREFIX}/tasks/", include("tasks.services.urls")),
    path(f"{settings.API_PREFIX}/security/", include("security.services.urls")),
    path(f"{settings.API_PREFIX}/workflow/", include("workflow.services.urls")),
    path(f"{settings.API_PREFIX}/invitations/", include("invitations.services.urls")),
    path(f"{settings.API_PREFIX}/contact/", include("contacts.services.urls")),
    path(f"{settings.API_PREFIX}/contacts/", include("contacts.services.urls")),
    path(f"{settings.API_PREFIX}/feedback/", include("feedback.services.urls")),
    path(f"{settings.API_PREFIX}/companieshouse/", include("core.services.urls")),
    path(
        f"{settings.API_PREFIX}/v2_register/",
        registration_api.V2RegistrationAPIView.as_view(),
        name="v2_registration",
    ),
    path(
        f"{settings.API_PREFIX}/email_verify/<uuid:user_pk>/",
        registration_api.EmailVerifyAPIView.as_view(),
        name="request_email_verify",
    ),
    path(
        f"{settings.API_PREFIX}/email_verify/<uuid:user_pk>/<str:email_verify_code>",
        registration_api.EmailVerifyAPIView.as_view(),
        name="email_verify",
    ),
]

router = routers.SimpleRouter()
router.register(f"{settings.API_V2_PREFIX}/cases", CaseViewSet, basename="cases")
urlpatterns += router.urls

if settings.DJANGO_ADMIN:
    urlpatterns.append(path("admin/", admin.site.urls))
