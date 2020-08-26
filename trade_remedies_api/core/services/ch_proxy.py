import base64
import requests
from django.conf import settings
from .base import TradeRemediesApiView, ResponseSuccess
from .exceptions import InvalidRequestParams


COMPANIES_HOUSE_BASIC_AUTH = base64.b64encode(
    bytes(f"{settings.COMPANIES_HOUSE_API_KEY}:", "utf-8")
).decode("utf-8")
COMPANIES_HOUSE_BASE_DOMAIN = "https://api.companieshouse.gov.uk"


class CompaniesHouseApiSearch(TradeRemediesApiView):
    def get(self, request, *args, **kwargs):
        query = request.query_params.get("q")
        if not query:
            raise InvalidRequestParams("Missing q param")
        headers = {"Authorization": f"Basic {COMPANIES_HOUSE_BASIC_AUTH}"}
        response = requests.get(
            f"{COMPANIES_HOUSE_BASE_DOMAIN}/search/companies",
            headers=headers,
            params={"q": query, "items_per_page": 10,},
        ).json()
        return ResponseSuccess(
            {
                "results": response.get("items"),
                "total": response.get("total_results"),
                "limit": response.get("items_per_page"),
                "page_number": response.get("page_number"),
            }
        )
