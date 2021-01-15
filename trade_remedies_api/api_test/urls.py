from django.urls import path

from api_test.views import (
    OrganisationDetail,
    OrganisationList,
    UserDetail,
    UserList,
    restore_database,
)

from trade_remedies_api.urls import urlpatterns

urlpatterns += [
    path("api-test-obj/users/", UserList.as_view(),),
    path("api-test-obj/users/<str:email>/", UserDetail.as_view(),),
    path("api-test-obj/organisations/", UserList.as_view(),),
    path("api-test-obj/organisations/<str:name>/", OrganisationDetail.as_view(),),
    path("api-test-obj/reset-status/", restore_database),
]
