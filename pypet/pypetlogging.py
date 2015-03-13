"""Module containing utilities for logging."""

__author__ = 'Robert Meyer'
try:
    import ConfigParser as cp
except ImportError:
    import configparser as cp
try:
    import StringIO
except ImportError:
    pass
import logging
import logging.config
import os
import sys
import ast
import copy
import multiprocessing as multip
import functools

import pypet.pypetconstants as pypetconstants
import pypet.compat as compat


FILENAME_INDICATORS = (
    pypetconstants.LOG_ENV,
    pypetconstants.LOG_PROC,
    pypetconstants.LOG_TRAJ,
    pypetconstants.LOG_RUN,
    '.log',
    '.txt'
)

MAIN_LOGGING_DICT = {
    'version' : 1,
    'formatters' : {
        'file': {
            'format': '%(asctime)s %(name)s %(levelname)-8s %(message)s'
        },
        'stream': {
            'format': '%(processName)-10s %(name)s %(levelname)-8s %(message)s'
        }
    },
    'handlers': {
        'stream': {
            'class': 'logging.StreamHandler',
            'formatter': 'stream'
        },
        'file_main': {
            'class': 'logging.FileHandler',
            'formatter': 'file',
            'filename': os.path.join('$TRAJ$','$ENV$','LOG.txt')
        },
        'file_error': {
            'class': 'logging.FileHandler',
            'formatter': 'file',
            'filename': os.path.join('$TRAJ$', '$ENV$', 'ERROR.txt'),
            'level': 'ERROR'
        }
    }
}


MULTIPROC_LOGGING_DICT = {
    'version' : 1,
    'formatters' : {
        'file': {
            'format': '%(asctime)s %(name)s %(levelname)-8s %(message)s'
        },
    },
    'handlers': {
        'file_main': {
            'class': 'logging.FileHandler',
            'formatter': 'file',
            'filename': os.path.join('$TRAJ$', '$ENV$', '$RUN$_$PROC$_LOG.txt')
        },
        'file_error': {
            'class': 'logging.FileHandler',
            'formatter': 'file',
            'filename': os.path.join('$TRAJ$', '$ENV$', '$RUN$_$PROC$_ERROR.txt'),
            'level': 'ERROR'
        }
    }
}


def _change_logging_kwargs(kwargs):
    log_folder = kwargs.pop('log_folder')
    logger_names = kwargs.pop('logger_names')
    log_levels = kwargs.pop('log_levels')

    if not isinstance(logger_names, (tuple, list)):
        logger_names = [logger_names]
    if not isinstance(log_levels, (tuple, list)):
        log_levels = [log_levels]

    if len(log_levels) == 1:
        log_levels = [log_levels[0] for x in logger_names]
    logger_names = [logger_name if logger_name != '' else 'root'
                    for logger_name in logger_names]

    main_dict = copy.deepcopy(MAIN_LOGGING_DICT)
    multiproc_dict = copy.deepcopy(MULTIPROC_LOGGING_DICT)

    for dictionary in (main_dict, multiproc_dict):
        has_stream = 'stream' in dictionary['handlers']
        for handler, handler_dict in dictionary['handlers'].items():
            if 'filename' in handler_dict:
                handler_dict['filename'] = os.path.join(log_folder, handler_dict['filename'])
        dictionary['loggers'] = {}
        logger_dict = dictionary['loggers']
        for idx, logger_name in enumerate(logger_names):
            logger_dict[logger_name] = {
                'level': log_levels[idx],
                'handlers': ['file_main', 'file_error']
            }
            if has_stream:
                logger_dict[logger_name]['handlers'].append('stream')

    kwargs['log_config'] = (main_dict, multiproc_dict)

def old_logging_config(func):
    @functools.wraps(func)
    def new_func(self, *args, **kwargs):

        inside = [x in kwargs for x in ('log_folder', 'logger_names', 'log_levels')]
        if any(inside):
            if not all(inside):
                raise ValueError('If you want to specify logging the old way please provide, '
                                 'all arguments: log_folder, logger_names, log_levels')
            if 'log_config' in kwargs and kwargs['log_config'] is not None:
                raise ValueError('Please set `log_config to `None` if you want to use the old '
                                 'way of providing logging configuration.')
            _change_logging_kwargs(kwargs)

        return func(self, *args, **kwargs)

    return new_func


def try_make_dirs(filename):
    try:
        dirname = os.path.dirname(filename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
    except Exception as exc:
        sys.stderr.write('ERROR during log config file handling, could not create dirs for '
                         'filename `%s` because of: %s' % (filename, str(exc)))

def rename_log_file(traj, filename):
    if pypetconstants.LOG_ENV in filename:
        env_name = traj.v_environment_name
        filename = filename.replace(pypetconstants.LOG_ENV, env_name)
    if pypetconstants.LOG_TRAJ in filename:
        traj_name = traj.v_name
        filename = filename.replace(pypetconstants.LOG_TRAJ, traj_name)
    if pypetconstants.LOG_RUN in filename:
        run_name = traj.v_crun_
        filename = filename.replace(pypetconstants.LOG_RUN, run_name)
    if pypetconstants.LOG_PROC in filename:
        proc_name = multip.current_process().name
        filename = filename.replace(pypetconstants.LOG_PROC, proc_name)
    return filename


def infer_and_make_dir_from_args(parser_filename):
    split = parser_filename.split('\'')
    if len(split) > 1:
        filename = split[1]
        try_make_dirs(filename)


def get_strings(args):
    string_list = []
    for it in ast.walk(ast.parse(args)):
        if isinstance(it, ast.Str):
            string_list.append(it.s)
    return string_list


class TrajectoryMock(object):
    def __init__(self, traj):
        self.v_environment_name = traj.v_environment_name
        self.v_name = traj.v_name
        self.v_crun_ = traj.v_crun_


class LoggingManager(object):
    def __init__(self, traj=None, log_config=None, log_stdout=False):
        self.traj = traj
        self.log_config = log_config
        self.log_stdout = log_stdout
        self._tools = []
        self._null_handler = logging.NullHandler()

    def add_null_handler(self):
        root = logging.getLogger()
        root.addHandler(self._null_handler)

    def remove_null_handler(self):
        root = logging.getLogger()
        root.removeHandler(self._null_handler)

    def tabula_rasa(self):
        for logger in logging.Logger.manager.loggerDict.values():
            if hasattr(logger, 'handlers'):
                for handler in logger.handlers:
                    if hasattr(handler, 'flush'):
                        handler.flush()
                    if hasattr(handler, 'close'):
                        handler.close()
                logger.handlers = []
        logging.Logger.manager.loggerDict={}

    @staticmethod
    def _check_and_replace_parser_args(parser, section, option, rename_func, make_dirs=True):
        args = parser.get(section, option, raw=True)
        strings = get_strings(args)
        replace = False
        for string in strings:
            isfilename = any(x in string for x in FILENAME_INDICATORS)
            if isfilename:
                newstring = rename_func(string)
                if make_dirs:
                    try_make_dirs(newstring)
                args = args.replace(string, newstring)
                replace = True
        if replace:
            parser.set(section, option, args)

    @staticmethod
    def _copy_parser(parser):
        new_parser = cp.ConfigParser()
        sections = parser.sections()
        for section in sections:
            new_parser.add_section(section)
            options = parser.options(section)
            for option in options:
                value = parser.get(section, option, raw=True)
                new_parser.set(section, option, value)
        return new_parser

    def _handle_config_parsing(self, log_config):
        if isinstance(log_config, cp.ConfigParser):
            parser = self._copy_parser(log_config)
        else:
            parser = cp.ConfigParser()
            parser.read(log_config)

        rename_func = lambda string: rename_log_file(self.traj, string)

        sections = parser.sections()
        for section in sections:
            options = parser.options(section)
            for option in options:
                if option == 'args':
                    self._check_and_replace_parser_args(parser, section, option,
                                                        rename_func=rename_func)
        return parser

    def _handle_dict_config(self, log_config):
        """Recursively walks and copies the log_config dict and searches for filenames.

        Creates parent folders of files if necessary.

        """
        new_dict = dict()
        for key in log_config.keys():
            if key == 'filename':
                filename = log_config[key]
                filename = rename_log_file(self.traj, filename)
                new_dict[key] = filename
                try_make_dirs(filename)
            elif isinstance(log_config[key], dict):
                inner_dict = self._handle_dict_config(log_config[key])
                new_dict[key] = inner_dict
            else:
                new_dict[key] = log_config[key]
        return new_dict


    def make_logging_handlers_and_tools(self):
        """Creates logging handlers and redirects stdout."""
        if self.log_config:
            if isinstance(self.log_config, dict):
                new_dict = self._handle_dict_config(self.log_config)
                logging.config.dictConfig(new_dict)
            else:
                parser = self._handle_config_parsing(self.log_config)
                if compat.python == 3:
                    logging.config.fileConfig(parser, disable_existing_loggers=False)
                else:
                    memory_file = StringIO.StringIO()
                    parser.write(memory_file)
                    memory_file.flush()
                    memory_file.seek(0)
                    logging.config.fileConfig(memory_file, disable_existing_loggers=False)

        if self.log_stdout:
            #  Create a logging mock for stdout
            std_name, std_level = self.log_stdout

            stdout = StdoutToLogger(logging.getLogger(std_name), log_level=std_level)
            stdout.start()
            self._tools.append(stdout)

    def finalize(self, remove_all_handlers=True):
        for tool in self._tools:
            tool.finalize()
        self._tools = []
        if remove_all_handlers:
            self.tabula_rasa()


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


# class RemoveEmptyFileHandler(logging.FileHandler):
#     """ Simple FileHandler that removes the log file if it is empty"""
#     def __init__(self, filename, *args, **kwargs):
#         super(RemoveEmptyFileHandler, self).__init__(filename, *args, **kwargs)
#         self.filename = os.path.abspath(filename)
#
#     def close(self):
#         """Closes the FileHandler and removes the log file if it is empty."""
#         super(RemoveEmptyFileHandler, self).close()
#         if os.path.isfile(self.filename) and os.path.getsize(self.filename) == 0:
#             os.remove(self.filename)

