"""
Help make the same code work in both Python 2 and 3.
"""

import sys

python_version = sys.version_info[0]



if python_version == 2:

    int_types = (int, long)
    long_type = long

    unicode_type = unicode
    bytes_type = str
    base_type = basestring

    func_code = lambda func: func.func_code

    compatrange = xrange


elif python_version == 3:

    int_types = (int,)
    long_type = int

    unicode_type = str
    bytes_type = bytes
    base_type = str

    func_code = lambda func: func.__code__

    compatrange = range

else:

    raise RuntimeError('You shall not pass!')