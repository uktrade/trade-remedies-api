from django.test import TestCase, override_settings
from core.opensearch import get_open_search, OSWrapper, OSWrapperError
from opensearchpy import OpenSearch


class OpenSearchTest(TestCase):
    """Test the OpenSearch object instantiation process"""

    def test_get_open_search(self):
        """Tests that the get_open_search() function returns a working OpenSearch object"""
        opensearch_client = get_open_search()
        self.assertIsInstance(opensearch_client, OpenSearch)

    def test_get_client_cache(self):
        """Tests that the OSWrapper.get_client() method caches previous OpenSearch objects and returns them"""
        opensearch_client = get_open_search()
        self.assertIs(opensearch_client, OSWrapper._os_client)

        OSWrapper._os_client = None
        new_opensearch_client = get_open_search()

        self.assertFalse(opensearch_client is new_opensearch_client)

    @override_settings(OPENSEARCH_HOST=None, OPENSEARCH_PORT=None, OPENSEARCH_URI=None)
    def test_get_open_search_error(self):
        """Tests that without the correct environment variables, an OSWrapperError() is raised"""
        with self.assertRaises(OSWrapperError):
            get_open_search()
