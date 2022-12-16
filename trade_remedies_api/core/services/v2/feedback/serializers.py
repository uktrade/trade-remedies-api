from config.serializers import CustomValidationModelSerializer
from core.models import Feedback
from rest_framework import serializers


class FeedbackSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Feedback
        fields = "__all__"

    verbose_rating_name = serializers.ReadOnlyField(source="get_rating_display")
    verbose_what_didnt_go_so_well = serializers.SerializerMethodField()

    @staticmethod
    def get_verbose_what_didnt_go_so_well(instance):
        display_choices = dict(Feedback.what_didnt_work_so_well_choices)
        return (
            [display_choices[each] for each in instance.what_didnt_work_so_well]
            if instance.what_didnt_work_so_well
            else []
        )
