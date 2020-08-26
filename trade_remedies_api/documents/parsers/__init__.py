"""
This serves as an index of all implemented parsers, extracting text
from various file formats. One of the main goals was to remain
in python and not utilise any external binaries.  This limits the
file format selection as we cannot parse old doc and ppt files or
perform image ocr or audio/video transcribing.

However, if at any point these are needed, two main options exist:
utilise the (experimental) apt buildpack and install either
- textract - brings many utilities to extract text into python
- apache tika - the elephant of doc conversions

In either case, all that is then neeeded is to amment the parse method
of each parser to utilise the selected solution.
"""
from . import (
    docx,
    pdf,
    odt,
    xlsx,
    pptx,
    txt,
    csv,
    rtf,
)


parsers = {
    "docx": {"parse": docx.parse},
    "pdf": {"parse": pdf.parse},
    "odt": {"parse": odt.parse},
    "xls": {"parse": xlsx.parse},
    "xlsx": {"parse": xlsx.parse},
    "pptx": {"parse": pptx.parse},
    "txt": {"parse": txt.parse},
    "csv": {"parse": csv.parse},
    "rtf": {"parse": rtf.parse},
}
