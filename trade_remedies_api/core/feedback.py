import tempfile
from core.writers.spreadsheet import ExcelWriter


def feedback_export(form):
    outfile = tempfile.NamedTemporaryFile(mode="wb+", prefix="feedback-export", suffix=".xls")
    writer = ExcelWriter(outfile.name)
    elements = form.formelement_set.all().order_by("order", "created_at")
    collections = form.collections
    headers = ["Form", "Submitted", "Placement"] + [
        element.name or element.label or "N/A" for element in elements
    ]
    writer.write_row(headers)
    for collection in collections:
        row = [form.name, str(collection.created_at), collection.placement.id]
        for element in elements:
            value = collection.feedbackdata_set.filter(element=element).first()
            row.append(value.value if value else "")
        writer.write_row(row)
    writer.close()
    return outfile
