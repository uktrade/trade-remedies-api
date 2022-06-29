from rest_framework.renderers import JSONRenderer
from rest_framework import serializers

class APIResponseRenderer(JSONRenderer):

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response_dict = {
            "success": True
        }
        if isinstance(data, dict):
            # We are trying to return the response of two or more serializers
            response_dict["response"] = {"results": {}}
            for key, value in data.items():
                response_dict["response"]["results"][key] = value
        elif hasattr(data, "serializer") and isinstance(data.serializer, serializers.BaseSerializer):
            # We're just returning one serializer, we need to find out if it contains multiple
            # objects or just one. We can do this by checking many
            response_dict["response"] = {}
            response_type = "results" if hasattr(data.serializer, "many") and data.serializer.many else "result"
            response_dict["response"][response_type] = data

        return super().render(response_dict, accepted_media_type, renderer_context)
