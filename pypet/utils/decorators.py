"""Module containing decorators"""

__author__ = 'Robert Meyer'

import functools
import warnings


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

        if not self._traj.v_storage_service.is_open:
            raise RuntimeError('Function `%s` is only available if the storage is open.' %
                            func.__name__)

        return func(self, *args, **kwargs)

    return new_func