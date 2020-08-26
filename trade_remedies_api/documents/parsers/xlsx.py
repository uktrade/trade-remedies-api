import xlrd


def parse(document):
    text = []
    workbook = xlrd.open_workbook(file_contents=document.file.read())
    document.file.close()
    for sheet in workbook.sheets():
        for header in sheet.row_values(0):
            text.append(header)
    return "\n".join(text)
