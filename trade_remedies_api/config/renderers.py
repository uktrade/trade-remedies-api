from rest_framework.renderers import JSONRenderer
from rest_framework import serializers


class APIResponseRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response_dict = {"success": True, "response": {}}
        if hasattr(data, "serializer"):
            # We're just returning one serializer, we need to find out if it contains multiple
            # objects or just one. We can do this by checking the many argument
            response_type = (
                "results" if hasattr(data.serializer, "many") and data.serializer.many else "result"
            )
            response_dict["response"][response_type] = data
        else:
            # We're dealing with a dictionary, presumably an exception was thrown
            response_dict = data

        return super().render(response_dict, accepted_media_type, renderer_context)
