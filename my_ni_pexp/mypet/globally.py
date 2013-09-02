__author__ = 'robert'

import numpy as np







PARAMETERTYPEDICT={"<type 'bool'>": bool,
 "<type 'complex'>": complex,
 "<type 'float'>": float,
 "<type 'int'>": int,
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




PARAMETER_SUPPORTED_DATA = (np.int8,
                       np.int16,
                       np.int32,
                       np.int64,
                       np.int,
                       np.int_,
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


HDF5_STRCOL_MAX_NAME_LENGTH = 128
HDF5_STRCOL_MAX_COMMENT_LENGTH = 256

SHORT_REPRESENTATION = 32

MULTIPROC_MODE_QUEUE = 'Queue'
MULTIPROC_MODE_NORMAL = 'Normal'


LOAD_SKELETON = 1
LOAD_DATA = 2
LOAD_NOTHING = 0
UPDATE_SKELETON = -1




### STORING Constants
PARAMETER = 'PARAMETER'
UPDATE_PARAMETER = 'UPDATE_PARAMETER'
UPDATE_RESULT = 'UPDATE_RESULT'
RESULT = 'RESULT'
TRAJECTORY = 'TRAJECTORY'
MERGE = 'MERGE'
LIST = 'LIST'
SINGLERUN = 'SINGLERUN'
UPDATE_TRAJECTORY = 'UPDATE_TRAJECTORY'
BACKUP = 'BACKUP'

REMOVE_PARAMETER = 'REMOVE_PARAMETER'
REMOVE_RESULT = 'REMOVE_RESULT'
REMOVE_INCOMPLETE_RUNS = 'REMOVE_INCOMPLETE_RUNS'

