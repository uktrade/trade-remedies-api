from django.urls import path

from api_test.views import (
    create_test_case,
    create_test_user,
    create_standard_user,
)

from trade_remedies_api.urls import urlpatterns

urlpatterns += [
    path("api-test-obj/case/", create_test_case),
    path("api-test-obj/create-standard-user/", create_standard_user,),
    path("api-test-obj/create-user/<email>/<password>/<group>", create_test_user,),
]
