__author__ = 'robert'

import tables as pt
import numpy as np

PARAMETER_SUPPORTED_DATA = [np.int8,
                       np.int16,
                       np.int32,
                       np.int64,
                       np.int,
                       np.uint8,
                       np.uint16,
                       np.uint32,
                       np.uint64,
                       np.bool,
                       np.float32,
                       np.float64,
                       np.float,
                       np.complex64,
                       np.complex,
                       np.complex,
                       np.str ]


HDF5_STRCOL_MAX_NAME_LENGTH = 1024


MULTIPROC_MODE_QUEUE = 'Queue'
MULTIPROC_MODE_NORMAL = 'Normal'


LOAD_SKELETON = 1
LOAD_DATA = 2
LOAD_NOTHING = 0
UPDATE_SKELETON = -1