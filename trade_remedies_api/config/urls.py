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
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from rest_framework import routers
from rest_framework.response import Response
from rest_framework.views import APIView

from cases.services import api as cases_api
from cases.services.v2.views import CaseViewSet, SubmissionTypeViewSet, SubmissionViewSet
from core.views import health_check
from core.services import api as core_api
from core.services.auth import views as auth_api
from core.services.v2.feature_flags.views import FlagViewSet
from core.services.v2.feedback.views import FeedbackViewSet
from core.services.v2.registration import views as registration_api
from core.services.v2.users.views import ContactViewSet, TwoFactorAuthViewSet, UserViewSet
from documents.services.v2.views import DocumentBundleViewSet, DocumentViewSet
from invitations.services.v2.views import InvitationViewSet
from organisations.services.v2.views import OrganisationCaseRoleViewSet, OrganisationViewSet

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
router.register(f"{settings.API_V2_PREFIX}/submissions", SubmissionViewSet, basename="submissions")
router.register(
    f"{settings.API_V2_PREFIX}/organisations", OrganisationViewSet, basename="organisations"
)
router.register(
    f"{settings.API_V2_PREFIX}/organisation_case_roles",
    OrganisationCaseRoleViewSet,
    basename="organisation_case_roles",
)
router.register(f"{settings.API_V2_PREFIX}/documents", DocumentViewSet, basename="documents")
router.register(
    f"{settings.API_V2_PREFIX}/submission_types", SubmissionTypeViewSet, basename="submission_types"
)
router.register(
    f"{settings.API_V2_PREFIX}/document_bundles", DocumentBundleViewSet, basename="document_bundles"
)
router.register(f"{settings.API_V2_PREFIX}/submissions", SubmissionViewSet, basename="submissions")
router.register(f"{settings.API_V2_PREFIX}/invitations", InvitationViewSet, basename="invitations")
router.register(f"{settings.API_V2_PREFIX}/users", UserViewSet, basename="users")
router.register(f"{settings.API_V2_PREFIX}/contacts", ContactViewSet, basename="contacts")
router.register(
    f"{settings.API_V2_PREFIX}/two_factor_auths", TwoFactorAuthViewSet, basename="two_factor_auths"
)
router.register(
    f"{settings.API_V2_PREFIX}/django-feature-flags", FlagViewSet, basename="django-feature-flags"
)
router.register(f"{settings.API_V2_PREFIX}/feedback", FeedbackViewSet, basename="feedback")
urlpatterns += router.urls

if settings.DEBUG:
    urlpatterns.append(path("server_error", lambda x: 1 / 0))

    class ClientError(APIView):
        authentication_classes = ()

        def get(self, request, *args, **kwargs):
            return Response(status=402, data="client error")

    urlpatterns.append(path("client_error", ClientError.as_view()))

if settings.DJANGO_ADMIN:
    urlpatterns.append(path("admin/", admin.site.urls))

urlpatterns.append(path("healthcheck", health_check, name="healthcheck"))
