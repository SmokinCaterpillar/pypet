__author__ = 'Robert Meyer'

from pypet.utils.decorators import deprecated
from pypet.utils.comparisons import nested_equal as nested_equal_new

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


def progressbar(logger, index, total, percentage_step = 20):
    """Plots a progress bar to the given `logger` for large for loops.

    To be used inside a for-loop.

    :param logger: Logger to write to
    :param index: Current index of for-loop
    :param total: Total size of for-loop
    :param percentage_step: Steps with which the bar should be plotted

    :return: Progress bar string

    """
    point = total/100
    increment = total/(100/percentage_step)
    factor = percentage_step
    index += 1
    if (index % (factor*point) == 0):
        logger.info('[' + '=' * (index / increment) +
                     ' '  * ((total - index)/ increment) + ']' +  str(index / point) + '%')


@deprecated(msg='Please use `pypet.utils.comparisons.nested_equal` instead!')
def nested_equal(a, b):
    """
    Compare two objects recursively by element, handling numpy objects.

    Assumes hashable items are not mutable in a way that affects equality.

    DEPRECATED: Use `pypet.utils.comparisons.nested_equal` instead.
    """
    return nested_equal_new(a,b)




