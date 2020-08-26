from workflow.templatetags import register
from django.utils.safestring import mark_safe


"""
A dropdown (stage/action/task)
"""


@register.simple_tag
def workflow_select(name, value, index=None, parent_id=None):
    # TODO: here was a query to get all Node models
    items = []  # Temp setting items to empty list. This will break template editor probably
    _index = index if index is not None else -1
    _parent_id = f"""'{parent_id}'""" if parent_id is not None else "null"
    js = f""" onChange="setNode('{name}', this.value, {_parent_id}, {_index});" """
    output = [f'<select {js} name="', name, '"><option value=""></option>']
    for item in items:
        selected_marker = "selected" if str(value) == str(item.id) else ""
        output.append(
            '<option value="{0}" {1}>{2}</option>'.format(str(item.id), selected_marker, item.label)
        )
    output.append("</select>")
    return mark_safe("".join(output))
