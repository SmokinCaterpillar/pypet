__author__ = 'robert'

import tables as pt
import numpy as np

HDF5_TRANSLATIONDICT = {np.int8:pt.Int8Col,
                       np.int16:pt.Int16Col,
                       np.int32:pt.Int32Col,
                       np.int64:pt.Int64Col,
                       np.int:pt.IntCol,
                       np.uint8:pt.UInt8Col,
                       np.uint16:pt.UInt16Col,
                       np.uint32:pt.UInt32Col,
                       np.uint64:pt.UInt64Col,
                       np.bool:pt.BoolCol,
                       np.float32:pt.Float32Col,
                       np.float64:pt.Float64Col,
                       np.float:pt.Float64Col,
                       np.complex64:pt.Complex64Col,
                       np.complex:pt.Complex128Col,
                       np.complex:pt.Complex128Col,
                       np.str:pt.StringCol }

PARAMETER_SUPPORTED_DATA = HDF5_TRANSLATIONDICT.keys()

HDF5_STRCOL_MAX_NAME_LENGTH = 1024