"""Module containing utilities for logging."""

__author__ = 'Robert Meyer'

import logging
import os
import sys
import multiprocessing as multip

import pypet.pypetconstants as pypetconstants


def reset_log_options(log_options):
    """Removes all queue holders to replace them by the original option."""
    for idx, log_opt in enumerate(log_options):
        if isinstance(log_opt, LogQueueHolder):
            log_options[idx] = log_opt.option


def set_log_levels(logger_names, log_levels):
    """Sets a given list of levels to a list of loggers"""
    loggers = [logging.getLogger(logger_name) for logger_name in logger_names]
    for idx, logger in enumerate(loggers):
        log_level = log_levels[idx] if len(log_levels) > 1 else log_levels[0]
        logger.setLevel(log_level)


def add_handlers(logger_names, handlers_and_tools):
    """Adds handlers to the given loggers"""
    loggers = [logging.getLogger(logger_name) for logger_name in logger_names]
    for logger in loggers:
        for handler in handlers_and_tools[0]:
            logger.addHandler(handler)


def close_handlers_and_tools(handlers_and_tools):
    """Closes all (file) handlers"""
    for handler in handlers_and_tools[0]:
        if hasattr(handler, 'close'):
            handler.close()
    for tool in handlers_and_tools[1]:
        if hasattr(tool, 'finalize'):
            tool.finalize()


def remove_handlers(logger_names, handlers_and_tools):
    """Removes all handlers from the given list of logger names"""
    loggers = [logging.getLogger(logger_name) for logger_name in logger_names]
    for logger in loggers:
        for handler in handlers_and_tools[0]:
            logger.removeHandler(handler)


def make_logging_handlers_and_tools(log_path,
                           logger_names,
                           log_levels,
                           log_stdout,
                           log_options,
                           filename='main.txt',
                           called_from_main=False):
        """Creates logging handlers and redirects stdout.

        Moreover, returns the handlers.

        :param log_path: Path to logging folder
        :param logger_names: List/Tuple of logger names
        :param log_levels: The associated log levels
        :param log_stdout: If stdout should be logged
        :param log_options: Options for the logging handlers
        :param filename: Filename *without* path, e.g. ``'main.txt'``

        :return:

            Pair of handlers and tools.

        """
        handlers = []  # List of created handlers and managment devices
        tools = []
        queue_manager = None  # Queue manager if defined, so we have just 1
        added_queue = False

        if log_levels:
            # Set the log level to the specified one
            set_log_levels(logger_names, log_levels)

        for idx, log_opt in enumerate(log_options):

            understood_option = True
            if log_opt == pypetconstants.LOG_MODE_NULL:
                handlers.append(logging.NullHandler())

            elif log_opt == pypetconstants.LOG_MODE_FILE:
                full_filename = os.path.join(log_path, filename)
                file_handlers = create_main_and_error_file_handler(full_filename)
                handlers.extend(file_handlers)

            elif log_opt == pypetconstants.LOG_MODE_STREAM:
                handlers.append(create_stream_handler())

            elif log_opt == pypetconstants.LOG_MODE_MAIN_STREAM:
                if called_from_main:
                    handlers.append(create_stream_handler())
                else:
                    handlers.append(logging.NullHandler())

            elif (log_opt == pypetconstants.LOG_MODE_QUEUE or
                            log_opt == pypetconstants.LOG_MODE_QUEUE_STREAM):
                if queue_manager is None:
                    queue_manager = LogQueueManager('LogQueueManager')
                    tools.append(queue_manager)
                    queue_manager.start()

                queue_holder = queue_manager.get_queue_holder(log_opt)

                if log_opt == pypetconstants.LOG_MODE_QUEUE:
                    full_filename = os.path.join(log_path, 'main_queue.txt')
                    handler_maker = FileHandlerMaker(full_filename)
                elif log_opt == pypetconstants.LOG_MODE_QUEUE_STREAM:
                    handler_maker = StreamHandlerMaker()
                else:
                    raise RuntimeError('You shall not pass!')
                queue_holder.queue.put(('HANDLERS', handler_maker))

                log_opt = queue_holder
                log_options[idx] = log_opt

            else:
                understood_option = False

            if isinstance(log_opt, LogQueueHolder):
                if not added_queue:
                    queue_handler = LogQueueSender(log_opt.queue)
                    handlers.append(queue_handler)
                    added_queue = True
                understood_option = True

            if not understood_option:
                raise ValueError('Logging option `%s` not understood.' % str(log_opt))

        add_handlers(logger_names, handlers_and_tools=(handlers, tools))

        if log_stdout:
            #  Create a logging mock for stdout
            std_name, std_level = log_stdout

            stdout = StdoutToLogger(logging.getLogger(std_name), log_level=std_level)
            stdout.start()
            tools.append(stdout)

        return handlers, tools


def make_premature_handler(logger_names, log_levels, log_options):
    """Creates a stream logger before the actual logging options are applied"""
    if (pypetconstants.LOG_MODE_QUEUE_STREAM in log_options or
                pypetconstants.LOG_MODE_STREAM in log_options):
        premature_handler = create_stream_handler()
        set_log_levels(logger_names, log_levels)
        result = ([premature_handler], [])
        add_handlers(logger_names, result)
        return result
    else:
        return [], []


def create_stream_handler(stream=None):
    """Creates a StreamHandler with appropriate format."""
    stream_handler = logging.StreamHandler(stream)
    stream_format = '%(processName)-10s %(name)s %(levelname)-8s %(message)s'
    stream_formatter = logging.Formatter(stream_format)
    stream_handler.setFormatter(stream_formatter)
    return stream_handler


def create_main_and_error_file_handler(filename):
    """Creates two file handlers, main and error, with apporpriate format"""
    pypet_root_logger = logging.getLogger('pypet')

    main_log_handler, error_log_handler = None, None

    # Make the log folder
    log_path = os.path.dirname(filename)
    if not os.path.isdir(log_path):
        os.makedirs(log_path)

    filename, ext = os.path.splitext(filename)


    file_format = '%(asctime)s %(name)s %(levelname)-8s %(message)s'
    formatter = logging.Formatter(file_format)
    handlers = []

    # Add a handler for storing everything to a text file
    main_file_name = filename + '_log' + ext
    try:
        # Handler creation might fail under Windows sometimes
        main_log_handler = logging.FileHandler(main_file_name)
        pypet_root_logger.debug('Created logging file: `%s`' % main_file_name)
        main_log_handler.setFormatter(formatter)
        handlers.append(main_log_handler)
    except IOError as exc:
        pypet_root_logger.error('Could not create file `%s`. '
                   'I will NOT store log messages to disk. Original Error: `%s`' %
                                (main_file_name, str(exc)))

    # Add a handler for storing warnings and errors to a text file
    error_file_name = filename + '_errors' + ext
    try:
        # Handler creation might fail under Windows sometimes
        error_log_handler = RemoveEmptyFileHandler(error_file_name)
        pypet_root_logger.debug('Created error logging file that will be removed if empty: '
                                '`%s`' % error_file_name)
        error_log_handler.setLevel(logging.ERROR)
        error_log_handler.setFormatter(formatter)
        handlers.append(error_log_handler)
    except IOError as exc:
        pypet_root_logger.error('Could not create file `%s`. '
                   'I will NOT store log messages to disk. Original Error: `%s`' %
                                (error_file_name, str(exc)))

    return handlers


def queue_handling(queue_writer):
    """Starts the logging queue writer."""
    queue_writer.run()


class StreamHandlerMaker(object):
    """Messenger object that can be passed to the queue writer to create the stream handler"""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def make_handlers(self):
        return [create_stream_handler(*self.args, **self.kwargs)]


class FileHandlerMaker(StreamHandlerMaker):
    """Messenger object that can be passed to the queue writer to create the file handlers"""
    def make_handlers(self):
        return create_main_and_error_file_handler(*self.args, **self.kwargs)


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


class StdoutToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self._logger = logger
        self._log_level = log_level
        self._linebuf = ''
        self._recursion = False
        self._redirection = False
        self._original_steam = None

    def start(self):
        if sys.stdout is not self:
            self._original_steam = sys.stdout
            sys.stdout = self
            self._redirection = True
        if self._redirection:
            print('Established redirection of `stdout`.')

    def write(self, buf):
        """Writes data from bugger to logger"""
        if not self._recursion:
            self._recursion = True
            try:
                for line in buf.rstrip().splitlines():
                    self._logger.log(self._log_level, line.rstrip())
            finally:
                self._recursion = False
        else:
            # If stderr is redirected to stdout we can avoid further recursion by
            sys.__stderr__.write('ERROR: Recursion in Stream redirection!')

    def flush(self):
        """No-op to fulfil API"""
        pass

    def finalize(self):
        if self._redirection:
            sys.stdout = self._original_steam
            print('Disabled redirection of `stdout`.')
        self._redirection = False
        self._original_steam = None


class RemoveEmptyFileHandler(logging.FileHandler):
    """ Simple FileHandler that removes the log file if it is empty"""
    def __init__(self, filename, *args, **kwargs):
        super(RemoveEmptyFileHandler, self).__init__(filename, *args, **kwargs)
        self.filename = os.path.abspath(filename)

    def close(self):
        """Closes the FileHandler and removes the log file if it is empty."""
        super(RemoveEmptyFileHandler, self).close()
        if os.path.isfile(self.filename) and os.path.getsize(self.filename) == 0:
            os.remove(self.filename)


class LogQueueHolder(object):
    """Placeholder object that passes a logging queue around"""
    def __init__(self, manager_name, option, queue):
        self.manager_name = manager_name
        self.queue = queue
        self.option = option


class LogQueueManager(object):
    """Manager to start a logging queue."""
    def __init__(self, name):
        self.name = name
        self.manager = None
        self.queue = None
        self.queue_writer = None
        self.queue_process = None

    def start(self):
        self.manager = multip.Manager()
        self.queue = self.manager.Queue()
        self.queue_writer = LogQueueWriter(self.queue)
        self.queue_process = multip.Process(name='QueueStreamProcess',
                                            target=queue_handling,
                                            args=(self.queue_writer,))
        self.queue_process.start()

    def get_queue_holder(self, option):
        return LogQueueHolder(self.name, option, self.queue)

    def finalize(self):
        self.queue.put(('DONE', None))
        self.queue_process.join()
        self.manager.shutdown()

        self.manager = None
        self.queue = None
        self.queue_writer = None
        self.queue_process = None


class LogQueueWriter(object):
    def __init__(self, queue):
        self.queue = queue
        self.handlers = []

    def run(self):
        try:
            while True:
                try:
                    msg, item = self.queue.get()
                    if msg == 'DONE':
                        break
                    elif msg == 'RECORD':
                        for handler in self.handlers:
                            if item.levelno >= handler.level:
                                handler.handle(item)
                    elif msg == 'HANDLERS':
                        self.handlers.extend(item.make_handlers())
                    else:
                        raise RuntimeError('Wrong message `%s` to log queue writer.' % msg)
                except Exception as exc:
                    sys.stderr.write('ERROR in logging queue: `%s`' % str(exc))
        finally:
            close_handlers_and_tools((self.handlers, ()))
            self.handlers = []


class LogQueueSender(logging.Handler):
    """ Sends logging message over a queue."""

    def __init__(self, queue):
        """
        Initialise an instance, using the passed queue.
        """
        logging.Handler.__init__(self)
        self.queue = queue

    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue.
        """
        try:
            exc_info = record.exc_info
            if exc_info:
                record.exc_info = None
            self.queue.put_nowait(('RECORD', record))
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class WithoutHandlersForkContext():
    def __init__(self, logger_names, handlers_and_tools):
        self.logger_names = logger_names
        self.handlers_and_tools = handlers_and_tools

    def __enter__(self):
        if hasattr(os, 'fork'):
            remove_handlers(self.logger_names, self.handlers_and_tools)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(os, 'fork'):
            add_handlers(self.logger_names, self.handlers_and_tools)

