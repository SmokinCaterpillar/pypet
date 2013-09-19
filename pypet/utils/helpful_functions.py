__author__ = 'Robert Meyer'


from collections import Sequence, Mapping, Set
import numpy as np
import pandas as pd
from pypet import globally



def copydoc(fromfunc, sep="\n"):
    """
    Decorator: Copy the docstring of `fromfunc`
    """
    def _decorator(func):
        sourcedoc = fromfunc.__doc__
        if func.__doc__ == None:
            func.__doc__ = sourcedoc
        else:
            func.__doc__ = sep.join([sourcedoc, func.__doc__])
        return func
    return _decorator



def flatten_dictionary(nested_dict, separator):
    flat_dict = {}
    for key, val in nested_dict.items():
        if isinstance(val,dict):
            new_flat_dict = flatten_dictionary(val, separator)
            for flat_key, val in new_flat_dict.items():
                new_key = key + separator + flat_key
                flat_dict[new_key] = val
        else:
            flat_dict[key] = val

    return flat_dict

def nest_dictionary(flat_dict, separator):
    nested_dict = {}
    for key, val in flat_dict.items():
        split_key = key.split(separator)
        act_dict = nested_dict
        final_key = split_key.pop()
        for new_key in split_key:
            if not new_key in act_dict:
                act_dict[new_key] ={}

            act_dict = act_dict[new_key]

        act_dict[final_key] = val
    return nested_dict




def nested_equal(a, b):
    """
    Compare two objects recursively by element, handling numpy objects.

    Assumes hashable items are not mutable in a way that affects equality.
    """

    # for types that implement their own custom strict equality checking

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
    if isinstance(a, globally.PARAMETER_SUPPORTED_DATA):
        return a==b
    if isinstance(a, np.ndarray):
        return np.all(a==b)
    if isinstance(a, pd.DataFrame):
        new_frame = a == b
        new_frame = new_frame |( pd.isnull(a) & pd.isnull(b))
        return np.all(new_frame)
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





