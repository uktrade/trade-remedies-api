from django.test import SimpleTestCase

from core.utils import convert_to_e164
from core.utils import remove_xlsx_injection_attack_chars, InvalidPhoneNumberFormatException


class CSVInjectionTests(SimpleTestCase):
    @staticmethod
    def test_remove_xlsx_injection_attack_chars():
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


class ConvertPhoneNumberToE164StandardFormatTests(SimpleTestCase):
    @staticmethod
    def test_checks_uk_phone_number_length_is_valid():
        valid_uk_mobile_number = "+447123456789"

        output = convert_to_e164(valid_uk_mobile_number, country="GB")

        assert len(output) == 13

    @staticmethod
    def test_checks_us_phone_number_length_is_valid():
        valid_us_mobile_number = "+17123456789"

        output = convert_to_e164(valid_us_mobile_number, country="US")

        assert len(output) == 12

    def test_displays_error_for_invalid_uk_phone_number_length(self):
        invalid_uk_mobile_number = "+4492593121"

        with self.assertRaises(InvalidPhoneNumberFormatException):
            convert_to_e164(invalid_uk_mobile_number, country="GB")

    def test_displays_error_for_invalid_us_phone_number_length(self):
        invalid_us_mobile_number = "+192593121"

        with self.assertRaises(InvalidPhoneNumberFormatException):
            convert_to_e164(invalid_us_mobile_number, country="US")
