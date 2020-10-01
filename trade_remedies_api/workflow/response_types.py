# Response types define the default set of fields used
# when representing a workflow in a user interface.
# It is here as a default and an updated/other set can be injected into the workflow
# if neeeded. The UI rendering would have to know about those response types and
# handle their visual representation


RESPONSE_TYPES = {
    "YES_NO": {"id": 1, "name": "Yes/No", "description": "Has this been performed?"},
    "TEXT": {"id": 2, "name": "Free Text", "description": "Enter details relating to this task"},
    "OPTIONS": {"id": 3, "name": "Selection", "description": "Select one of the following options"},
    "CHECKBOX_NA": {
        "id": 4,
        "name": "Checkbox/NA",
        "description": "Answer checkbox with not applicable",
    },
    "CHECKBOX": {"id": 5, "name": "Checkbox", "description": "Tick or blank"},
    "NOTES": {"id": 6, "name": "NoteSection", "description": "Add notes or upload documents"},
    "YES_NO_NA": {"id": 7, "name": "Yes/No/NA", "description": "Three radios"},
    "TIMER": {
        "id": 8,
        "name": "Timer",
        "description": "No response from user. This is a system timer task",
    },
    "LABEL": {"id": 9, "name": "Label", "description": "Just a text label with no input"},
    "DATE": {"id": 10, "name": "Date", "description": "A date value"},
}
