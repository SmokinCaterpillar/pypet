__author__ = 'Robert Meyer'



import mypet.parameter
import itertools as it
from mypet.utils.helpful_functions import nested_equal

def results_equal(a,b):
    if not isinstance(a, mypet.parameter.Result) or not isinstance(b, mypet.parameter.Result):
        return False

    if not a.get_name()==b.get_name():
        return False

    if not a.get_location()==b.get_location():
        return False

    if not a.get_fullname() == b.get_fullname():
        return False



    akeyset = set(a._data.keys())
    bkeyset = set(b._data.keys())

    if akeyset != bkeyset:
        return False

    for key, val in a._data.iteritems():
        bval = b._data[key]

        if not nested_equal(val,bval):
            return False


    return True

def parameters_equal(a,b):
    if not isinstance(b, mypet.parameter.BaseParameter) or not isinstance(a, mypet.parameter.BaseParameter):
        return False

    if not a.get_name()==b.get_name():
        return False

    if not a.get_location()==b.get_location():
        return False

    if not a.get_fullname() == b.get_fullname():
        return False

    # I allow different comments for now
    # if not a.get_comment() == b.get_comment():
    #     return False

    if not a._values_of_same_type(a.get(),b.get()):
        return False

    if not a._equal_values(a.get(),b.get()):
        return False

    if not len(a) == len(b):
        return False

    if a.is_array():
        for myitem, bitem in it.izip(a.get_array(),b.get_array()):
            if not a._values_of_same_type(myitem,bitem):
                return False

            if not a._equal_values(myitem,bitem):
                return False

    return True