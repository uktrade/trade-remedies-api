from django.test import TestCase

from core.utils import remove_xlsx_injection_attack_chars, InvalidPhoneNumberFormatException

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


class ConvertPhoneNumberToE164StandardFormatTests(TestCase):
    @staticmethod
    def test_checks_uk_phone_number_length_is_valid():
        valid_uk_mobile_number = "+447123456789"

        output = convert_to_e164(valid_uk_mobile_number, country="GB")

        assert len(output) == 13

    def test_displays_error_for_invalid_uk_phone_number_length(self):
        invalid_uk_mobile_number = "+4492593121"

        with self.assertRaises(InvalidPhoneNumberFormatException):
            convert_to_e164(invalid_uk_mobile_number, country="GB")
