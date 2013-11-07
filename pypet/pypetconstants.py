"""This module contains constants defined for a global scale and used across most pypet modules.

It contains constants defining the maximum length of a parameter/result name or constants
that are recognized by storage services to determine how to store and load data.

"""

__author__ = 'Robert Meyer'

import numpy as np


###################### Supported Data ########################

PARAMETERTYPEDICT={"<type 'bool'>": bool,
 "<type 'complex'>": complex,
 "<type 'float'>": float,
 "<type 'int'>": int,
 "<type 'long'>": long,
 "<type 'numpy.bool_'>": np.bool_,
 "<type 'numpy.complex128'>": np.complex128,
 "<type 'numpy.complex64'>": np.complex64,
 "<type 'numpy.float32'>": np.float32,
 "<type 'numpy.float64'>": np.float64,
 "<type 'numpy.int16'>": np.int16,
 "<type 'numpy.int32'>": np.int32,
 "<type 'numpy.int64'>": np.int64,
 "<type 'numpy.int8'>": np.int8,
 "<type 'numpy.string_'>": np.string_,
 "<type 'numpy.uint16'>": np.uint16,
 "<type 'numpy.uint32'>": np.uint32,
 "<type 'numpy.uint64'>": np.uint64,
 "<type 'numpy.uint8'>": np.uint8,
 "<type 'str'>": str}
""" A Mapping (dict) from the the string representation of a type and the type.

These are the so far supported types of the storage service and the standard parameter!
"""

PARAMETER_SUPPORTED_DATA = (np.int8,
                       np.int16,
                       np.int32,
                       np.int64,
                       np.int,
                       np.int_,
                       np.long,
                       np.uint8,
                       np.uint16,
                       np.uint32,
                       np.uint64,
                       np.bool,
                       np.bool_,
                       np.float32,
                       np.float64,
                       np.float,
                       np.float_,
                       np.complex64,
                       np.complex,
                       np.complex_,
                       np.str,
                       np.str_)
"""Set of supported scalar types by the storage service and the standard parameter"""



################### HDF5 Naming and Comments ##########################

HDF5_STRCOL_MAX_NAME_LENGTH = 64
"""Maximum length of a (short) name"""
HDF5_STRCOL_MAX_LOCATION_LENGTH = 128
"""Maximum length of the location string"""
HDF5_STRCOL_MAX_VALUE_LENGTH = 64
"""Maximum length of a value string"""
HDF5_STRCOL_MAX_COMMENT_LENGTH = 256
"""Maximum length of a comment """
HDF5_STRCOL_MAX_ARRAY_LENGTH = 1024
"""Maximum length of a parameter array summary """
HDF5_STRCOL_MAX_RUNTIME_LENGTH = 18
"""Maximum length of human readable runtime, 18 characters allows to display up to 999 days
excluding the microseconds

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
UPDATE_SKELETON = -1
""" Updates skeleton, i.e. adds only items that are not part of your current trajectory."""
UPDATE_DATA = -2
""" Updates skeleton and data, adds only items that are not part of your current trajectory."""


##################### STORING Message Constants ################################

LEAF ='LEAF'
""" For trajectory or item storage, stores a *leaf* node, i.e. parameter or result object"""
UPDATE_LEAF = 'UPDATE_LEAF'
""" Updates a *leaf* node, currently only parameters that are extended in length can be updated."""
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
REMOVE='REMOVE'
""" Removes an item from hdf5 file"""
REMOVE_INCOMPLETE_RUNS = 'REMOVE_INCOMPLETE_RUNS'
""" Removes incomplete runs to continue a crashed trajectory"""
TREE = 'TREE'
""" Stores a subtree of the trajectory"""


################### Search Strategies ##########################

BFS = 'BFS'
"""For search in trajectory tree, breadth first search, default strategy"""
DFS = 'DFS'
"""Depth first search in trajectory tree, not recommended"""


########## Names of Runs ####################

FORMAT_ZEROS=8
""" Number of leading zeros"""
RUN_NAME = 'run_'
"""Name of a single run"""
FORMATTED_RUN_NAME=RUN_NAME+'%0'+str(FORMAT_ZEROS)+'d'
"""Name formatted with leading zeros"""