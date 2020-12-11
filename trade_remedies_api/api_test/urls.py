from django.urls import path

from api_test.views import create_test_case

from trade_remedies_api.urls import urlpatterns

urlpatterns += [
    path("api-test-obj/case/", create_test_case),
]
