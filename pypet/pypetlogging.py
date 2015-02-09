__author__ = 'Robert Meyer'

import logging


class HasLogger(object):
    """Abstract super class that automatically adds a logger to a class.

    To add a logger to a sub-class of yours simply call ``myobj._set_logger(name)``.
    If ``name=None`` the logger name is picked as follows:

        ``self._logger = logging.getLogger(type(self).__name__)``

    The logger can be accessed via ``myobj._logger``.

    """

    def __getstate__(self):
        """Called for pickling.

        Removes the logger to allow pickling and returns a copy of `__dict__`.

        """
        statedict = self.__dict__.copy()
        if '_logger' in statedict:
            # Pickling does not work with loggers objects, so we just keep the logger's name:
            statedict['_logger'] = self._logger.name
        return statedict

    def __setstate__(self, statedict):
        """Called after loading a pickle dump.

        Restores `__dict__` from `statedict` and adds a new logger.

        """
        self.__dict__.update(statedict)
        if '_logger' in statedict:
            # If we re-instantiate the component the logger attribute only contains a name,
            # so we also need to re-create the logger:
            self._set_logger(statedict['_logger'])

    def _set_logger(self, name=None):
        """Adds a logger with a given `name`.

        If no name is given, name is constructed as
        `type(self).__name__`.

        """
        if name is None:
            name = 'pypet.%s' % type(self).__name__
        else:
            name = 'pypet.%s' % name
        self._logger = logging.getLogger(name)


class DisableLogger(object):
    """Context Manager that disables logging"""

    def __enter__(self):
        logging.disable(logging.CRITICAL)

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.disable(logging.NOTSET)


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self._logger = logger
        self._log_level = log_level
        self._linebuf = ''

    def write(self, buf):
        """Writes data from bugger to logger"""
        for line in buf.rstrip().splitlines():
            self._logger.log(self._log_level, line.rstrip())

    def flush(self):
        """No-op to fulfil API"""
        pass