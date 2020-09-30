from odf.opendocument import load
from odf import text


def parse(document):
    content = []
    doc = load(document.file)
    for element in doc.getElementsByType(text.P):
        content.append(str(element))
    return "\n ".join(content)
