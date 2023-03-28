from django.test import TestCase, override_settings

from core.models import User
from core.opensearch import get_open_search, OSWrapper, OSWrapperError
from opensearchpy import OpenSearch

from organisations.decorators import no_commit_transaction


class TestNoCommitTransaction(TestCase):
    """Test the no_commit_transaction decorator used to wrap functions
    that do not commit the transaction to the DB.
    """

    def test_no_commit_transaction(self):
        """Test that the no_commit_transaction decorator works as expected."""

        # normally 1 user in DB
        assert User.objects.all().count() == 0

        @no_commit_transaction
        def to_be_decorated():
            # create a new one which will never be committed
            User.objects.create(
                email="test12@examle.com", name="test 12", password="test"  # /PS-IGNORE
            )
            # checks that it exists within the function
            assert User.objects.all().count() == 1

        to_be_decorated()
        # after the function returns, the user is not committed to the DB
        assert User.objects.all().count() == 0
