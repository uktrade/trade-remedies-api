import base64
import json
import typing

from django.core.exceptions import FieldError
from django.http import Http404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from v2_api_client.shared.logging import audit_logger

from config.ratelimit import get_rate
from config.serializers import (
    CustomValidationModelSerializer,
    GenericSerializerType,
    ReadOnlyModelMixinSerializer,
)
from core.services.base import GroupPermission


@method_decorator(ratelimit(key="user_or_ip", rate=get_rate, method=ratelimit.ALL), name="dispatch")
class BaseModelViewSet(viewsets.ModelViewSet):
    """
    Base class for ModelViewSets to share commonly overriden methods
    """

    serializer_class: typing.Union[GenericSerializerType, None] = None
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

        serializer_class = self.get_serializer_class()
        if hasattr(serializer_class, "eager_load_queryset"):
            queryset = self.get_serializer_class().eager_load_queryset(queryset)

        return queryset

    def initialize_request(self, request, *args, **kwargs):
        """
        Set the `.action` attribute on the view, depending on the request method.
        """
        request = super().initialize_request(request, *args, **kwargs)

        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        object_id = self.kwargs.get(lookup_url_kwarg, "N/A")
        audit_logger.info(
            f"API V2 - {self.action} operation",
            extra={
                "user": request.user.id,
                "model": (
                    self.serializer_class.Meta.model.__name__ if self.serializer_class else "N/A"
                ),
                "id": object_id,
                "view": self.__class__.__name__,
                "url": self.request.path,
            },
        )
        return request

    def perform_create(self, serializer):
        # Overriding perform_create to return the instance, not just do it silently
        new_instance = serializer.save()
        audit_logger.info(
            "API V2 - ViewSet create operation",
            extra={
                "user": self.request.user.id,
                "model": new_instance.__class__.__name__,
                "id": new_instance.id,
                "view": self.__class__.__name__,
            },
        )
        return new_instance

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

    def get_serializer_class(self):
        """
        Return the class to use for the serializer. If the request has 'skinny: yes' in the query
        then a slim serializer will be used, this is identical to a normal serializer but without
        any of the bloated computed fields.
        """
        if "slim" in self.request.query_params:
            # they want a slim serializer without additional computed fields
            def slim_serializer_factory(model_name):
                class SlimSerializer(CustomValidationModelSerializer):
                    class Meta:
                        model = model_name
                        fields = "__all__"

                    def __repr__(self):
                        return f"<SlimSerializer for {model_name}>"

                if self.request.method == "GET":
                    # if it's also a GET method, we can initialise a
                    # read-only serializer to speed up the request
                    SlimSerializer.__bases__ = (
                        ReadOnlyModelMixinSerializer,
                    ) + SlimSerializer.__bases__

                return SlimSerializer

            return slim_serializer_factory(self.queryset.model)

        if self.request.method == "GET":
            # it's a GET method, we can initialise a read-only serializer to speed up the request
            # https://hakibenita.com/django-rest-framework-slow
            def read_only_serializer_factory(model_name, model_serializer):
                class ReadOnlyModelSerializer(ReadOnlyModelMixinSerializer, model_serializer):
                    def __repr__(self):
                        return f"<ReadOnlyModelSerializer for {model_name}>"

                return ReadOnlyModelSerializer

            return read_only_serializer_factory(self.queryset.model, self.serializer_class)

        return super().get_serializer_class()
