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

        if func.__doc__ == None:
            func.__doc__ = sourcedoc
        else:
            func.__doc__ = sep.join([sourcedoc, func.__doc__])
        return func
    return _decorator