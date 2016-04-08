"""Module containing all exceptions"""

__author__ = 'Robert Meyer'


class ParameterLockedException(TypeError):
    """Exception raised if someone tries to modify a locked Parameter."""
    pass


class VersionMismatchError(TypeError):
    """Exception raised if the current version of pypet does not match the version with which
        the trajectory was handled."""
    pass


class PresettingError(RuntimeError):
    """Exception raised if parameter presetting failed.

    Probable cause might be a typo in the parameter name.

    """
    pass


class NoSuchServiceError(TypeError):
    """Exception raised by the Storage Service if a specific operation is not supported,
    i.e. the message is not understood.

    """
    pass


class NotUniqueNodeError(AttributeError):
    """Exception raised by the Natural Naming if a node can be found more than once."""
    pass


class TooManyGroupsError(TypeError):
    """Exception raised by natural naming fast search if fast search cannot be applied.
    """
    pass


class DataNotInStorageError(IOError):
    """Excpetion raise by Storage Service if data that is supposed to be loaded cannot
    be found on disk."""
    pass


class GitDiffError(RuntimeError):
    """Exception raised if there are uncommited changes."""
    pass
