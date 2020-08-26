import csv
from io import StringIO


def parse(document):
    file_content = document.file.read()
    document.file.close()
    content = StringIO(file_content.decode("utf-8"))
    reader = csv.reader(content)
    first_row = next(reader)
    return "\n ".join(first_row)
