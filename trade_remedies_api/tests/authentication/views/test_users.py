import json
import pytest


pytestmark = [pytest.mark.version2, pytest.mark.functional, pytest.mark.django_db]


def test_user_list(authorised_api_client):
    response = authorised_api_client.get("/api/v2/auth/users/")
    assert response.status_code == 200
    assert len(json.loads(response.content))


def test_user_list_unauthorised(unauthorised_api_client):
    response = unauthorised_api_client.get("/api/v2/auth/users/")
    assert response.status_code == 401
    data = json.loads(response.content)
    assert data["detail"] == "Invalid token."
