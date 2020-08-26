INVALID_FILE_EXTENSIONS = (
    "com",
    "exe",
    "bat",
    "js",
    "php",
    "py",
    "ps",
    "sh",
)

SEARCH_FIELD_MAP = {
    "name": "name",
    "file": "file",
    "organisation": "submissiondocument__submission__organisation_name",
    "case": "submissiondocument__submission__case__name",
    "ref": "submissiondocument__submission__case__initiated_sequence",
    "case_type": "submissiondocument__submission__case__type__name",
}

SEARCH_CONFIDENTIAL_STATUS_MAP = {
    "CONF": True,
    "NONCONF": False,
    "ALL": None,
}


INDEX_STATE_NOT_INDEXED = 0
INDEX_STATE_UNKONWN_TYPE = 1
INDEX_STATE_INDEX_FAIL = 2
INDEX_STATE_FULL_INDEX = 3

INDEX_STATES = (
    (INDEX_STATE_NOT_INDEXED, "Pending"),
    (INDEX_STATE_UNKONWN_TYPE, "Unkown type)"),
    (INDEX_STATE_INDEX_FAIL, "Index failed"),
    (INDEX_STATE_FULL_INDEX, "Full index"),
)
