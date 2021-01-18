import logging
import tempfile


log = logging.getLogger(__name__)


class BaseWriter:
    """Base Writer.

    Base writer class. Implementations of this class publish different export formats.

    Note this class creates a `tempfile.NamedTemporaryFile` object for the
    implementation to use as a scratch file. As `NamedTemporaryFile.delete==True`
    by default, the temp file is automatically closed and deleted, do not be
    tempted to manually close it in any derived implementation.
    """

    def __init__(self, mode, prefix, suffix):
        """BaseWriter constructor.

        :param (str) mode: tempfile open mode.
        :param (str) prefix: prefix used for tmp file.
        :param (str) suffix: suffix used for tmp file.
        """
        self.file = tempfile.NamedTemporaryFile(mode=mode, prefix=prefix, suffix=suffix)
        self.setup()

    def setup(self):
        """Setup writer.

        Perform any pre-write actions required to prepare the file for writing.
        """
        raise NotImplementedError

    def write_rows(self, rows):
        """Write a batch of rows to the file.

        :param (list) rows: a list of row value lists.
        """
        raise NotImplementedError

    def write_row(self, row):
        """Write a single row.

        :param (list) row: a list of row values.
        """
        raise NotImplementedError

    def close(self):
        """Close writer.

        Override this to perform any post-write actions. Ensure scratch file
        handle is returned.
        """
        return self.file
