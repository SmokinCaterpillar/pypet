"""Module containing utility functions to compare parameters and results"""

__author__ = 'Robert Meyer'

from collections import Sequence, Mapping

import numpy as np
import pandas as pd
import scipy.sparse as spsp

import pypet.slots as slots


def results_equal(a, b):
    """Compares two result instances

    Checks full name and all data. Does not consider the comment.

    :return: True or False

    :raises: ValueError if both inputs are no result instances

    """
    if a.v_is_parameter and b.v_is_parameter:
        raise ValueError('Both inputs are not results.')

    if a.v_is_parameter or b.v_is_parameter:
        return False

    if a.v_full_name != b.v_full_name:
        return False

    if hasattr(a, '_data') and not hasattr(b, '_data'):
        return False

    if hasattr(a, '_data'):
        akeyset = set(a._data.keys())
        bkeyset = set(b._data.keys())

        if akeyset != bkeyset:
            return False

        for key in a._data:
            val = a._data[key]
            bval = b._data[key]

            if not nested_equal(val, bval):
                return False

    return True


def parameters_equal(a, b):
    """Compares two parameter instances

    Checks full name, data, and ranges. Does not consider the comment.

    :return: True or False

    :raises: ValueError if both inputs are no parameter instances

    """
    if (not b.v_is_parameter and
            not a.v_is_parameter):
        raise ValueError('Both inputs are not parameters')

    if (not b.v_is_parameter or
            not a.v_is_parameter):
        return False

    if a.v_full_name != b.v_full_name:
        return False

    if a.f_is_empty() and b.f_is_empty():
        return True

    if a.f_is_empty() != b.f_is_empty():
        return False

    if not a._values_of_same_type(a.f_get(), b.f_get()):
        return False

    if not a._equal_values(a.f_get(), b.f_get()):
        return False

    if a.f_has_range() != b.f_has_range():
        return False

    if a.f_has_range():
        if a.f_get_range_length() != b.f_get_range_length():
            return False

        for myitem, bitem in zip(a.f_get_range(copy=False), b.f_get_range(copy=False)):
            if not a._values_of_same_type(myitem, bitem):
                return False
            if not a._equal_values(myitem, bitem):
                return False

    return True


def get_all_attributes(instance):
    """Returns an attribute value dictionary much like `__dict__` but incorporates `__slots__`"""
    try:
        result_dict = instance.__dict__.copy()
    except AttributeError:
        result_dict = {}

    if hasattr(instance, '__all_slots__'):
        all_slots = instance.__all_slots__
    else:
        all_slots = slots.get_all_slots(instance.__class__)

    for slot in all_slots:
        result_dict[slot] = getattr(instance, slot)

    result_dict.pop('__dict__', None)
    result_dict.pop('__weakref__', None)

    return result_dict


def nested_equal(a, b):
    """Compares two objects recursively by their elements.

    Also handles numpy arrays, pandas data and sparse matrices.

    First checks if the data falls into the above categories.
    If not, it is checked if a or b are some type of sequence or mapping and
    the contained elements are compared.
    If this is not the case, it is checked if a or b do provide a custom `__eq__` that
    evaluates to a single boolean value.
    If this is not the case, the attributes of a and b are compared.
    If this does not help either, normal `==` is used.

    Assumes hashable items are not mutable in a way that affects equality.
    Based on the suggestion from HERE_, thanks again Lauritz V. Thaulow :-)

    .. _HERE: http://stackoverflow.com/questions/18376935/best-practice-for-equality-in-python

    """
    if a is b:
        return True

    if a is None or b is None:
        return False

    a_sparse = spsp.isspmatrix(a)
    b_sparse = spsp.isspmatrix(b)
    if a_sparse != b_sparse:
        return False
    if a_sparse:
        if a.nnz == 0:
            return b.nnz == 0
        else:
            return not np.any((a != b).data)

    a_series = isinstance(a, pd.Series)
    b_series = isinstance(b, pd.Series)
    if a_series != b_series:
        return False
    if a_series:
        try:
            eq = (a == b).all()
            return eq
        except (TypeError, ValueError):
            # If Sequence itself contains numpy arrays we get here
            if not len(a) == len(b):
                return False
            for idx, itema in enumerate(a):
                itemb = b[idx]
                if not nested_equal(itema, itemb):
                    return False
            return True

    a_frame = isinstance(a, pd.DataFrame)
    b_frame = isinstance(b, pd.DataFrame)
    if a_frame != b_frame:
        return False
    if a_frame:
        try:
            if a.empty and b.empty:
                return True
            new_frame = a == b
            new_frame = new_frame | (pd.isnull(a) & pd.isnull(b))
            if isinstance(new_frame, pd.DataFrame):
                return np.all(new_frame.values)
        except (ValueError, TypeError):
            # The Value Error can happen if the data frame is of dtype=object and contains
            # numpy arrays. Numpy array comparisons do not evaluate to a single truth value
            for name in a:
                cola = a[name]
                if not name in b:
                    return False
                colb = b[name]
                if not len(cola) == len(colb):
                    return False
                for idx, itema in enumerate(cola):
                    itemb = colb[idx]
                    if not nested_equal(itema, itemb):
                        return False
            return True

    a_array = isinstance(a, np.ndarray)
    b_array = isinstance(b, np.ndarray)
    if a_array != b_array:
        return False
    if a_array:
        if a.shape != b.shape:
            return False
        return np.all(a == b)

    a_list = isinstance(a, (Sequence, list, tuple))
    b_list = isinstance(b, (Sequence, list, tuple))
    if a_list != b_list:
        return False
    if a_list:
        return all(nested_equal(x, y) for x, y in zip(a, b))

    a_mapping = isinstance(a, (Mapping, dict))
    b_mapping = isinstance(b, (Mapping, dict))
    if a_mapping != b_mapping:
        return False
    if a_mapping:
        keys_a = a.keys()
        if set(keys_a) != set(b.keys()):
            return False
        return all(nested_equal(a[k], b[k]) for k in keys_a)

    # Equality for general objects
    # for types that support __eq__ or __cmp__
    equality = NotImplemented
    try:
        equality = a.__eq__(b)
    except (AttributeError, NotImplementedError, TypeError, ValueError):
        pass
    if equality is NotImplemented:
        try:
            equality = b.__eq__(a)
        except (AttributeError, NotImplementedError, TypeError, ValueError):
            pass
    if equality is NotImplemented:
        try:
            cmp = a.__cmp__(b)
            if cmp is not NotImplemented:
                equality = cmp == 0
        except (AttributeError, NotImplementedError, TypeError, ValueError):
            pass
    if equality is NotImplemented:
        try:
            cmp = b.__cmp__(a)
            if cmp is not NotImplemented:
                equality = cmp == 0
        except (AttributeError, NotImplementedError, TypeError, ValueError):
            pass
    if equality is not NotImplemented:
        try:
            return bool(equality)
        except (AttributeError, NotImplementedError, TypeError, ValueError):
            pass

    # Compare objects based on their attributes
    attributes_a = get_all_attributes(a)
    attributes_b = get_all_attributes(b)
    if len(attributes_a) != len(attributes_b):
        return False
    if len(attributes_a) > 0:
        keys_a = list(attributes_a.keys())
        if set(keys_a) != set(attributes_b.keys()):
            return False

        return all(nested_equal(attributes_a[k], attributes_b[k]) for k in keys_a)

    # Ok they are really not equal
    return False
