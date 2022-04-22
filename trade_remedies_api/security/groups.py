GROUPS = [
    ("Super User", "Has all permissions and can override security restrictions"),
    ("TRA Administrator", "TRA Administrator"),
    ("TRA Investigator", "TRA Investigator"),
    ("Head of Investigation", "Head of Investigation"),
    ("Lead Investigator", "Lead Investigator"),
    ("Organisation Owner", "A member of an organisation with owner access"),
    ("Organisation User", "A member of an organisation with standard access"),
    ("Third Party User", "A member of a third party organisation with standard access"),
]

ORGANISATION_USER_TYPES = [
    ("Organisation Owner", "A member of an organisation with owner access"),
    ("Organisation User", "A member of an organisation with standard access"),
    ("Third Party User", "A member of a third party organisation with standard access"),
]

GROUP_PERMISSIONS = {}
GROUP_PERMISSIONS["TRA Investigator"] = []
GROUP_PERMISSIONS["TRA Administrator"] = GROUP_PERMISSIONS["TRA Investigator"] + [
    "core.add_user",
    "core.change_user",
    "core.delete_user",
]
GROUP_PERMISSIONS["Organisation User"] = []
GROUP_PERMISSIONS["Organisation Owner"] = GROUP_PERMISSIONS["Organisation User"] + []
GROUP_PERMISSIONS["Third Party User"] = []

PERMISSION_MODELS = [
    "core",
]

# Any additional permissions to be assigned to the Super User
ADDITIONAL_PERMISSIONS = []

# The initial user will be assigned the Super User group which provides them with all
# permissions, and cannot be unset. New users will default to the following group
# configuration
DEFAULT_USER_PERMISSIONS = []

DEFAULT_ADMIN_PERMISSIONS = DEFAULT_USER_PERMISSIONS + [
    "Administrator",
]
