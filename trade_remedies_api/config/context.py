from contextlib import ContextDecorator

from config.routers import set_active_db


class db(ContextDecorator):
    def __init__(self, connection_name):
        self.connection_name = connection_name

    def __enter__(self):
        set_active_db(self.connection_name)
        return self

    def __exit__(self, *exc):
        set_active_db(None)
        return False
