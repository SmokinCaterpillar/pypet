"""This module contains constants defined for a global scale and used across most pypet modules.

It contains constants defining the maximum length of a parameter/result name or constants
that are recognized by storage services to determine how to store and load data.

"""

__author__ = 'Robert Meyer'


import sys

####################### VERSIONS_TO_STORE ####################
from pypet._version import __version__ as VERSION
import tables
tablesversion = tables.__version__
hdf5version = tables.hdf5_version
import pandas
pandasversion = pandas.__version__
import numpy
numpyversion = numpy.__version__
import scipy
scipyversion = scipy.__version__

try:
    import platform
    platformversion = ', '.join(platform.uname())
except Exception:
    platformversion = 'N/A'

try:
    import sumatra
    sumatraversion = sumatra.__version__
except ImportError:
    sumatraversion = 'N/A'

try:
    import dill
    dillversion = dill.__version__
except ImportError:
    dillversion = 'N/A'

try:
    import psutil
    psutilversion = psutil.__version__
except ImportError:
    psutilversion = 'N/A'

try:
    import git
    gitversion = git.__version__
except ImportError:
    gitversion = 'N/A'


python_version_string = '.'.join([str(x) for x in sys.version_info[0:3]])

VERSIONS_TO_STORE = {'pypet': VERSION, 'python': python_version_string,
                     'scipy': scipyversion, 'numpy': numpyversion, 'PyTables': tablesversion,
                     'pandas': pandasversion, 'Sumatra': sumatraversion,
                     'dill': dillversion, 'GitPython': gitversion,
                     'psutil': psutilversion, 'platform': platformversion,
                     'HDF5': hdf5version}


###################### Supported Data ########################

PARAMETERTYPEDICT = {bool.__name__: bool,
                     complex.__name__: complex,
                     float.__name__: float,
                     int.__name__: int,
                     numpy.bool_.__name__: numpy.bool_,
                     numpy.complex128.__name__: numpy.complex128,
                     numpy.complex64.__name__: numpy.complex64,
                     numpy.float32.__name__: numpy.float32,
                     numpy.float64.__name__: numpy.float64,
                     numpy.int16.__name__: numpy.int16,
                     numpy.int32.__name__: numpy.int32,
                     numpy.int64.__name__: numpy.int64,
                     numpy.int8.__name__: numpy.int8,
                     numpy.string_.__name__: numpy.string_,
                     numpy.uint16.__name__: numpy.uint16,
                     numpy.uint32.__name__: numpy.uint32,
                     numpy.uint64.__name__: numpy.uint64,
                     numpy.uint8.__name__: numpy.uint8,
                     str.__name__: str,
                     bytes.__name__: bytes}
""" A Mapping (dict) from the the string representation of a type and the type.

These are the so far supported types of the storage service and the standard parameter!
"""

# For compatibility with older pypet versions:
COMPATPARAMETERTYPEDICT = {}
for key in PARAMETERTYPEDICT.keys():
    dtype = PARAMETERTYPEDICT[key]
    typestr = repr(dtype)
    if 'class' in typestr:
        # Python 3 replaced "<type 'x'>" with "<class 'x'>"
        typestr=typestr.replace('class', 'type')

    COMPATPARAMETERTYPEDICT[typestr] = dtype

PARAMETER_SUPPORTED_DATA = (numpy.int8,
                            numpy.int16,
                            numpy.int32,
                            numpy.int64,
                            numpy.int,
                            numpy.int_,
                            numpy.long,
                            numpy.uint8,
                            numpy.uint16,
                            numpy.uint32,
                            numpy.uint64,
                            numpy.bool,
                            numpy.bool_,
                            numpy.float32,
                            numpy.float64,
                            numpy.float,
                            numpy.float_,
                            numpy.complex64,
                            numpy.complex,
                            numpy.complex_,
                            numpy.str_,
                            str,
                            bytes)
"""Set of supported scalar types by the storage service and the standard parameter"""



################### HDF5 Naming and Comments ########################

HDF5_STRCOL_MAX_NAME_LENGTH = 128
"""Maximum length of a (short) name"""
HDF5_STRCOL_MAX_LOCATION_LENGTH = 512
"""Maximum length of the location string"""
HDF5_STRCOL_MAX_VALUE_LENGTH = 64
"""Maximum length of a value string"""
HDF5_STRCOL_MAX_COMMENT_LENGTH = 512
"""Maximum length of a comment """
HDF5_STRCOL_MAX_RANGE_LENGTH = 1024
"""Maximum length of a parameter array summary """
HDF5_STRCOL_MAX_RUNTIME_LENGTH = 18
"""Maximum length of human readable runtime, 18 characters allows to display up to 999 days
excluding the microseconds"""
HDF5_MAX_OVERVIEW_TABLE_LENGTH = 1000
"""Maximum number of entries in an overview table"""


######## Multiprocessing Modes #############

WRAP_MODE_QUEUE = 'QUEUE'
"""For multiprocessing, queue multiprocessing mode """
WRAP_MODE_LOCK = 'LOCK'
""" Lock multiprocessing mode """
WRAP_MODE_NONE = 'NONE'
""" No multiprocessing wrapping for the storage service"""
WRAP_MODE_PIPE = 'PIPE'
"""Pipe multiprocessing mode"""
WRAP_MODE_LOCAL = 'LOCAL'
"""Data is only stored on the local machine"""
WRAP_MODE_NETLOCK = 'NETLOCK'
""" Lock multiprocessing mode over a network """
WRAP_MODE_NETQUEUE = 'NETQUEUE'
""" Queue multiprocessing mode over a network """


############ Loading Constants ###########################

LOAD_SKELETON = 1
"""For trajectory loading, loads only the skeleton."""
LOAD_DATA = 2
""" Loads skeleton and data."""
LOAD_NOTHING = 0
""" Loads nothing """
OVERWRITE_DATA = 3
"""Overwrites all data in RAM with data from disk"""
UPDATE_SKELETON = 1
""" DEPRECATED: Updates skeleton, i.e. adds only items that are not
part of your current trajectory."""
UPDATE_DATA = 2
""" DEPRECATED: Updates skeleton and data,
adds only items that are not part of your current trajectory."""


######### Storing Constants #####

STORE_NOTHING = 0
"""Stores nothing to disk"""
STORE_DATA_SKIPPING = 1
"""Stores only data of instances that have not been stored before"""
STORE_DATA = 2
"""Stored all data to disk adds to existing data"""
OVERWRITE_DATA = OVERWRITE_DATA
"""Overwrites data on disk"""


##################### STORING Message Constants ################################

LEAF = 'LEAF'
""" For trajectory or item storage, stores a *leaf* node, i.e. parameter or result object"""
TRAJECTORY = 'TRAJECTORY'
""" Stores the whole trajectory"""
MERGE = 'MERGE'
""" Merges two trajectories """
GROUP = 'GROUP'
""" Stores a group node, can be recursive."""
LIST = 'LIST'
""" Stores a list of different things, in order to avoid reopening and closing of the hdf5 file."""
SINGLE_RUN = 'SINGLE_RUN'
""" Stores a single run"""
PREPARE_MERGE = 'PREPARE_MERGE'
""" Updates a trajectory before it is going to be merged"""
BACKUP = 'BACKUP'
""" Backs up a trajectory"""
DELETE = 'DELETE'
""" Removes an item from hdf5 file"""
DELETE_LINK = 'DELETE_LINK'
""" Removes a soft link from hdf5 file"""
TREE = 'TREE'
""" Stores a subtree of the trajectory"""
ACCESS_DATA = 'ACCESS_DATA'
""" Access and manipulate data directly in the hdf5 file """
CLOSE_FILE = 'CLOSE_FILE'
""" Close a still opened HDF5 file """
OPEN_FILE = 'OPEN_FILE'
""" Opens an HDF5 file and keeps it open until `CLOSE_FILE` is passed. """
FLUSH = 'FLUSH'
""" Tells the storage to flush the file """


########## Names of Runs ####################

FORMAT_ZEROS = 8
""" Number of leading zeros"""
RUN_NAME = 'run_'
"""Name of a single run"""
RUN_NAME_DUMMY = 'run_ALL'
"""Dummy name if not created during run"""
FORMATTED_RUN_NAME = RUN_NAME + '%0' + str(FORMAT_ZEROS) + 'd'
"""Name formatted with leading zeros"""

SET_FORMAT_ZEROS = 5
""" Number of leading zeros for set"""
SET_NAME = 'run_set_'
"""Name of a run set"""
SET_NAME_DUMMY = 'run_set_ALL'
"""Dummy name if not created during run"""
FORMATTED_SET_NAME = SET_NAME + '%0' + str(SET_FORMAT_ZEROS) + 'd'
"""Name formatted with leading zeros"""


### Constants how to store individual leaf data into HDF5 ######

ARRAY = 'ARRAY'
"""Stored as array_

.. _array: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-array-class

"""
CARRAY = 'CARRAY'
"""Stored as carray_

.. _carray: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-carray-class

"""
EARRAY = 'EARRAY'
""" Stored as earray_e.

.. _earray: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-earray-class

"""

VLARRAY = 'VLARRAY'
"""Stored as vlarray_

.. _vlarray: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-vlarray-class

"""

TABLE = 'TABLE'
"""Stored as pytable_

.. _pytable: http://pytables.github.io/usersguide/libref/structured_storage.html#the-table-class

"""

DICT = 'DICT'
""" Stored as dict.

In fact, stored as pytable, but the dictionary wil be reconstructed.
"""

FRAME = 'FRAME'
""" Stored as pandas DataFrame_

.. _DataFrame: http://pandas.pydata.org/pandas-docs/dev/io.html#hdf5-pytables

"""

SERIES = 'SERIES'
""" Store data as pandas Series """

SPLIT_TABLE = 'SPLIT_TABLE'
""" If a table was split due to too many columns"""

DATATYPE_TABLE = 'DATATYPE_TABLE'
"""If a table contains the data types instead of the attrs"""

SHARED_DATA = 'SHARED_DATA_'
""" An HDF5 data object for direct interaction """

NESTED_GROUP = 'NESTED_GROUP'
""" An HDF5 group containing nested data """

############# LOGGING ############

LOG_ENV = '$env'
"""Wildcard replaced by name of environment"""
LOG_TRAJ = '$traj'
"""Wildcard replaced by name of trajectory"""
LOG_RUN = '$run'
"""Wildcard replaced by name of current run"""
LOG_PROC = '$proc'
"""Wildcard replaced by the name of the current process"""
LOG_HOST = '$host'
"""Wildcard replaced by the name of the current host"""
LOG_SET = '$set'
"""Wildcard replaced by the name of the current run set"""

DEFAULT_LOGGING = 'DEFAULT'
"""Default logging configuration"""