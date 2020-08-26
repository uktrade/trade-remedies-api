from unittest.mock import patch

from django.test import TestCase

from core.feature_flags import FeatureFlags, FeatureFlagNotFound
from cases.tests.test_case import load_system_params


class CaseAPITest(TestCase):
    def setUp(self):
        load_system_params()
        self.feature_flags = FeatureFlags()

    @patch("core.feature_flags.SystemParameter.get")
    @patch("core.feature_flags.cache")
    def test_get_when_true(self, cache, get_param):
        get_param.return_value = 1
        cache.get.return_value = None

        self.assertTrue(self.feature_flags("my_flag"))
        get_param.assert_called_once_with("FEATURE_MY_FLAG")
        cache.get.assert_called_once_with("FF:FEATURE_MY_FLAG")
        cache.set.assert_called_once_with("FF:FEATURE_MY_FLAG", True, 300)

    @patch("core.feature_flags.SystemParameter.get")
    @patch("core.feature_flags.cache")
    def test_get_when_false(self, cache, get_param):
        get_param.return_value = 0
        cache.get.return_value = None

        self.assertFalse(self.feature_flags("my_flag"))
        get_param.assert_called_once_with("FEATURE_MY_FLAG")
        cache.get.assert_called_once_with("FF:FEATURE_MY_FLAG")
        cache.set.assert_called_once_with("FF:FEATURE_MY_FLAG", False, 300)

    @patch("core.feature_flags.SystemParameter.get")
    @patch("core.feature_flags.cache")
    def test_get_when_cached(self, cache, get_param):
        cache.get.return_value = True

        self.assertTrue(self.feature_flags("my_flag"))
        self.assertEqual(get_param.call_count, 0)
        cache.get.assert_called_once_with("FF:FEATURE_MY_FLAG")
        self.assertEqual(cache.set.call_count, 0)

    @patch("core.feature_flags.SystemParameter.get")
    @patch("core.feature_flags.cache")
    def test_get_when_not_found(self, cache, get_param):
        cache.get.return_value = None
        get_param.return_value = None

        with self.assertRaises(FeatureFlagNotFound):
            self.feature_flags("my_flag")
            self.assertEqual(get_param.call_count, 0)
            cache.get.assert_called_once_with("FF:FEATURE_MY_FLAG")
            self.assertEqual(cache.set.call_count, 0)
