import openpyxl
from .base_writer import BaseWriter


class ExcelWriter(BaseWriter):
    """Excel writer."""

    def __init__(self, prefix):
        """Constructor.

        Adds Excel writer specific members.

        :param (str) prefix: prefix used for returned file's name.
        """
        self.wb = None
        self.ws = None
        super().__init__("wb+", prefix, ".xlsx")

    def setup(self):
        """Setup override.

        Creates workbook and worksheet.
        """
        self.wb = openpyxl.Workbook()
        self.ws = self.wb.active

    def write_rows(self, rows):
        """Write a batch of rows to spreadsheet.

        :param (list) rows: a list of row value lists.
        """
        for row in rows:
            self.ws.append(row)

    def write_row(self, row):
        """Write a single row to the spreadsheet.

        :param (list) row: a list of row values.
        """
        self.ws.append(row)

    def close(self):
        """Close override.

        Save the workbook and return file handle.
        """
        self.wb.save(filename=self.file.name)
        return super().close()
