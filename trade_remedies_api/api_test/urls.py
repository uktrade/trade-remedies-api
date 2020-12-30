from django.urls import path

from api_test.views import (
    create_test_case,
    Users,
)

from trade_remedies_api.urls import urlpatterns

urlpatterns += [
    path("api-test-obj/case/", create_test_case),
    path("api-test-obj/users/", Users.as_view(),),
    path("api-test-obj/users/<str:email>/", Users.as_view(),),
]
