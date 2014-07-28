"""
Help make the same code work in both Python 2 and 3.
"""

import sys

python = sys.version_info[0]

python_version_string = '.'.join([str(x) for x in sys.version_info[0:3]])

if python == 2:

    int_types = (int, long)
    long_type = long

    unicode_type = unicode
    bytes_type = str
    base_type = basestring

    func_code = lambda func: func.func_code
    tostrtype = lambda string: str(string)
    # encode = lambda string, encoding: string

    itervalues = lambda dictionary: dictionary.itervalues()
    iterkeys = lambda dictionary: dictionary.iterkeys()
    listkeys = lambda dictionary: dictionary.keys()
    listvalues = lambda dictionary: dictionary.values()
    tobytetype = lambda string: string
    # decode = lambda string, encodig: string

    xrange = xrange


elif python == 3:

    int_types = (int,)
    long_type = int

    unicode_type = str
    bytes_type = bytes
    base_type = str

    func_code = lambda func: func.__code__
    tostrtype = lambda string: str(string.decode('utf-8'))
    # encode = lambda string, encoding: string.encode(encoding)

    itervalues = lambda dictionary: dictionary.values()
    iterkeys = lambda dictionary: dictionary.keys()
    listkeys = lambda dictionary: list(dictionary.keys())
    listvalues = lambda dictionary: list(dictionary.values())

    tobytetype = lambda string: string.encode('utf-8')
    # decode = lambda string, encoding: string.decode(encoding)

    xrange = range

else:

    raise RuntimeError('You shall not pass!')