from contextvars import ContextVar

active_db = ContextVar("DB to use", default=None)


def get_active_db():
    # return default connection if not set
    db = active_db.get(None)
    return db if db else "default"


def set_active_db(connection_name):
    return active_db.set(connection_name)


class DynamicDatabaseRouter:
    @staticmethod
    def _get_db(*args, **kwargs):
        db = get_active_db()
        return db

    db_for_read = _get_db
    db_for_write = _get_db
