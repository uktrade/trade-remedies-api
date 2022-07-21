from rest_framework import viewsets


class BaseModelViewSet(viewsets.ModelViewSet):
    """
    Base class for ModelViewSets to share commonly overriden methods
    """

    def perform_create(self, serializer):
        # Overriding perform_create to return the instance, not just do it silently
        return serializer.save()
