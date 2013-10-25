import functools
import warnings

__author__ = 'Robert Meyer'


def deprecated(msg=''):
    '''This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.

    :param msg:

        Additional message added to the warning.

    '''
    def wrapper(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            warning_string = "Call to deprecated function or property `%s`." % func.__name__
            warning_string= warning_string + ' ' + msg
            warnings.warn_explicit(
                 warning_string,
                 category=DeprecationWarning,
                 filename=func.func_code.co_filename,
                 lineno=func.func_code.co_firstlineno + 1
             )
            return func(*args, **kwargs)
        return new_func
    return wrapper


def copydoc(fromfunc, sep="\n"):
    """
    Decorator: Copy the docstring of `fromfunc`
    """
    def _decorator(func):
        sourcedoc = fromfunc.__doc__
        if func.__doc__ == None:
            func.__doc__ = sourcedoc
        else:
            func.__doc__ = sep.join([sourcedoc, func.__doc__])
        return func
    return _decorator