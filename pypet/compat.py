"""
Module to allow the same code to work with both Python 2 and 3.
"""

import sys

python = sys.version_info[0]
python_version_string = '.'.join([str(x) for x in sys.version_info[0:3]])

if python == 2:

    # different types of ints
    int_types = (int, long)
    long_type = long

    # The different types of strings
    unicode_type = unicode
    bytes_type = str
    base_type = basestring

    func_code = lambda func: func.func_code
    # Returns the source code of a given python function

    tostr = lambda string: str(string)
    # Converts to the string type, str in python 2 and unicode in 3
    tobytes = lambda string: str(string)
    # Converts a string to byte type (in python 2 str and 3 bytestr)

    itervalues = lambda dictionary: dictionary.itervalues()
    # Returns an iterator over values
    iterkeys = lambda dictionary: dictionary.iterkeys()
    # Returns an iterator over keys
    iteritems = lambda dictionary: dictionary.iteritems()
    # Returns iterator over items
    listkeys = lambda dictionary: dictionary.keys()
    # Returns a list of keys
    listvalues = lambda dictionary: dictionary.values()
    # Returns a list of values
    listitems = lambda dictionary: dictionary.items()
    # Returns list items

    xrange = xrange
    # Returns the iterator function range

elif python == 3:

    int_types = (int,)
    long_type = int

    unicode_type = str
    bytes_type = bytes
    base_type = str

    func_code = lambda func: func.__code__

    tostr = lambda string: str(string.decode('utf-8'))
    tobytes = lambda string: string.encode('utf-8')

    itervalues = lambda dictionary: dictionary.values()
    iterkeys = lambda dictionary: dictionary.keys()
    iteritems = lambda dictionary: dictionary.items()
    listkeys = lambda dictionary: list(dictionary.keys())
    listvalues = lambda dictionary: list(dictionary.values())
    listitems = lambda dictionary: list(dictionary.items())

    xrange = range

else:

    raise RuntimeError('You shall not pass!')