__version__ = "unknown"
try:
    from _version import __version__
except ImportError:
    # We're running in a tree that doesn't
    # have a _version.py, so we don't know what our version is.
    pass

from pypet.trajectory import Trajectory, SingleRun
from pypet.environment import Environment
from pypet.storageservice import HDF5StorageService, LazyStorageService
from pypet.naturalnaming import ParameterGroup, DerivedParameterGroup, ConfigGroup, \
    ResultGroup, NNGroupNode, NNLeafNode
from pypet.parameter import BaseParameter, Parameter, ArrayParameter, SparseParameter, PickleParameter, \
    BaseResult, Result, SparseResult, PickleResult, ObjectTable
from pypetexceptions import *
from pypet.pypetlogging import HasLogger