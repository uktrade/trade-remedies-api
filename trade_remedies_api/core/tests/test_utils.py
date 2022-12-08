from django.test import TestCase

from core.utils import remove_xlsx_injection_attack_chars

from core.utils import convert_to_e164



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

    def test_checks_phone_number_length_is_valid(self):

        valid_uk_mobile_number = "+447123456789"

        output = convert_to_e164(valid_uk_mobile_number)

        assert len(output) == 13


