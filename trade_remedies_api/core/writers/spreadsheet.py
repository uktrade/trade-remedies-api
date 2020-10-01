import os
import openpyxl
import csv
import datetime
import tempfile
from django.conf import settings
from django.utils import timezone


class SpreadsheetWriter(object):
    """
    Base abstract class for a spreadsheet writer.
    The implementing classes can output csv, xls etc. but should follow the
    interface defined in this class.
    Note:
        A local filesystem file will be generated for the purpose of the audit export.
        However, it should be deleted after it is no longer required (delivered to user).
        It is recommended to use temporary files for this purpose (/tmp).
    """

    def __init__(self, file_path):
        self.file_path = file_path
        self.setup()

    def setup(self):
        """
        Perform any pre-write actions required to prepare the file for writing.
        """
        raise NotImplementedError

    def write_row(self, row):
        """
        Write a single row to the file.
        """
        raise NotImplementedError

    def close(self):
        """
        Perform any post-write actions and return the finished spreadsheet
        """
        raise NotImplementedError

    def delete(self):
        os.remove(self.file_path)


class ExcelWriter(SpreadsheetWriter):
    def setup(self):
        self.wb = openpyxl.Workbook()
        self.ws = self.wb.active

    def write_row(self, row):
        self.ws.append(row)

    def close(self):
        self.wb.save(filename=self.file_path)


class CSVWriter(SpreadsheetWriter):
    def setup(self):
        with open(self.file_path, "w") as file:
            self.file = file
            self.csv = csv.writer(self.file)

    def write_row(self, row):
        self.csv.writerow(row)

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass  # file might be closed already


class QuerysetExport(object):
    """
from core.writers import QuerysetExport
audit = Audit.objects.all().order_by('-created_at')
exporter = QuerysetExport(audit)
file = exporter.do_export()
    """

    FILE_FORMATS = {"csv": CSVWriter, "xls": ExcelWriter, "xlsx": ExcelWriter}

    def __init__(self, queryset, fields=None, file_format=None, filename=None, headers=True):
        """
        Initiate a data exporter:
        :param queryset: The queryset to export. An iterable of models.
        :param fields: Which fields to export. Will be auto generated if not provided.
        :param file_format: The type of export. One of csv|xls|xlsx
        :param filename: Postfix for the file generated.
        :param headers: True to include headers row
        """
        self.file_format = file_format or "xlsx"
        _timestamp = timezone.now().strftime(settings.API_DATETIME_FORMAT)
        self.filename = filename or f"tr-export-{_timestamp}.{self.file_format}"
        self.headers = headers
        self.fields = fields
        _mode = "w+" if self.file_format == "csv" else "wb+"
        self.file = tempfile.NamedTemporaryFile(
            mode=_mode, prefix=self.filename, suffix=f".{self.file_format}"
        )
        self.file_path = self.file.name
        self.queryset = queryset
        self.writer = self.FILE_FORMATS.get(self.file_format)(self.file_path)

    def extract_fields(self, item):
        fields = []
        item_fields = item._meta.local_fields
        for field in item_fields:
            fields.append(field.name)
        return fields

    def extract_values(self, item, fields):
        values = []
        for field in fields:
            values.append(str(getattr(item, field)))
        return values

    def do_export(self):
        """
        Iterate the queryset and generate the export.
        Models can support exports by having a to_row method implemented, which
        renders a list of (field_name, field) tuples in the order they should be used for exports.
        Failing that, the first model's fields will be used to generate a list of all
        available fields, and their string representations will be used.
        """
        headers = False
        headers_written = False
        for item in self.queryset:
            row = None
            if hasattr(item, "to_row"):
                headers, row = zip(*item.to_row())
                if self.headers and not headers_written:
                    self.writer.write_row(headers)
                    headers_written = True
            else:
                if not self.fields:  # happens on the first row
                    self.fields = self.extract_fields(item)
                    if self.headers and not headers_written:
                        self.writer.write_row(self.fields)
                        headers_written = True
                row = self.extract_values(item, self.fields)
            if row:
                self.writer.write_row(row)
        self.writer.close()
        return self.file
