import PyPDF2


def parse(document):
    text = []
    reader = PyPDF2.PdfFileReader(document.file)
    for page in reader.pages:
        text.append(page.extractText())
    return "\n ".join(text)
