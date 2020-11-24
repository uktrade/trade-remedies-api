from django.urls import path
from .api import (
    InvitationsAPIView,
    ValidateInvitationAPIView,
    InvitationDetailsAPI,
    InviteThirdPartyAPI,
    NotifyInviteThirdPartyAPI,
    ValidateUserInviteAPIView,
    UserInvitations,
)

urlpatterns = [
    path("", InvitationsAPIView.as_view()),
    path("users/", UserInvitations.as_view()),
    path("users/<uuid:invite_id>/", UserInvitations.as_view()),
    path("case/<uuid:case_id>/", InvitationsAPIView.as_view()),
    path("case/<uuid:case_id>/submission/<uuid:submission_id>/", InvitationsAPIView.as_view()),
    # path('<uuid:invitation_id>/', InvitationAPIView.as_view()),
    path("for/<uuid:contact_id>/to/<uuid:case_id>/", InvitationsAPIView.as_view()),
    path("for/<uuid:contact_id>/", InvitationsAPIView.as_view()),
    path("to/<uuid:case_id>/", InvitationsAPIView.as_view()),
    path(
        "invite/<uuid:contact_id>/to/<uuid:case_id>/as/<int:case_role_id>/",
        InvitationsAPIView.as_view(),
    ),
    path("<uuid:invitation_id>/", InvitationsAPIView.as_view()),
    path("<uuid:organisation_id>/validate/", ValidateInvitationAPIView.as_view()),
    path("accept/<uuid:code>/<uuid:case_id>/", ValidateInvitationAPIView.as_view()),
    path("validate/<uuid:code>/<uuid:organisation_id>/", ValidateUserInviteAPIView.as_view()),
    path("accept/<str:short_code>/", ValidateInvitationAPIView.as_view()),
    path("details/<uuid:code>/<uuid:case_id>/", InvitationDetailsAPI.as_view()),
    path(
        "invite/case/<uuid:case_id>/organisation/<uuid:organisation_id>/",
        InviteThirdPartyAPI.as_view(),
    ),
    path(
        "invite/case/<uuid:case_id>/submission/<uuid:submission_id>/", InviteThirdPartyAPI.as_view()
    ),
    path(
        "invite/case/<uuid:case_id>/organisation/<uuid:organisation_id>/submission/<uuid:submission_id>/",  # noqa: E501
        InviteThirdPartyAPI.as_view(),
    ),
    path(
        "case/<uuid:case_id>/submission/<uuid:submission_id>/invite/contact/<uuid:contact_id>/notify/",  # noqa: E501
        NotifyInviteThirdPartyAPI.as_view(),
    ),
]
