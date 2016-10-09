"""Module containing factory functions for parameter exploration"""

import logging
import sys
import itertools as itools
from collections import OrderedDict


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

        >>> print cartesian_product( {'param1': [42.0, 52.5], 'param2':['a', 'b'], 'param3' : [1,2,3]}, ('param3',('param1', 'param2')))
        {param3':[1,1,2,2,3,3],'param1' : [42.0,52.5,42.0,52.5,42.0,52.5], 'param2':['a','b','a','b','a','b']}

    :returns: Dictionary with cartesian product lists.

    """
    if not combined_parameters:
        combined_parameters = list(parameter_dict)
    else:
        combined_parameters = list(combined_parameters)

    for idx, item in enumerate(combined_parameters):
        if isinstance(item, str):
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


def find_unique_points(explored_parameters):
    """Takes a list of explored parameters and finds unique parameter combinations.

    If parameter ranges are hashable operates in O(N), otherwise O(N**2).

    :param explored_parameters:

        List of **explored** parameters

    :return:

        List of tuples, first entry being the parameter values, second entry a list
        containing the run position of the unique combination.

    """
    ranges = [param.f_get_range(copy=False) for param in explored_parameters]
    zipped_tuples = list(zip(*ranges))
    try:
        unique_elements = OrderedDict()
        for idx, val_tuple in enumerate(zipped_tuples):
            if val_tuple not in unique_elements:
                unique_elements[val_tuple] = []
            unique_elements[val_tuple].append(idx)
        return list(unique_elements.items())
    except TypeError:
        logger = logging.getLogger('pypet.find_unique')
        logger.error('Your parameter entries could not be hashed, '
                     'now I am sorting slowly in O(N**2).')
        unique_elements = []
        for idx, val_tuple in enumerate(zipped_tuples):
            matches = False
            for added_tuple, pos_list in unique_elements:
                matches = True
                for idx2, val in enumerate(added_tuple):
                    if not explored_parameters[idx2]._equal_values(val_tuple[idx2], val):
                        matches = False
                        break
                if matches:
                    pos_list.append(idx)
                    break
            if not matches:
                unique_elements.append((val_tuple, [idx]))
        return unique_elements


