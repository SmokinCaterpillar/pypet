

__author__ = 'Robert Meyer'

try:
    from ._version import __version__
except ImportError:
    # We're running in a tree that doesn't
    # have a _version.py, so we don't know what our version is.
    __version__ = "unknown"


from pypet.environment import Environment
from pypet.trajectory import Trajectory, SingleRun
from pypet.storageservice import HDF5StorageService, LazyStorageService
from pypet.naturalnaming import ParameterGroup, DerivedParameterGroup, ConfigGroup,\
    ResultGroup, NNGroupNode, NNLeafNode
from pypet.parameter import Parameter, ArrayParameter, SparseParameter,\
    PickleParameter, Result, SparseResult, PickleResult, ObjectTable, BaseParameter, BaseResult
from pypet.pypetexceptions import DataNotInStorageError, NoSuchServiceError,\
    NotUniqueNodeError, ParameterLockedException, PresettingError, TooManyGroupsError,\
    VersionMismatchError
from pypet.pypetlogging import HasLogger
from pypet.utils.explore import cartesian_product


__all__ = [
    Trajectory.__name__,
    SingleRun.__name__,
    Environment.__name__,
    HDF5StorageService.__name__,
    LazyStorageService.__name__,
    ParameterGroup.__name__,
    DerivedParameterGroup.__name__,
    ConfigGroup.__name__,
    ResultGroup.__name__,
    NNGroupNode.__name__,
    NNLeafNode.__name__,
    BaseParameter.__name__,
    Parameter.__name__,
    ArrayParameter.__name__,
    SparseParameter.__name__,
    PickleParameter.__name__,
    BaseResult.__name__,
    Result.__name__,
    SparseResult.__name__,
    PickleResult.__name__,
    ObjectTable.__name__,
    DataNotInStorageError.__name__,
    NoSuchServiceError.__name__,
    NotUniqueNodeError.__name__,
    ParameterLockedException.__name__,
    PresettingError.__name__,
    TooManyGroupsError.__name__,
    VersionMismatchError.__name__,
    HasLogger.__name__,
    cartesian_product.__name__
]
