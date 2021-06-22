from django.test import TestCase

from core.utils import remove_xlsx_injection_attack_chars


class CSVInjectionTests(TestCase):
    def test_remove_xlsx_injection_attack_chars(self):
        output = remove_xlsx_injection_attack_chars("==test+")
        assert output == "test+"

        output = remove_xlsx_injection_attack_chars("++test-")
        assert output == "test-"

        output = remove_xlsx_injection_attack_chars("--test@")
        assert output == "test@"

        output = remove_xlsx_injection_attack_chars("@@test=")
        assert output == "test="

        output = remove_xlsx_injection_attack_chars("@@=")
        assert output == ""
