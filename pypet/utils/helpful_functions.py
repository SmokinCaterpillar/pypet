__author__ = 'Robert Meyer'

import sys
import os
import datetime
import numpy as np
import inspect
import logging
import socket
try:
    import zmq
except ImportError:
    zmq = None


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
        self._start_time = None   # Time of start/reset
        self._start_index = None  # Index of start/reset
        self._current_index = np.inf  # Current index
        self._percentage_step = None  # Percentage step for bar update
        self._total = None  # Total steps of the bas (float) not to be mistaken for length
        self._total_minus_one = None  # (int) the above minus 1
        self._length = None  # Length of the percentage bar in `=` signs
        self._norm_factor = None  # Normalization factor
        self._current_interval = None  # The current interval,
        # to check if bar needs to be updated

    def _reset(self, index, total, percentage_step, length):
        """Resets to the progressbar to start a new one"""
        self._start_time = datetime.datetime.now()
        self._start_index = index
        self._current_index = index
        self._percentage_step = percentage_step
        self._total = float(total)
        self._total_minus_one = total - 1
        self._length = length
        self._norm_factor = total * percentage_step / 100.0
        self._current_interval = int((index + 1.0) / self._norm_factor)

    def _get_remaining(self, index):
        """Calculates remaining time as a string"""
        try:
            current_time = datetime.datetime.now()
            time_delta = current_time - self._start_time
            try:
                total_seconds = time_delta.total_seconds()
            except AttributeError:
                # for backwards-compatibility
                # Python 2.6 does not support `total_seconds`
                total_seconds = ((time_delta.microseconds +
                                    (time_delta.seconds +
                                     time_delta.days * 24 * 3600) * 10 ** 6) / 10.0 ** 6)
            remaining_seconds = int((self._total - self._start_index - 1.0) *
                                    total_seconds / float(index - self._start_index) -
                                    total_seconds)
            remaining_delta = datetime.timedelta(seconds=remaining_seconds)
            remaining_str = ', remaining: ' + str(remaining_delta)
        except ZeroDivisionError:
            remaining_str = ''
        return remaining_str

    def __call__(self, index, total, percentage_step=5, logger='print', log_level=logging.INFO,
                 reprint=False, time=True, length=20, fmt_string=None,  reset=False):
        """Plots a progress bar to the given `logger` for large for loops.

        To be used inside a for-loop at the end of the loop.

        :param index: Current index of for-loop
        :param total: Total size of for-loop
        :param percentage_step: Percentage step with which the bar should be updated
        :param logger:

            Logger to write to, if string 'print' is given, the print statement is
            used. Use None if you don't want to print or log the progressbar statement.

        :param log_level: Log level with which to log.
        :param reprint:

            If no new line should be plotted but carriage return (works only for printing)

        :param time: If the remaining time should be calculated and displayed
        :param length: Length of the bar in `=` signs.
        :param fmt_string:

            A string which contains exactly one `%s` in order to incorporate the progressbar.
            If such a string is given, ``fmt_string % progressbar`` is printed/logged.

        :param reset:

            If the progressbar should be restarted. If progressbar is called with a lower
            index than the one before, the progressbar is automatically restarted.

        :return:

            The progressbar string or None if the string has not been updated.


        """
        reset = (reset or
                 index <= self._current_index or
                 total != self._total)
        if reset:
            self._reset(index, total, percentage_step, length)

        statement = None
        indexp1 = index + 1.0
        next_interval = int(indexp1 / self._norm_factor)
        ending = index >= self._total_minus_one

        if next_interval > self._current_interval or ending or reset:
            if time:
                remaining_str = self._get_remaining(index)
            else:
                remaining_str = ''

            if ending:
                statement = '[' + '=' * self._length +']100.0%'
            else:
                bars = int((indexp1 / self._total) * self._length)
                spaces = self._length - bars
                percentage = indexp1 / self._total * 100.0
                if reset:
                    statement = ('[' + '=' * bars +
                                 ' ' * spaces + ']' + ' %4.1f' % percentage + '%')
                else:
                    statement = ('[' + '=' * bars +
                                 ' ' * spaces + ']' + ' %4.1f' % percentage + '%' +
                                 remaining_str)

            if fmt_string:
                statement = fmt_string % statement
            if logger == 'print':
                if reprint:
                    print('\r' + statement, end='', flush=True)
                else:
                    print(statement)
            elif logger is not None:
                if isinstance(logger, str):
                    logger = logging.getLogger(logger)
                logger.log(msg=statement, level=log_level)

        self._current_interval = next_interval
        self._current_index = index

        return statement


_progressbar = _Progressbar()


def progressbar(index, total, percentage_step=10, logger='print', log_level=logging.INFO,
                 reprint=True, time=True, length=20, fmt_string=None, reset=False):
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

    :param log_level: Log level with which to log.
    :param reprint:

        If no new line should be plotted but carriage return (works only for printing)

    :param time: If the remaining time should be estimated and displayed
    :param length: Length of the bar in `=` signs.
    :param fmt_string:

        A string which contains exactly one `%s` in order to incorporate the progressbar.
        If such a string is given, ``fmt_string % progressbar`` is printed/logged.

    :param reset:

        If the progressbar should be restarted. If progressbar is called with a lower
        index than the one before, the progressbar is automatically restarted.

    :return:

        The progressbar string or `None` if the string has not been updated.

    """
    return _progressbar(index=index, total=total, percentage_step=percentage_step,
                        logger=logger, log_level=log_level, reprint=reprint,
                        time=time, length=length, fmt_string=fmt_string, reset=reset)


def _get_argspec(func):
    """Helper function to support both Python versions"""
    if inspect.isclass(func):
        func = func.__init__
    if not inspect.isfunction(func):
        # Init function not existing
        return [], False
    parameters = inspect.signature(func).parameters
    args = []
    uses_starstar = False
    for par in parameters.values():
        if (par.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD or
                    par.kind == inspect.Parameter.KEYWORD_ONLY):
            args.append(par.name)
        elif par.kind == inspect.Parameter.VAR_KEYWORD:
            uses_starstar = True
    return args, uses_starstar


def get_matching_kwargs(func, kwargs):
    """Takes a function and keyword arguments and returns the ones that can be passed."""
    args, uses_startstar = _get_argspec(func)
    if uses_startstar:
        return kwargs.copy()
    else:
        matching_kwargs = dict((k, kwargs[k]) for k in args if k in kwargs)
        return matching_kwargs


def result_sort(result_list, start_index=0):
    """Sorts a list of results in O(n) in place (since every run is unique)

    :param result_list: List of tuples [(run_idx, res), ...]
    :param start_index: Index with which to start, every entry before `start_index` is ignored

    """
    if len(result_list) < 2:
        return result_list
    to_sort = result_list[start_index:]
    minmax = [x[0] for x in to_sort]
    minimum = min(minmax)
    maximum = max(minmax)
    #print minimum, maximum
    sorted_list = [None for _ in range(minimum, maximum + 1)]
    for elem in to_sort:
        key = elem[0] - minimum
        sorted_list[key] = elem
    idx_count = start_index
    for elem in sorted_list:
        if elem is not None:
            result_list[idx_count] = elem
            idx_count += 1
    return result_list


def format_time(timestamp):
    """Formats timestamp to human readable format"""
    format_string = '%Y_%m_%d_%Hh%Mm%Ss'
    formatted_time = datetime.datetime.fromtimestamp(timestamp).strftime(format_string)
    return formatted_time


def convert_ipv6(host):
    if ':' in host:
        #IP 6 address
        host = host.split('%')[0]
        host = '[%s]' % host

    return  host


def is_ipv6(url):
    return '[' in url


def port_to_tcp(port=None):
    """Returns local tcp address for a given `port`, automatic port if `None`"""
    #address = 'tcp://' + socket.gethostbyname(socket.getfqdn())
    domain_name = socket.getfqdn()
    try:
        addr_list = socket.getaddrinfo(domain_name, None)
    except Exception:
        addr_list = socket.getaddrinfo('127.0.0.1', None)
    family, socktype, proto, canonname, sockaddr = addr_list[0]
    host = convert_ipv6(sockaddr[0])
    address =  'tcp://' + host
    if port is None:
        port = ()
    if not isinstance(port, int):
        # determine port automatically
        context = zmq.Context()
        try:
            socket_ = context.socket(zmq.REP)
            socket_.ipv6 = is_ipv6(address)
            port = socket_.bind_to_random_port(address, *port)
        except Exception:
            print('Could not connect to {} using {}'.format(address, addr_list))
            pypet_root_logger = logging.getLogger('pypet')
            pypet_root_logger.exception('Could not connect to {}'.format(address))
            raise
        socket_.close()
        context.term()
    return address + ':' + str(port)


def racedirs(path):
    """Like os.makedirs but takes care about race conditions"""
    if os.path.isfile(path):
        raise IOError('Path `%s` is already a file not a directory')
    while True:
        try:
            if os.path.isdir(path):
                # only break if full path has been created or exists
                break
            os.makedirs(path)
        except EnvironmentError as exc:
            # Part of the directory path already exist
            if exc.errno != 17:
                # This error won't be any good
                raise

