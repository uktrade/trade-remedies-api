from django.http import Http404
from rest_framework import viewsets
from rest_framework.response import Response


class BaseModelViewSet(viewsets.ModelViewSet):
    """
    Base class for ModelViewSets to share commonly overriden methods
    """

    def perform_create(self, serializer):
        # Overriding perform_create to return the instance, not just do it silently
        return serializer.save()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # If the object in question has been deleted, raise a 404
        if hasattr(instance, "deleted_at") and instance.deleted_at:
            raise Http404

        serializer = self.get_serializer(instance)
        return Response(serializer.data)
