from config.test_bases import CaseSetupTestMixin
from core.models import Feedback
from core.services.v2.feedback.serializers import FeedbackSerializer


class TestFeedbackSerializer(CaseSetupTestMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.feedback_object = Feedback.objects.create(
            rating=2,
            what_didnt_work_so_well=["not_enough_guidance", "other_issue"],
            logged_in=False,
            url="/",
        )

    def test_verbose_rating_name(self):
        serializer = FeedbackSerializer(instance=self.feedback_object)
        assert serializer.data["verbose_rating_name"] == "Dissatisfied"

    def test_verbose_what_didnt_go_so_well(self):
        serializer = FeedbackSerializer(instance=self.feedback_object)
        assert serializer.data["verbose_what_didnt_go_so_well"] == [
            "Not enough guidance",
            "Other issue",
        ]
