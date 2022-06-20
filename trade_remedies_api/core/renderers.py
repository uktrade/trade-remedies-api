from rest_framework.renderers import JSONRenderer


class APIResponseRenderer(JSONRenderer):

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response_type = "result" if len(data) == 1 else "results"

        response = {
            'success': True,
            'response': {response_type: data}
        }

        return super().render(response, accepted_media_type, renderer_context)
