from django.urls import path

from api_test.views import (
    create_test_case,
    create_test_user,
)

from trade_remedies_api.urls import urlpatterns

urlpatterns += [
    path("api-test-obj/case/", create_test_case),
    path(
        "api-test-obj/create-test-user/<str:email>/<str:password>/<str:group>/", create_test_user,
    ),
]
