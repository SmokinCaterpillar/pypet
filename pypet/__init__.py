

__author__ = 'Robert Meyer'

try:
    from ._version import __version__
except ImportError:
    # We're running in a tree that doesn't
    # have a _version.py, so we don't know what our version is.
    __version__ = "unknown"


from pypet.environment import Environment, MultiprocContext
from pypet.trajectory import Trajectory, load_trajectory
from pypet.storageservice import HDF5StorageService, LazyStorageService
from pypet.naturalnaming import ParameterGroup, DerivedParameterGroup, ConfigGroup,\
    ResultGroup, NNGroupNode, NNLeafNode, KnowsTrajectory
from pypet.parameter import Parameter, ArrayParameter, SparseParameter,\
    PickleParameter, Result, SparseResult, PickleResult, ObjectTable, BaseParameter, BaseResult
from pypet.pypetexceptions import DataNotInStorageError, NoSuchServiceError,\
    NotUniqueNodeError, ParameterLockedException, PresettingError, TooManyGroupsError,\
    VersionMismatchError, GitDiffError
from pypet.pypetlogging import HasLogger, rename_log_file
from pypet.utils.explore import cartesian_product, find_unique_points
from pypet.utils.hdf5compression import compact_hdf5_file
from pypet.utils.helpful_functions import progressbar, racedirs
from pypet.shareddata import SharedArray, SharedCArray, SharedEArray,\
    SharedVLArray, SharedPandasFrame, SharedTable, SharedResult,\
    StorageContextManager, make_ordinary_result, make_shared_result
from pypet.slots import HasSlots
from pypet.utils.trajectory_utils import merge_all_in_folder
from pypet.utils.decorators import manual_run
from pypet.utils.pypettest import test


__all__ = [
    Trajectory.__name__,
    Environment.__name__,
    MultiprocContext.__name__,
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
    GitDiffError.__name__,
    HasSlots.__name__,
    HasLogger.__name__,
    rename_log_file.__name__,
    cartesian_product.__name__,
    load_trajectory.__name__,
    compact_hdf5_file.__name__,
    KnowsTrajectory.__name__,
    StorageContextManager.__name__,
    SharedArray.__name__,
    SharedCArray.__name__,
    SharedEArray.__name__,
    SharedVLArray.__name__,
    SharedPandasFrame.__name__,
    SharedTable.__name__,
    SharedResult.__name__,
    make_ordinary_result.__name__,
    make_shared_result.__name__,
    progressbar.__name__,
    racedirs.__name__,
    find_unique_points.__name__,
    merge_all_in_folder.__name__,
    manual_run.__name__,
    test.__name__
]
