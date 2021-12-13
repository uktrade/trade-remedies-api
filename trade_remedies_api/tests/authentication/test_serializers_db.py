import pytest

from rest_framework import serializers
import authentication.models as auth_models
import authentication.serializers as auth_serializers


pytestmark = pytest.mark.version2


def test_get_user_helper(fake_user):
    with pytest.raises(serializers.ValidationError) as e:
        auth_serializers.TwoFactorTokenSerializer.get_user("no-such-username")
    assert "User does not exist" in str(e)


def test_user_serializer(fake_user):
    queryset = auth_models.User.objects.all()
    serializer = auth_serializers.UserSerializer(queryset, many=True)
    assert len(serializer.data) == 1
    with pytest.raises(KeyError):
        _ = serializer.data[0]["password"]
