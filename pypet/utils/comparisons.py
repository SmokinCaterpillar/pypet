__author__ = 'Robert Meyer'



import pypet.parameter
import itertools as it
from pypet.utils.helpful_functions import nested_equal

def results_equal(a,b):
    ''' Compares two result objects
    '''
    if not isinstance(a, pypet.parameter.Result) or not isinstance(b, pypet.parameter.Result):
        return False

    if not a.v_name==b.v_name:
        return False

    if not a.v_location==b.v_location:
        return False

    if not a.v_full_name == b.v_full_name:
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
    '''Compares two parameter objects'''
    if not isinstance(b, pypet.parameter.BaseParameter) or not isinstance(a, pypet.parameter.BaseParameter):
        return False

    if not a.v_name==b.v_name:
        return False

    if not a.v_location==b.v_location:
        return False

    if not a.v_full_name == b.v_full_name:
        return False

    # I allow different comments for now
    # if not a.get_comment() == b.get_comment():
    #     return False

    if not a._values_of_same_type(a.f_get(),b.f_get()):
        return False

    if not a._equal_values(a.f_get(),b.f_get()):
        return False

    if not len(a) == len(b):
        return False

    if a.f_has_range():
        for myitem, bitem in it.izip(a.f_get_range(),b.f_get_range()):
            if not a._values_of_same_type(myitem,bitem):
                return False

            if not a._equal_values(myitem,bitem):
                return False

    return True