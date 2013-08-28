__author__ = 'robert'


from collections import Sequence, Mapping, Set
import numpy as np

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
    #
    # # for types that implement their own custom strict equality checking
    # __seq__ = getattr(a, "__seq__", None)
    # if  __seq__!=None and callable(__seq__):
    #     return a.__seq__(b)
    try:
        custom_eq= a == b
        if isinstance(custom_eq,bool):
            return custom_eq
    except:
        pass

    # Use __class__ instead of type() to be compatible with instances of
    # old-style classes.
    if a.__class__ != b.__class__:
        return False



    # # Check equality according to type type [sic].
    # if isinstance(a, basestring):
    #     return a == b
    if isinstance(a, np.ndarray):
        return np.all(custom_eq)
    if isinstance(a, Sequence):
        return all(nested_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, Mapping):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(nested_equal(a[k], b[k]) for k in a.keys())
    # if isinstance(a, Set):
    #     return a == b

    if set(a.__dict__.keys() != set(b.__dict__.keys())):
        return False

    return all(nested_equal(a.__dict__[k], b.__dict__[k]) for k in a.__dict__keys())



