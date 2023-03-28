from core.models import User
from organisations.decorators import no_commit_transaction
from django.test.testcases import TransactionTestCase

@no_commit_transaction
def to_be_decorated():
    # create a new one which will never be committed
    User.objects.create(email="test12@examle.com", name="test 12", password="test")  # /PS-IGNORE


class TestNoCommitTransaction(TransactionTestCase):
    """Test the no_commit_transaction decorator used to wrap functions
    that do not commit the transaction to the DB.
    """

    databases = "__all__"

    def test_no_commit_transaction(self):
        """Test that the no_commit_transaction decorator works as expected."""
        assert User.objects.all().count() == 0
        to_be_decorated()
        # after the function returns, the user is not committed to the DB
        assert User.objects.all().count() == 0
