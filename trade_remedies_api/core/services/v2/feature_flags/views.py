from flags.sources import get_flags
from rest_framework import viewsets
from rest_framework.response import Response

from config.renderers import APIResponseRenderer
from core.services.v2.feature_flags.serializers import FlagSerializer
from rest_framework import exceptions


class FlagViewSet(viewsets.ViewSet):
    """
    GenericViewSet to retrieve feature flags in the codebase.
    """

    renderer_classes = (APIResponseRenderer,)

    def dispatch(self, request, *args, **kwargs):
        self.flags = get_flags()
        return super().dispatch(request, *args, **kwargs)

    def list(self, request):
        feature_flags = [value for key, value in self.flags.items()]
        serializer = FlagSerializer(feature_flags, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk):
        if pk in self.flags:
            flag_serializer = FlagSerializer(self.flags[pk])
            return Response(flag_serializer.data)
        else:
            raise exceptions.NotFound()
