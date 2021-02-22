from django.test import TestCase
from content.models import Content
from cases.models import Case
from core.models import User


PASSWORD = "A7Hhfa!jfaw@f"


class ContentTest(TestCase):

    def setUp(self):
        self.caseworker = User.objects.create(email="case@worker.com", name="Case Worker")
        self.user = User.objects.create_user(
            name="standard user",
            email="standard@test.com",
            password=PASSWORD,
            assign_default_groups=False,
        )
        self.case = Case.objects.create(name="Test Case", created_by=self.user)

    def test_content_hierarchy(self):
        parent_content_1 = Content.objects.create(
            case=self.case,
            name="Parent Content 1",
            short_name="Parent",
            content="Some content comes here",
        )
        Content.objects.create(
            case=self.case,
            name="Parent Content 2",
            short_name="Parent 2",
            content="Some more content comes here",
        )
        Content.objects.create(
            case=self.case,
            name="Child Content 1",
            short_name="Child 1",
            content="Sub section content",
            parent=parent_content_1,
        )
        Content.objects.create(
            case=self.case,
            name="Child Content 2",
            short_name="Child 2",
            content="Sub section content",
            parent=parent_content_1,
        )
        top_level = Content.objects.content_branch(self.case, root=None)
        assert len(top_level) == 2
        tree = [node.to_embedded_dict() for node in top_level]
        assert len(tree) == 2
        assert len(tree[0]["children"]) == 2
        assert tree[0]["children"][1]["short_name"] == "Child 2"
