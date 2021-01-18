import csv
from .base_writer import BaseWriter


class CSVWriter(BaseWriter):
    """CSV Writer."""
    def __init__(self, prefix):
        """Constructor.

        Adds CSV writer specific members.

        :param (str) prefix: prefix used for returned file's name.
        """
        self.csv = None
        super().__init__("w+", prefix, ".csv")

    def setup(self):
        """Setup override.

        Creates a csv writer using the `csv` package.
        """
        self.csv = csv.writer(self.file)

    def write_rows(self, rows):
        """Write a batch of rows to the csv file.

        :param (list) rows: a list of row value lists.
        """
        self.csv.writerows(rows)

    def write_row(self, row):
        """Write a single row to the csv file.

        :param (list) row: a list of row values.
        """
        self.csv.writerow(row)
