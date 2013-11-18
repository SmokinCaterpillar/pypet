from collections import Sequence, Mapping, Set
import numpy as np
import pandas as pd
from pypet import pypetconstants

__author__ = 'Robert Meyer'



import pypet.parameter
import itertools as it


def results_equal(a,b):
    """Compares two result instances

    Checks full name and all data. Does not consider the comment.

    :return: True or False

    :raises: ValueError if both inputs are no result instances

    """
    if not isinstance(a, pypet.parameter.Result) and not isinstance(b, pypet.parameter.Result):
        raise ValueError('Both inputs are not results.')

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
    """Compares two parameter instances

    Checks full name, data, and ranges. Does not consider the comment.

    :return: True or False

    :raises: ValueError if both inputs are no parameter instances

    """
    if not isinstance(b, pypet.parameter.BaseParameter) and not isinstance(a, pypet.parameter.BaseParameter):
        raise ValueError('Both inputs are not parameters')

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


def nested_equal(a, b):
    """Compares two objects recursively by their elements, also handling numpy objects.

    Assumes hashable items are not mutable in a way that affects equality.
    Based on the suggestion from HERE_, thanks again Lauritz V. Thaulow :-)

    .. _HERE: http://stackoverflow.com/questions/18376935/best-practice-for-equality-in-python

    """
    if id(a) == id(b):
        return True

    # for types that support __eq__
    if hasattr(a,'__eq__'):
        try:
            custom_eq= a == b
            if isinstance(custom_eq,bool):
                return custom_eq
        except ValueError:
            pass

    #Check equality according to type type [sic].
    if a is None:
        return b is None
    if isinstance(a, basestring):
         return a == b
    if isinstance(a, pypetconstants.PARAMETER_SUPPORTED_DATA):
        return a==b
    if isinstance(a, np.ndarray):
        return np.all(a==b)
    if isinstance(a, pd.DataFrame):
        try:
            new_frame = a == b
            new_frame = new_frame |( pd.isnull(a) & pd.isnull(b))
            return np.all(new_frame.as_matrix())
        except ValueError:
            # The Value Error can happen if the data frame is of dtype=object and contains
            # numpy arrays. Numpy array comparisons do not evaluate to a single truth value
            for name, cola in a.iteritems():
                if not name in b:
                    return False

                colb = b[name]

                if not len(cola)==len(colb):
                    return False

                for idx,itema in enumerate(cola):
                    itemb = colb[idx]
                    if not nested_equal(itema,itemb):
                        return False

            return True

    if isinstance(a, Sequence):
        return all(nested_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, Mapping):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(nested_equal(a[k], b[k]) for k in a.keys())
    if isinstance(a, Set):
         return a == b

    if hasattr(a,'__dict__'):
        if not hasattr(b,'__dict__'):
            return False

        if set(a.__dict__.keys()) != set(b.__dict__.keys()):
            return False

        return all(nested_equal(a.__dict__[k], b.__dict__[k]) for k in a.__dict__.keys())

    return id(a) == id(b)