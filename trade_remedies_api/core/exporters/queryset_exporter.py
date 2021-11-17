import types
import logging
from django.conf import settings
from django.utils import timezone
from .writers import CSVWriter
from .writers import ExcelWriter

log = logging.getLogger(__name__)


class QuerysetExporter:
    """Queryset Exporter.

    Export a queryset using one of the available export formats defined in FILE_FORMATS.
    Usage:

    from core.writers import QuerysetExport
    data = SomeModel.objects.all().order_by('-created_at').iterator()
    exporter = QuerysetExport(data)
    file = exporter.do_export()

    NB: The class expects a generator provided by django.db.models.query.QuerySet.iterator
    """

    FILE_FORMATS = {"csv": CSVWriter, "xlsx": ExcelWriter}
    BATCH_SIZE = 2000

    def __init__(self, queryset, file_format="xlsx", prefix="tr-export"):
        """Constructor.

        Initialise a queryset export.

        :param (generator) queryset: A generator for the queryset to export.
        :param file_format: The type of export. One of csv|xlsx
        :raises:
          ValueError if an unsupported export format is specified
          ValueError if queryset is not a generator
        """
        if file_format not in self.FILE_FORMATS:
            raise ValueError(f"Unsupported export format: {file_format}")
        if not isinstance(queryset, types.GeneratorType):
            raise ValueError("queryset must be a generator")
        self.queryset = queryset
        timestamp = timezone.now().strftime(settings.API_DATETIME_FORMAT)
        self.writer = self.FILE_FORMATS.get(file_format)(prefix=f"{prefix}-{timestamp}-")

    def publish_compatible_model(self, first):
        """Publish helper for a compatible model.

        :param (Model) first: A django model with row_columns and row_values methods.
        """
        fields = first.row_columns()
        batch = [fields, first.row_values()]
        for item in self.queryset:
            if len(batch) >= self.BATCH_SIZE:
                self.writer.write_rows(batch)
                batch = []
            batch.append(item.row_values())
        self.writer.write_rows(batch)

    def publish_generic_model(self, first):
        """Publish helper for any model.

        :param (django.db.models.Model) first: A django model.
        """
        fields = [f.name for f in first._meta.local_fields]  # noqa
        fmt = ','.join([f'{{item.{i}}}' for i in fields])
        first = fmt.format(item=first).split(',')
        batch = [fields, first]
        for item in self.queryset:
            if len(batch) >= self.BATCH_SIZE:
                self.writer.write_rows(batch)
                batch = []
            batch.append(fmt.format(item=item).split(','))
        self.writer.write_rows(batch)

    def do_export(self, compatible=False):
        """Export a queryset.

        A 'compatible' model set can be supplied, which has `row_columns` and
        `row_values` helper methods. `row_columns` should return a list of
        strings representing export column names. `row_values` should be an equal
        length list, containing values for each column. Pay special attention to
        the performance of these helpers if the data is large.

        :param (bool) compatible: True if the models provided are 'compatible',
          treated as standard models otherwise.
        :returns (tempfile._TemporaryFileWrapper): A file handle to a temporary file.
        """
        try:
            first = next(self.queryset)
        except StopIteration:
            log.info("Export requested for empty queryset")
            self.writer.write_row(["NO EXPORT DATA FOUND"])
        else:
            if compatible:
                self.publish_compatible_model(first)
            else:
                self.publish_generic_model(first)
        self.writer.close()
        return self.writer.file
