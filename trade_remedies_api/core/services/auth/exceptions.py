class TwoFactorRequestedTooMany(Exception):
    """TwoFactor code could not be generated as it was generated too recently in the past"""


class AxesLockedOutException(Exception):
    """The user has been temporarily locked out from their account after too many failed attempts"""
