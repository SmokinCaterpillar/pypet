"""
Module to allow the same code to work with both Python 2 and 3.
"""

#pylint: skip-file

import sys

python_major = sys.version_info[0]
python_minor = sys.version_info[1]
python_version_string = '.'.join([str(x) for x in sys.version_info[0:3]])

if python_major == 2:

    # different types of ints
    int_types = (int, long)
    long_type = long

    # The different types of strings
    unicode_type = unicode
    bytes_type = str
    base_type = basestring

    def func_code(func): return func.func_code
    # Returns the source code of a given python function

    def tostr(string): return str(string)
    # Converts to the string type, str in python 2 and unicode in 3
    def tobytes(string): return str(string)
    # Converts a string to byte type (in python 2 str and 3 bytestr)

    def itervalues(dictionary): return dictionary.itervalues()
    # Returns an iterator over values
    def iterkeys(dictionary): return dictionary.iterkeys()
    # Returns an iterator over keys
    def iteritems(dictionary): return dictionary.iteritems()
    # Returns iterator over items
    def listkeys(dictionary): return dictionary.keys()
    # Returns a list of keys
    def listvalues(dictionary): return dictionary.values()
    # Returns a list of values
    def listitems(dictionary): return dictionary.items()
    # Returns list items

    xrange = xrange
    # Returns the iterator function range

elif python_major == 3:

    int_types = (int,)
    long_type = int

    unicode_type = str
    bytes_type = bytes
    base_type = str

    def func_code(func): return func.__code__

    def tostr(string): return str(string.decode('utf-8'))
    def tobytes(string): return string.encode('utf-8')

    def itervalues(dictionary): return dictionary.values()
    def iterkeys(dictionary): return dictionary.keys()
    def iteritems(dictionary): return dictionary.items()
    def listkeys(dictionary): return list(dictionary.keys())
    def listvalues(dictionary): return list(dictionary.values())
    def listitems(dictionary): return list(dictionary.items())

    xrange = range

else:

    raise RuntimeError('You shall not pass!')