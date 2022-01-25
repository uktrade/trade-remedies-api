from django.test import TestCase
from core.models import SystemParameter
from django.contrib.contenttypes.models import ContentType
from documents.models import Document


class SystemParameterTest(TestCase):
    """
    Test system parameters across various configurations
    """

    def setUp(self):
        doc_content_type = ContentType.objects.get(app_label="documents", model="document")
        document_1 = Document.objects.create(name="Doc 1")
        document_2 = Document.objects.create(name="Doc 2")
        # list of models
        SystemParameter.objects.create(
            key="MODELS",
            data_type="list",
            value=[str(document_1.id), str(document_2.id)],
            content_type=doc_content_type,
        )
        # list of string
        SystemParameter.objects.create(key="STRING_LIST", value=["one", "two"])
        # string
        SystemParameter.objects.create(key="STRING", value="str_value")
        # dict value
        SystemParameter.objects.create(key="DICT", value={"one": 1, "two": 2})

    def test_list_with_content_type(self):
        value = SystemParameter.get("MODELS")
        assert len(value) == 2
        assert isinstance(value[0], Document)

    def test_list_of_string(self):
        value = SystemParameter.get("STRING_LIST")
        assert len(value) == 2
        assert isinstance(value[0], str)
        assert value[1] == "two"

    def test_string_value(self):
        value = SystemParameter.get("STRING")
        assert value == "str_value"

    def test_dict_value(self):
        value = SystemParameter.get("DICT")
        assert isinstance(value, dict)
        assert value["one"] == 1
        assert value["two"] == 2
