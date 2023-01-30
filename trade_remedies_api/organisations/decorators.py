import functools

from django.db import connection, transaction

from config.exceptions import BreakNoCommitTransaction


def no_commit_transaction(func):
    """Decorator to wrap a function in a transaction that is not committed, but can still be read
    from the database. This is useful for loading data from the database into a serializer without
    committing the transaction, e.g. for previewing what an Organisation merge would look like."""

    @functools.wraps(func)
    def wrapper_no_commit_transaction(*args, **kwargs):
        with connection.cursor() as cursor:
            # setting the read level to REPEATABLE READ ensures that we can read the uncommitted
            # data from the database when loading the serializer
            cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            try:
                with transaction.atomic():
                    result = func(*args, **kwargs)
                    raise BreakNoCommitTransaction()
            except BreakNoCommitTransaction:
                pass

            # returning to the default read level, not sure if this is necessary as we are
            # using an isolated connection but doing it nonetheless
            cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")

            return result

    return wrapper_no_commit_transaction
