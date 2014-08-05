"""This module contains constants defined for a global scale and used across most pypet modules.

It contains constants defining the maximum length of a parameter/result name or constants
that are recognized by storage services to determine how to store and load data.

"""

__author__ = 'Robert Meyer'

import numpy
import pypet.compat as compat


###################### Supported Data ########################

PARAMETERTYPEDICT = {bool.__name__: bool,
                     complex.__name__: complex,
                     float.__name__: float,
                     int.__name__: int,
                     compat.long_type.__name__: compat.long_type,
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
                     compat.unicode_type.__name__: compat.unicode_type,
                     compat.bytes_type.__name__: compat.bytes_type}

""" A Mapping (dict) from the the string representation of a type and the type.

These are the so far supported types of the storage service and the standard parameter!
"""

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
                            compat.unicode_type,
                            compat.bytes_type)
"""Set of supported scalar types by the storage service and the standard parameter"""



################### HDF5 Naming and Comments ##########################


HDF5_STRCOL_MAX_NAME_LENGTH = 128
"""Maximum length of a (short) name"""
HDF5_STRCOL_MAX_LOCATION_LENGTH = 256
"""Maximum length of the location string"""
HDF5_STRCOL_MAX_VALUE_LENGTH = 64
"""Maximum length of a value string"""
HDF5_STRCOL_MAX_COMMENT_LENGTH = 512
"""Maximum length of a comment """
HDF5_STRCOL_MAX_ARRAY_LENGTH = 1024
"""Maximum length of a parameter array summary """
HDF5_STRCOL_MAX_RUNTIME_LENGTH = 18
"""Maximum length of human readable runtime, 18 characters allows to display up to 999 days
excluding the microseconds

"""
HDF5_MAX_OBJECT_TABLE_TYPE_ATTRS = 32
"""
Maximum number of attributes before a distinct table is created
"""

######## Multiprocessing Modes #############

WRAP_MODE_QUEUE = 'QUEUE'
"""For multiprocessing, queue multiprocessing mode """
WRAP_MODE_LOCK = 'LOCK'
""" Lock multiprocessing mode """
WRAP_MODE_NONE = 'NONE'
""" No multiprocessing wrapping for the storage service"""


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
TREE = 'TREE'
""" Stores a subtree of the trajectory"""



########## Names of Runs ####################
FORMAT_ZEROS = 8
""" Number of leading zeros"""
RUN_NAME = 'run_'
"""Name of a single run"""
RUN_NAME_DUMMY = 'run_ALL'
"""Dummy name if not created during run"""
FORMATTED_RUN_NAME = RUN_NAME + '%0' + str(FORMAT_ZEROS) + 'd'
"""Name formatted with leading zeros"""