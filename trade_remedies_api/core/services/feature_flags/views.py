from flags.sources import get_flags
from rest_framework import viewsets
from rest_framework.response import Response

from config.renderers import APIResponseRenderer
from core.services.base import ResponseSuccess
from core.services.feature_flags.serializers import FlagSerializer


class FlagViewSet(viewsets.ViewSet):
    permission_classes = ()
    authentication_classes = ()
    renderer_classes = (APIResponseRenderer,)

    def list(self, request):
        feature_flags = [value for key, value in get_flags().items()]
        serializer = FlagSerializer(feature_flags, many=True)
        return Response(serializer.data)

    def retrieve(self, request, name):

        serializer = FlagSerializer()
