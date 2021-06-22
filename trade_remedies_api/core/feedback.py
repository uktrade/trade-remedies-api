from core.exporters.writers.excel_writer import ExcelWriter
from core.utils import remove_xlsx_injection_attack_chars


def feedback_export(form):
    writer = ExcelWriter(prefix="feedback-export")
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
            row.append(
                remove_xlsx_injection_attack_chars(
                    value.value
                ) if value else ""
            )
        writer.write_row(row)
    return writer.close()
