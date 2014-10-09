"""Module containing all exceptions"""

__author__ = 'Robert Meyer'


class ParameterLockedException(TypeError):
    """Exception raised if someone tries to modify a locked Parameter."""

    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return repr(self._msg)


class VersionMismatchError(TypeError):
    """Exception raised if the current version of pypet does not match the version with which
        the trajectory was handled."""

    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return repr(self._msg)


class PresettingError(Exception):
    """Exception raised if parameter presetting failed.

    Probable cause might be a typo in the parameter name.

    """

    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return repr(self._msg)


class NoSuchServiceError(TypeError):
    """Exception raised by the Storage Service if a specific operation is not supported,
    i.e. the message is not understood.

    """

    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return repr(self._msg)


class NotUniqueNodeError(AttributeError):
    """Exception raised by the Natural Naming if a node can be found more than once."""

    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return repr(self._msg)


class TooManyGroupsError(TypeError):
    """Exception raised by natural naming fast search if fast search cannot be applied.
    """

    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return repr(self._msg)


class DataNotInStorageError(IOError):
    """Excpetion raise by Storage Service if data that is supposed to be loaded cannot
    be found on disk."""

    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return repr(self._msg)
