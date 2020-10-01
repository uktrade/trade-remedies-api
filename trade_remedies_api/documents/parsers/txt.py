def parse(document):
    content = document.file.read()
    document.file.close()
    return content.decode("utf-8")
