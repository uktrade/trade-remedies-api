from striprtf.striprtf import rtf_to_text


def parse(document):
    content = document.file.read()
    document.file.close()
    return rtf_to_text(content.decode("utf-8"))
