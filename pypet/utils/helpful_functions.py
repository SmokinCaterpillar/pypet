from __future__ import print_function
__author__ = 'Robert Meyer'

import sys
import datetime
import numpy as np
import inspect

from pypet.utils.decorators import deprecated
from pypet.utils.comparisons import nested_equal as nested_equal_new


def is_debug():
    """Checks if user is currently debugging.

    Debugging is checked via ``'pydevd' in sys.modules``.

    :return: True of False

    """
    return 'pydevd' in sys.modules


def flatten_dictionary(nested_dict, separator):
    """Flattens a nested dictionary.

    New keys are concatenations of nested keys with the `separator` in between.

    """
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
    """ Nests a given flat dictionary.

    Nested keys are created by splitting given keys around the `separator`.

    """
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
        self._total_minus_one = None

    def _reset(self, index, total, percentage_step):
        """Resets to the progressbar to start a new one"""
        self._start_time = datetime.datetime.now()
        self._current_index = index
        self._total_minus_one = total - 1
        self._total_float = float(total)
        self._total_norm =  total / 100.
        self._steps = int(100 / percentage_step)
        self._percentage_step = percentage_step
        self._current = int(int(index / self._total_norm) / percentage_step)

    def __call__(self, index, total, percentage_step=10, logger='print',
                 reprint=False, time=True, reset=False):
        """Plots a progress bar to the given `logger` for large for loops.

        To be used inside a for-loop at the end of the loop.

        :param index: Current index of for-loop
        :param total: Total size of for-loop
        :param percentage_step: Steps with which the bar should be plotted
        :param logger:

            Logger to write to, if string 'print' is given, the print statement is
            used. Use None if you don't want to print or log the progressbar statement.

        :param reprint:

            If no new line should be plotted but carriage return (works only for printing)

        :param time: If the remaining time should be calculated and displayed
        :param reset:

            If the progressbar should be restarted. If progressbar is called with a lower
            index than the one before, the progressbar is automatically restarted.

        :return:

            The progressbar string or None if the string has not been updated.

        """
        indexp1 = index + 1

        reset = reset or index <= self._current_index
        if reset:
            self._reset(index, total, percentage_step)

        next = int(int(indexp1 / self._total_norm) / self._percentage_step)
        statement = None

        if next > self._current or index == self._total_minus_one or reset:
            current_time = datetime.datetime.now()

            if time:
                time_delta = current_time - self._start_time
                remaining_seconds = int(np.round(
                            (self._total_float - indexp1)*(indexp1 + 1.0)/(indexp1 * indexp1) *
                             time_delta.total_seconds()))
                remaining_delta = datetime.timedelta(seconds=remaining_seconds)
                remaining_str = ', remaining: ' + str(remaining_delta)
            else:
                remaining_str = ''

            ending = False
            if index == self._total_minus_one:
                statement = '[' + '=' * self._steps +']100.0%'
                ending=True
            elif reset:
                statement = ('[' + '=' * min(next, self._steps) +
                             ' ' * max(self._steps - next, 0) + ']' + ' %4.1f' % (
                             (index + 1) / (0.01 * total)) + '%')
            else:
                statement = ('[' + '=' * min(next, self._steps) +
                             ' ' * max(self._steps - next, 0) + ']' + ' %4.1f' % (
                             (index + 1) / (0.01 * total)) + '%' + remaining_str)

            if logger == 'print':
                if reprint and not ending:
                    print(statement, end='\r')
                else:
                    print(statement)
            elif logger is not None:
                logger.info(statement)

        self._current = next

        return statement


_progressbar = _Progressbar()


def progressbar(index, total, percentage_step=10, logger='print',
                 reprint=True, time=True, reset=False):
    """Plots a progress bar to the given `logger` for large for loops.

    To be used inside a for-loop at the end of the loop:

    .. code-block:: python

        for irun in range(42):
            my_costly_job() # Your expensive function
            progressbar(index=irun, total=42, reprint=True) # shows a growing progressbar


    There is no initialisation of the progressbar necessary before the for-loop.
    The progressbar will be reset automatically if used in another for-loop.

    :param index: Current index of for-loop
    :param total: Total size of for-loop
    :param percentage_step: Steps with which the bar should be plotted
    :param logger:

        Logger to write to - with level INFO. If string 'print' is given, the print statement is
        used. Use ``None`` if you don't want to print or log the progressbar statement.

    :param reprint:

        If no new line should be plotted but carriage return (works only for printing)

    :param time: If the remaining time should be estimated and displayed
    :param reset:

        If the progressbar should be restarted. If progressbar is called with a lower
        index than the one before, the progressbar is automatically restarted.

    :return:

        The progressbar string or None if the string has not been updated.

    """
    return _progressbar(index=index, total=total, percentage_step=percentage_step,
                        logger=logger, reprint=reprint, time=time, reset=reset)


@deprecated(msg='Please use `pypet.utils.comparisons.nested_equal` instead!')
def nested_equal(a, b):
    """
    Compare two objects recursively by element, handling numpy objects.

    Assumes hashable items are not mutable in a way that affects equality.

    DEPRECATED: Use `pypet.utils.comparisons.nested_equal` instead.
    """
    return nested_equal_new(a, b)


def get_matching_kwargs(func, kwargs):
    """Takes a function and keyword arguments and returns the ones that can be passed."""
    if inspect.isclass(func):
        func = func.__init__
    argspec = inspect.getargspec(func)
    if argspec.keywords is not None:
        return kwargs.copy()
    else:
        matching_kwargs = dict((k, kwargs[k]) for k in argspec.args if k in kwargs)
        return matching_kwargs




