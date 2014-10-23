__author__ = 'Robert Meyer'

import sys
import datetime
import numpy as np
from pypet.utils.decorators import deprecated
from pypet.utils.comparisons import nested_equal as nested_equal_new



def is_debug():
    """Checks if user is currently debugging.

    Debugging is checked via ``'pydevd' in sys.modules``.

    :return: True of False

    """
    return 'pydevd' in sys.modules


def flatten_dictionary(nested_dict, separator):
    flat_dict = {}
    for key, val in nested_dict.items():
        if isinstance(val, dict):
            new_flat_dict = flatten_dictionary(val, separator)
            for flat_key, inval in new_flat_dict.items():
                new_key = key + separator + flat_key
                flat_dict[new_key] = inval
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
                act_dict[new_key] = {}

            act_dict = act_dict[new_key]

        act_dict[final_key] = val
    return nested_dict

class _Progressbar(object):
    """Implements a progress bar.

    This class is supposed to be a singleton. Do not
    import the class itself but use the `progressbar` function from this module.

    """
    def __init__(self):
        self._start_time = None
        self._current = None
        self._steps = None
        self._total_norm = None
        self._current_index = np.inf
        self._percentage_step = None
        self._total_float = None

    def _reset(self, index, total, percentage_step):
        self._start_time = datetime.datetime.now()
        self._current_index = index
        self._total_minus_one = total - 1
        self._total_float = float(total)
        self._total_norm =  total / 100.
        self._steps = int(100 / percentage_step)
        self._percentage_step = percentage_step
        self._current = int(int(index / self._total_norm) / percentage_step)

    def __call__(self, index, total, percentage_step=20, logger='print',
                 newline=True, time=True, reset=False):
        """Plots a progress bar to the given `logger` for large for loops.

        To be used inside a for-loop.

        :param index: Current index of for-loop
        :param total: Total size of for-loop
        :param percentage_step: Steps with which the bar should be plotted
        :param logger:

            Logger to write to, if string 'print' is given, the print statement is
            used. Use None if you don't want to print or log the progressbar statement.

        :param newline: If a new line should be plotted or carriage return
        :param time: If the lasting and remaining time should be calculated and displayed
        :param reset:

            If the progressbar should be restarted. If progressbar is called with a lower
            index than the one before, the progressbar is automatically restarted.

        :return:

            The progressbar string or None if the string has not been updated.

        """
        reset = reset or index <= self._current_index
        if reset:
            self._reset(index, total, percentage_step)

        next = int(int((index + 1) / self._total_norm) / self._percentage_step)
        statement = None

        if next > self._current or index == self._total_minus_one or reset:
            current_time = datetime.datetime.now()

            indexp1 = index + 1

            if time:
                time_delta = current_time - self._start_time
                remaining_seconds = int(np.round((self._total_float - indexp1)/indexp1 *
                                        time_delta.total_seconds()))
                remaining_delta = datetime.timedelta(seconds=remaining_seconds)
                time_delta = datetime.timedelta(seconds =
                                                int(np.round(time_delta.total_seconds())))

                runtime_str = ' runtime: ' + str(time_delta)
                remaining_str = ', remaining: ' + str(remaining_delta)
            else:
                runtime_str = ''
                remaining_str = ''

            if index == self._total_minus_one:
                statement = '[' + '=' * self._steps +']100.0%' + runtime_str
            elif reset:
                statement = '[' + ' ' * self._steps +']  0.0%'
            else:
                statement = ('[' + '=' * min(next, self._steps) +
                             ' ' * max(self._steps - next, 0) + ']' + ' %.1f' % (
                             (index + 1) / (0.01 * total)) + '%' + runtime_str + remaining_str)

            if not newline:
                statement = '\r' + statement

            if logger == 'print':
                print(statement)
            elif logger is not None:
                logger.info(statement)

        self._current = next

        return statement


progressbar = _Progressbar()
"""Plots a progress bar to the given `logger` for large for loops.

To be used inside a for-loop.

:param index: Current index of for-loop
:param total: Total size of for-loop
:param percentage_step: Steps with which the bar should be plotted
:param logger:

    Logger to write to, if string 'print' is given, the print statement is
    used. Use None if you don't want to print or log the progressbar statement.

:param newline: If a new line should be plotted or carriage return
:param reset:

    If the progressbar should be restarted. If progressbar is called with a lower
    index than the one before, the progressbar is automatically restarted.

:return:

    The progressbar string or None if the string has not been updated.

"""
# def progressbar(index, total, percentage_step=20, logger=None):
#     """Plots a progress bar to the given `logger` for large for loops.
#
#     To be used inside a for-loop.
#
#
#     :param index: Current index of for-loop
#     :param total: Total size of for-loop
#     :param percentage_step: Steps with which the bar should be plotted
#     :param logger: Logger to write to, if None `print` is used
#
#     :return: Progress bar string
#
#     """
#     steps = int(100 / percentage_step)
#     total_float = total / 100.
#     cur = int(int(index / total_float) / percentage_step)
#     nex = int(int((index + 1) / total_float) / percentage_step)
#
#     if nex > cur:
#         statement = ('[' + '=' * min(nex, steps) +
#                      ' ' * max(steps - nex, 0) + ']' + '%.1f' % (
#                     (index + 1) / (0.01 * total)) + '%')
#         try:
#             logger.info(statement)
#         except AttributeError:
#             print(statement)


@deprecated(msg='Please use `pypet.utils.comparisons.nested_equal` instead!')
def nested_equal(a, b):
    """
    Compare two objects recursively by element, handling numpy objects.

    Assumes hashable items are not mutable in a way that affects equality.

    DEPRECATED: Use `pypet.utils.comparisons.nested_equal` instead.
    """
    return nested_equal_new(a, b)




