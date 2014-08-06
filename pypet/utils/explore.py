"""Module containing factory functions for parameter exploration"""

import itertools as itools

try:
    from future_builtins import zip
except ImportError:  # not 2.6+ or is 3.x
    try:
        from itertools import izip as zip  # < 2.5 or 3.x
    except ImportError:
        pass
import pypet.compat as compat


def cartesian_product(parameter_dict, combined_parameters=()):
    """ Generates a Cartesian product of the input parameter dictionary.

    For example:

    >>> print cartesian_product({'param1':[1,2,3], 'param2':[42.0, 52.5]})
    {'param1':[1,1,2,2,3,3],'param2': [42.0,52.5,42.0,52.5,42.0,52.5]}

    :param parameter_dict:

        Dictionary containing parameter names as keys and iterables of data to explore.

    :param combined_parameters:

        Tuple of tuples. Defines the order of the parameters and parameters that are
        linked together.
        If an inner tuple contains only a single item, you can spare the
        inner tuple brackets.


        For example:

        >>> print cartesian_product( {'param1': [42.0, 52.5], 'param2':['a', 'b'],\
        'param3' : [1,2,3]}, ('param3',('param1', 'param2')))
        {param3':[1,1,2,2,3,3],'param1' : [42.0,52.5,42.0,52.5,42.0,52.5],\
        'param2':['a','b','a','b','a','b']}

    :returns: Dictionary with cartesian product lists.

    """
    if not combined_parameters:
        combined_parameters = list(parameter_dict)
    else:
        combined_parameters = list(combined_parameters)

    for idx, item in enumerate(combined_parameters):
        if isinstance(item, compat.base_type):
            combined_parameters[idx] = (item,)

    iterator_list = []
    for item_tuple in combined_parameters:
        inner_iterator_list = [parameter_dict[key] for key in item_tuple]
        zipped_iterator = zip(*inner_iterator_list)
        iterator_list.append(zipped_iterator)

    result_dict = {}
    for key in parameter_dict:
        result_dict[key] = []

    cartesian_iterator = itools.product(*iterator_list)

    for cartesian_tuple in cartesian_iterator:
        for idx, item_tuple in enumerate(combined_parameters):
            for inneridx, key in enumerate(item_tuple):
                result_dict[key].append(cartesian_tuple[idx][inneridx])

    return result_dict
