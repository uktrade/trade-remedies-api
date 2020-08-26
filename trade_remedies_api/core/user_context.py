from functools import singledispatch


class UserContext:
    """
    A container for user context.
    The user context determines which user is performing the current set of actions, and
    if relevant which case worker user is assisting them (by doing it on their behalf).
    """

    def __init__(self, user, assisted_by=None):
        self.user = user
        self.assisted_by = assisted_by

    def __repr__(self):
        if self.assisted_by:
            return f"<UserContext: {self.user} assisted by {self.assisted_by}"
        else:
            return f"<UserContext: {self.user}"


# The following singledispatch calls are handy to get a user context from
# either an actual UserContext object, a list of one or two users (where the first
# is the context user and the second the assist), or a dict with keys 'user' and optional
# 'assisted_by'.


@singledispatch
def user_context(context):
    if context:
        return UserContext(context)
    else:
        return context


@user_context.register(UserContext)
def _(context):
    return context


@user_context.register(list)  # noqa
def _(context):
    return UserContext(*context)


@user_context.register(dict)  # noqa
def _(context):
    return UserContext(**context)
