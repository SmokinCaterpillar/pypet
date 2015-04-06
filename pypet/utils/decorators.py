"""Module containing decorators"""

__author__ = 'Robert Meyer'

import functools
import warnings
import logging
import time


def deprecated(msg=''):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.

    :param msg:

        Additional message added to the warning.

    """

    def wrapper(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            warning_string = "Call to deprecated function or property `%s`." % func.__name__
            warning_string = warning_string + ' ' + msg
            warnings.warn(
                warning_string,
                category=DeprecationWarning,
                # filename=compat.func_code(func).co_filename,
                # lineno=compat.func_code(func).co_firstlineno + 1
            )
            return func(*args, **kwargs)

        return new_func

    return wrapper


def copydoc(fromfunc, sep="\n"):
    """Decorator: Copy the docstring of `fromfunc`

    If the doc contains a line with the keyword `ABSTRACT`,
    like `ABSTRACT: Needs to be defined in subclass`, this line and the line after are removed.

    """

    def _decorator(func):
        sourcedoc = fromfunc.__doc__

        # Remove the ABSTRACT line:
        split_doc = sourcedoc.split('\n')
        split_doc_no_abstract = [line for line in split_doc if not 'ABSTRACT' in line]

        # If the length is different we have found an ABSTRACT line
        # Finally we want to remove the final blank line, otherwise
        # we would have three blank lines at the end
        if len(split_doc) != len(split_doc_no_abstract):
            sourcedoc = '\n'.join(split_doc_no_abstract[:-1])

        if func.__doc__ is None:
            func.__doc__ = sourcedoc
        else:
            func.__doc__ = sep.join([sourcedoc, func.__doc__])
        return func

    return _decorator


def kwargs_mutual_exclusive(param1_name, param2_name, map2to1=None):
    """ If there exist mutually exclusive parameters checks for them and maps param2 to 1."""
    def wrapper(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            if param2_name in kwargs:
                if param1_name in kwargs:
                    raise ValueError('You cannot specify `%s` and `%s` at the same time, '
                                     'they are mutually exclusive.' % (param1_name, param2_name))
                param2 = kwargs.pop(param2_name)
                if map2to1 is not None:
                    param1 = map2to1(param2)
                else:
                    param1 = param2
                kwargs[param1_name] = param1

            return func(*args, **kwargs)

        return new_func

    return wrapper


def kwargs_api_change(old_name, new_name=None):
    """This is a decorator which can be used if a kwarg has changed
    its name over versions to also support the old argument name.

    Issues a warning if the old keyword argument is detected and
    converts call to new API.

    :param old_name:

        Old name of the keyword argument

    :param new_name:

        New name of keyword argument

    """

    def wrapper(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):

            if old_name in kwargs:
                if new_name is None:
                    warning_string = 'Using deprecated keyword argument `%s` in function `%s`. ' \
                                 'This keyword is no longer supported, please don`t use it ' \
                                 'anymore.' % (old_name, func.__name__)
                else:
                    warning_string = 'Using deprecated keyword argument `%s` in function `%s`, ' \
                                 'please use keyword `%s` instead.' % \
                                 (old_name, func.__name__, new_name)
                warnings.warn(
                    warning_string,
                    category=DeprecationWarning,
                    # filename=compat.func_code(func).co_filename,
                    # lineno=compat.func_code(func).co_firstlineno + 1
                )
                value = kwargs.pop(old_name)
                if new_name is not None:
                    kwargs[new_name] = value

            return func(*args, **kwargs)

        return new_func

    return wrapper

def not_in_run(func):
    """This is a decorator that signaling that a function is not available during a single run.

    """
    doc = func.__doc__
    na_string = '''\nATTENTION: This function is not available during a single run!\n'''

    if doc is not None:
        func.__doc__ = '\n'.join([doc, na_string])
    func._not_in_run = True

    @functools.wraps(func)
    def new_func(self, *args, **kwargs):

        if self._is_run:
            raise TypeError('Function `%s` is not available during a single run.' %
                            func.__name__)

        return func(self, *args, **kwargs)

    return new_func

def with_open_store(func):
    """This is a decorator that signaling that a function is only available if the storage is open.

    """
    doc = func.__doc__
    na_string = '''\nATTENTION: This function can only be used if the store is open!\n'''

    if doc is not None:
        func.__doc__ = '\n'.join([doc, na_string])
    func._with_open_store = True

    @functools.wraps(func)
    def new_func(self, *args, **kwargs):

        if not self.traj.v_storage_service.is_open:
            raise TypeError('Function `%s` is only available if the storage is open.' %
                            func.__name__)

        return func(self, *args, **kwargs)

    return new_func


def retry(n, errors, wait=0.0, logger_name=None):
    """This is a decorator that retries a function.

    Tries `n` times and catches a given tuple of `errors`.

    If the `n` retries are not enough, the error is reraised.

    If desired `waits` some seconds.

    Optionally takes a 'logger_name' of a given logger to print the caught error.

    """

    def wrapper(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            retries = 0
            while True:
                try:
                    result = func(*args, **kwargs)
                    if retries:
                        logger.error('Retry of `%s` successful' % func.__name__)
                    return result
                except errors:
                    if retries >= n:
                        raise
                    retries += 1

                    if logger_name:
                        logger = logging.getLogger(logger_name)
                        logger.exception('I could not execute `%s`, '
                                         'starting next try. ' % func.__name__)
                    if wait:
                        time.sleep(wait)
        return new_func

    return wrapper