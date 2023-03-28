import base64
import json

from django.core.exceptions import FieldError
from django.http import Http404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.services.base import GroupPermission

from config.serializers import (
    CustomValidationModelSerializer,
    GenericSerializerType,
    ReadOnlyModelSerializer,
)


class BaseModelViewSet(viewsets.ModelViewSet):
    """
    Base class for ModelViewSets to share commonly overriden methods
    """

    serializer_class: GenericSerializerType

    permission_classes = (IsAuthenticated, GroupPermission)

    def get_queryset(self):
        queryset = super().get_queryset()
        if filter_parameters := self.request.query_params.get("filter_parameters"):
            # there are some additional query parameters in this request, let's get the dictionary
            # and filter the queryset accordingly.
            filter_parameters = json.loads(base64.b64decode(filter_parameters))  # /PS-IGNORE
            queryset = queryset.filter(**filter_parameters)

        # removing deleted objects from the queryset
        try:
            queryset = queryset.exclude(deleted_at__isnull=False)
        except FieldError:
            # some models do not have deleted_at
            pass
        return queryset

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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["requesting_user"] = self.request.user
        return context

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())
        if fields := kwargs.get("data", {}).get("fields"):
            # We only want the serializer to have the fields mentioned here, this is to increase
            # speed primarily
            if fields == "__none__":
                # we don't want a return value from the serializer, fine with us
                fields = []
            else:
                # the fields value should be a string, with commas separating the names of fields
                fields = fields.split(",")
            kwargs.setdefault("fields", fields)
        return serializer_class(*args, **kwargs)

    def get_serializer_class(self) -> GenericSerializerType:
        """
        Return the class to use for the serializer. If the request has 'skinny: yes' in the query
        then a slim serializer will be used, this is identical to a normal serializer but without
        any of the bloated computed fields.
        """
        if "slim" in self.request.query_params:
            # they want a slim serializer without additional computed fields
            def slim_serializer_factory(model_name) -> GenericSerializerType:
                class SlimSerializer(CustomValidationModelSerializer):
                    class Meta:
                        model = model_name
                        fields = "__all__"

                    def __repr__(self):
                        return f"<SlimSerializer for {model_name}>"

                return SlimSerializer

            return slim_serializer_factory(self.queryset.model)

        if self.action == "list":

            def read_only_serializer_factory(model_name) -> GenericSerializerType:
                class ListModelSerializer(ReadOnlyModelSerializer):
                    class Meta:
                        model = model_name
                        fields = "__all__"
                        read_only_fields = fields

                    def __repr__(self):
                        return f"<ListModelSerializer for {model_name}>"

                return ListModelSerializer

            return read_only_serializer_factory(self.queryset.model)

        return super().get_serializer_class()
