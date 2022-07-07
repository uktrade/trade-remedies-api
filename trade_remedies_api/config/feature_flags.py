from core.models import User


def is_user_part_of_group(request, user_object: User, group_name: str) -> bool:
    """
    Checks that a user object is part of a group.

    Parameters
    ----------
    request : request object
    user_object : User object
    group_name : name of a group

    Returns
    -------
    True if the user is part of that group, False otherwise.
    """
    return user_object.is_authenticated and user_object.groups.filter(name=group_name).exists()
