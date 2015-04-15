"""Module containing utilities for logging."""

__author__ = 'Robert Meyer'

try:
    import ConfigParser as cp
except ImportError:
    import configparser as cp
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import logging
from logging.config import fileConfig
try:
    from logging.config import dictConfig
except ImportError:
    from logutils.dictconfig import dictConfig
try:
    from logging import NullHandler
except ImportError:
    from logutils import NullHandler
import os
import math
import sys
import ast
import copy
import multiprocessing as multip
import functools

import pypet.pypetconstants as pypetconstants
import pypet.compat as compat
from pypet.utils.helpful_functions import progressbar
from pypet.slots import HasSlots


FILENAME_INDICATORS = set([pypetconstants.LOG_ENV,
                           pypetconstants.LOG_PROC,
                           pypetconstants.LOG_TRAJ,
                           pypetconstants.LOG_RUN,
                           '.log',
                           '.txt'])
"""Set of strings that mark a log file"""

LOGGING_DICT = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
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
            'filename': os.path.join(pypetconstants.LOG_TRAJ,
                                     pypetconstants.LOG_ENV,
                                     'LOG.txt')
        },
        'file_error': {
            'class': 'logging.FileHandler',
            'formatter': 'file',
            'filename': os.path.join(pypetconstants.LOG_TRAJ,
                                     pypetconstants.LOG_ENV,
                                     'ERROR.txt'),
            'level': 'ERROR'
        }
    },
    'multiproc_formatters': {
        'file': {
            'format': '%(asctime)s %(name)s %(levelname)-8s %(message)s'
        },
    },
    'multiproc_handlers': {
        'file_main': {
            'class': 'logging.FileHandler',
            'formatter': 'file',
            'filename': os.path.join(pypetconstants.LOG_TRAJ,
                                     pypetconstants.LOG_ENV,
                                     '%s_%s_LOG.txt' % (pypetconstants.LOG_RUN,
                                                        pypetconstants.LOG_PROC))
        },
        'file_error': {
            'class': 'logging.FileHandler',
            'formatter': 'file',
            'filename': os.path.join(pypetconstants.LOG_TRAJ,
                                     pypetconstants.LOG_ENV,
                                     '%s_%s_ERROR.txt' % (pypetconstants.LOG_RUN,
                                                          pypetconstants.LOG_PROC)),
            'level': 'ERROR'
        }
    }
}
"""Dictionary containing the default configuration."""


def _change_logging_kwargs(kwargs):
    """ Helper function to turn the simple logging kwargs into a `log_config`."""
    log_folder = kwargs.pop('log_folder', 'logs')
    logger_names = kwargs.pop('logger_names', '')
    log_levels = kwargs.pop('log_levels', logging.INFO)

    if not isinstance(logger_names, (tuple, list)):
        logger_names = [logger_names]
    if not isinstance(log_levels, (tuple, list)):
        log_levels = [log_levels]
    if len(log_levels) == 1:
        log_levels = [log_levels[0] for _ in logger_names]

    # We don't want to manipulate the original dictionary
    dictionary = copy.deepcopy(LOGGING_DICT)

    # Add all handlers to all loggers
    for prefix in ('', 'multiproc_'):
        for handler_dict in dictionary[prefix + 'handlers'].values():
            if 'filename' in handler_dict:
                handler_dict['filename'] = os.path.join(log_folder, handler_dict['filename'])
        dictionary[prefix + 'loggers'] = {}
        logger_dict = dictionary[prefix + 'loggers']
        for idx, logger_name in enumerate(logger_names):
            logger_dict[logger_name] = {
                'level': log_levels[idx],
                'handlers': list(dictionary[prefix + 'handlers'].keys())
            }

    kwargs['log_config'] = dictionary


def simple_logging_config(func):
    """Decorator to allow a simple logging configuration.

    This encompasses giving a `log_folder`, `logger_names` as well as `log_levels`.

    """

    @functools.wraps(func)
    def new_func(self, *args, **kwargs):

        inside = [x in kwargs for x in ('log_folder', 'logger_names', 'log_levels')]
        if any(inside):
            if 'log_config' in kwargs and kwargs['log_config'] is not None:
                raise ValueError('Please set `log_config to `None` if you want to use the simple '
                                 'way of providing logging configuration.')
            _change_logging_kwargs(kwargs)

        return func(self, *args, **kwargs)

    return new_func


def try_make_dirs(filename):
    """ Tries to make directories for a given `filename`.

    Ignores any error but notifies via stderr.

    """
    try:
        dirname = os.path.dirname(filename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
    except Exception as exc:
        sys.stderr.write('ERROR during log config file handling, could not create dirs for '
                         'filename `%s` because of: %s' % (filename, repr(exc)))


def rename_log_file(traj, filename, process_name=None):
    """ Renames a given `filename` with valid wildcard placements.

    :const:`~pypet.pypetconstants.LOG_ENV` ($env) is replaces by the name of the
    trajectory`s environment.

    :const:`~pypet.pypetconstants.LOG_TRAJ` ($traj) is replaced by the name of the
    trajectory.

    :const:`~pypet.pypetconstants.LOG_RUN` ($run) is replaced by the name of the current
    run. If the trajectory is not set to a run 'run_ALL' is used.

    :const:`~pypet.pypetconstants.LOG_SET` ($set) is replaced by the name of the current
    run set. If the trajectory is not set to a run 'run_set_ALL' is used.

    :const:`~pypet.pypetconstants.LOG_PROC` ($proc) is replaced by the name fo the
    current process.

    :param traj:  A trajectory container
    :param filename:  A filename string
    :param process_name:

        The name of the desired process. If `None` the name of the current process is
        taken determined by the multiprocessing module.

    :return: The new filename

    """
    if pypetconstants.LOG_ENV in filename:
        env_name = traj.v_environment_name
        filename = filename.replace(pypetconstants.LOG_ENV, env_name)
    if pypetconstants.LOG_TRAJ in filename:
        traj_name = traj.v_name
        filename = filename.replace(pypetconstants.LOG_TRAJ, traj_name)
    if pypetconstants.LOG_RUN in filename:
        run_name = traj.f_wildcard('$')
        filename = filename.replace(pypetconstants.LOG_RUN, run_name)
    if pypetconstants.LOG_SET in filename:
        set_name = traj.f_wildcard('$set')
        filename = filename.replace(pypetconstants.LOG_SET, set_name)
    if pypetconstants.LOG_PROC in filename:
        if process_name is None:
            process_name = multip.current_process().name
        filename = filename.replace(pypetconstants.LOG_PROC, process_name)
    return filename


def get_strings(args):
    """Returns all valid python strings inside a given argument string."""
    string_list = []
    for elem in ast.walk(ast.parse(args)):
        if isinstance(elem, ast.Str):
            string_list.append(elem.s)
    return string_list


class HasLogger(HasSlots):
    """Abstract super class that automatically adds a logger to a class.

    To add a logger to a sub-class of yours simply call ``myobj._set_logger(name)``.
    If ``name=None`` the logger is chosen as follows:

        ``self._logger = logging.getLogger(self.__class.__.__module__ + '.' + self.__class__.__name__)``

    The logger can be accessed via ``myobj._logger``.

    """

    __slots__ = ('_logger',)

    def __getstate__(self):
        """Called for pickling.

        Removes the logger to allow pickling and returns a copy of `__dict__`.

        """
        state_dict = super(HasLogger, self).__getstate__()
        if '_logger' in state_dict:
            # Pickling does not work with loggers objects, so we just keep the logger's name:
            state_dict['_logger'] = self._logger.name
        return state_dict

    def __setstate__(self, statedict):
        """Called after loading a pickle dump.

        Restores `__dict__` from `statedict` and adds a new logger.

        """
        super(HasLogger, self).__setstate__(statedict)
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
            cls = self.__class__
            name = '%s.%s' % (cls.__module__, cls.__name__)
        self._logger = logging.getLogger(name)


class LoggingManager(object):
    """ Manager taking care of all logging related issues.

    :param trajectory: Trajectory container of Mock
    :param log_config: Logging configuration

        Can be a a full name of an `ini` file. An already instantiated config parser,
        or a logging dictionary.

    :param log_stdout: If `stdout` should be logged.

    :param report_progress:

        How to report progress.

    """
    def __init__(self, trajectory=None, log_config=None, log_stdout=False,
                 report_progress=False):
        self.trajectory = trajectory
        self.log_config = log_config
        self._sc_config = None
        self._mp_config = None
        self.log_stdout = log_stdout
        self.report_progress = report_progress
        self._tools = []
        self._null_handler = NullHandler()
        self._format_string = 'PROGRESS: Finished %d/%d runs '
        # Format string for the progressbar

    def __getstate__(self):
        """ConfigParsers are not guaranteed to be picklable so we need to remove these."""
        state_dict = self.__dict__.copy()
        if isinstance(state_dict['log_config'], cp.RawConfigParser):
            # Config Parsers are not guaranteed to be picklable
            state_dict['log_config'] = True
        return state_dict

    def show_progress(self, n, total_runs):
        """Displays a progressbar"""
        if self.report_progress:
            percentage, logger_name, log_level = self.report_progress
            if logger_name == 'print':
                logger = 'print'
            else:
                logger = logging.getLogger(logger_name)

            if n == 0:
                # Compute the number of digits and avoid log10(0)
                digits = int(math.log10(total_runs + 0.1)) + 1
                self._format_string = 'PROGRESS: Finished %' + '%d' % digits + 'd/%d runs '

            fmt_string = self._format_string % (n + 1, total_runs) + '%s'
            reprint = log_level == 0
            progressbar(n, total_runs, percentage_step=percentage,
                        logger=logger, log_level=log_level,
                        fmt_string=fmt_string, reprint=reprint)

    def add_null_handler(self):
        """Adds a NullHandler to the root logger.

        This is simply added to avoid warnings that no logger has been configured.

        """
        root = logging.getLogger()
        root.addHandler(self._null_handler)

    def remove_null_handler(self):
        """Removes the NullHandler from the root logger."""
        root = logging.getLogger()
        root.removeHandler(self._null_handler)

    @staticmethod
    def tabula_rasa():
        """Removes all loggers and logging handlers. """
        erase_dict = {'disable_existing_loggers': False, 'version': 1}
        dictConfig(erase_dict)

    @staticmethod
    def _check_and_replace_parser_args(parser, section, option, rename_func, make_dirs=True):
        """ Searches for parser settings that define filenames.

        If such settings are found, they are renamed according to the wildcard
        rules. Moreover, it is also tried to create the corresponding folders.

        :param parser:  A config parser
        :param section: A config section
        :param option: The section option
        :param rename_func: A function to rename found files
        :param make_dirs: If the directories of the file should be created.

        """
        args = parser.get(section, option, raw=True)
        strings = get_strings(args)
        replace = False
        for string in strings:
            isfilename = any(x in string for x in FILENAME_INDICATORS)
            if isfilename:
                newstring = rename_func(string)
                if make_dirs:
                    try_make_dirs(newstring)
                # To work with windows path specifications we need this replacement:
                raw_string = string.replace('\\', '\\\\')
                raw_newstring = newstring.replace('\\', '\\\\')
                args = args.replace(raw_string, raw_newstring)
                replace = True
        if replace:
            parser.set(section, option, args)

    @staticmethod
    def _parser_to_string_io(parser):
        """Turns a ConfigParser into a StringIO stream."""
        memory_file = StringIO()
        parser.write(memory_file)
        memory_file.flush()
        memory_file.seek(0)
        return memory_file

    @staticmethod
    def _find_multiproc_options(parser):
        """ Searches for multiprocessing options within a ConfigParser.

        If such options are found, they are copied (without the `'multiproc_'` prefix)
        into a new parser.

        """
        sections = parser.sections()
        if not any(section.startswith('multiproc_') for section in sections):
            return None
        mp_parser = NoInterpolationParser()
        for section in sections:
            if section.startswith('multiproc_'):
                new_section = section.replace('multiproc_', '')
                mp_parser.add_section(new_section)
                options = parser.options(section)
                for option in options:
                    val = parser.get(section, option, raw=True)
                    mp_parser.set(new_section, option, val)
        return mp_parser

    @staticmethod
    def _find_multiproc_dict(dictionary):
        """ Searches for multiprocessing options in a given `dictionary`.

        If found they are copied (without the `'multiproc_'` prefix)
        into a new dictionary

        """
        if not any(key.startswith('multiproc_') for key in dictionary.keys()):
            return None
        mp_dictionary = {}
        for key in dictionary.keys():
            if key.startswith('multiproc_'):
                new_key = key.replace('multiproc_', '')
                mp_dictionary[new_key] = dictionary[key]
        mp_dictionary['version'] = dictionary['version']
        if 'disable_existing_loggers' in dictionary:
            mp_dictionary['disable_existing_loggers'] = dictionary['disable_existing_loggers']
        return mp_dictionary

    def check_log_config(self):
        """ Checks and converts all settings if necessary passed to the Manager.

        Searches for multiprocessing options as well.

        """
        if self.report_progress:
            if self.report_progress is True:
                self.report_progress = (5, 'pypet', logging.INFO)
            elif isinstance(self.report_progress, (int, float)):
                self.report_progress = (self.report_progress, 'pypet', logging.INFO)
            elif isinstance(self.report_progress, compat.base_type):
                self.report_progress = (5, self.report_progress, logging.INFO)
            elif len(self.report_progress) == 2:
                self.report_progress = (self.report_progress[0], self.report_progress[1],
                                        logging.INFO)

        if self.log_config:
            if self.log_config == pypetconstants.DEFAULT_LOGGING:
                pypet_path = os.path.abspath(os.path.dirname(__file__))
                init_path = os.path.join(pypet_path, 'logging')
                if os.sep == '\\':
                    # Use the windows setting
                    # The only differences is the path separator `\`
                    self.log_config = os.path.join(init_path, 'windows_default.ini')
                else:
                    self.log_config = os.path.join(init_path, 'default.ini')

            if isinstance(self.log_config, compat.base_type):
                if not os.path.isfile(self.log_config):
                    raise ValueError('Could not find the logger init file '
                                     '`%s`.' % self.log_config)

            if isinstance(self.log_config, compat.base_type):
                parser = NoInterpolationParser()
                parser.read(self.log_config)
            elif isinstance(self.log_config, cp.RawConfigParser):
                parser = self.log_config
            else:
                parser = None

            if parser is not None:
                self._sc_config = self._parser_to_string_io(parser)
                self._mp_config = self._find_multiproc_options(parser)
                if self._mp_config is not None:
                    self._mp_config = self._parser_to_string_io(self._mp_config)

            elif isinstance(self.log_config, dict):
                self._sc_config = self.log_config
                self._mp_config = self._find_multiproc_dict(self._sc_config)

        if self.log_stdout:
            if self.log_stdout is True:
                self.log_stdout = ('STDOUT', logging.INFO)
            if isinstance(self.log_stdout, compat.base_type):
                self.log_stdout = (self.log_stdout, logging.INFO)
            if isinstance(self.log_stdout, int):
                self.log_stdout = ('STDOUT', self.log_stdout)

    def _handle_config_parsing(self, log_config):
        """ Checks for filenames within a config file and translates them.

        Moreover, directories for the files are created as well.

        :param log_config: Config file as a stream (like StringIO)

        """
        parser = NoInterpolationParser()
        parser.readfp(log_config)

        rename_func = lambda string: rename_log_file(self.trajectory, string)

        sections = parser.sections()
        for section in sections:
            options = parser.options(section)
            for option in options:
                if option == 'args':
                    self._check_and_replace_parser_args(parser, section, option,
                                                        rename_func=rename_func)
        return parser

    def _handle_dict_config(self, log_config):
        """Recursively walks and copies the `log_config` dict and searches for filenames.

        Translates filenames and creates directories if necessary.

        """
        new_dict = dict()
        for key in log_config.keys():
            if key == 'filename':
                filename = log_config[key]
                filename = rename_log_file(self.trajectory, filename)
                new_dict[key] = filename
                try_make_dirs(filename)
            elif isinstance(log_config[key], dict):
                inner_dict = self._handle_dict_config(log_config[key])
                new_dict[key] = inner_dict
            else:
                new_dict[key] = log_config[key]
        return new_dict

    def make_logging_handlers_and_tools(self, multiproc=False):
        """Creates logging handlers and redirects stdout."""

        log_stdout = self.log_stdout
        if multiproc and hasattr(os, 'fork'):
            # If we allow forking and it is possible we already have a redirection of stdout
            log_stdout = False

        if self.log_config:
            if multiproc:
                proc_log_config = self._mp_config
            else:
                proc_log_config = self._sc_config

            if proc_log_config:
                if isinstance(proc_log_config, dict):
                    new_dict = self._handle_dict_config(proc_log_config)
                    dictConfig(new_dict)
                else:
                    parser = self._handle_config_parsing(proc_log_config)
                    memory_file = self._parser_to_string_io(parser)
                    fileConfig(memory_file, disable_existing_loggers=False)

        if log_stdout:
            #  Create a logging mock for stdout
            std_name, std_level = self.log_stdout

            stdout = StdoutToLogger(std_name, log_level=std_level)
            stdout.start()
            self._tools.append(stdout)

    def finalize(self, remove_all_handlers=True):
        """Finalizes the manager, closes and removes all handlers if desired."""
        for tool in self._tools:
            tool.finalize()
        self._tools = []
        for config in (self._sc_config, self._mp_config):
            if hasattr(config, 'close'):
                config.close()
        self._sc_config = None
        self._mp_config = None
        if remove_all_handlers:
            self.tabula_rasa()


class NoInterpolationParser(cp.ConfigParser):
    """Dummy class to solve a Python 3 bug/feature in configparser.py"""
    def __init__(self):
        try:
            # Needed for Python 3, see [http://bugs.python.org/issue21265]
            super(NoInterpolationParser, self).__init__(interpolation=None)
        except TypeError:
            # Python 2.x
            cp.ConfigParser.__init__(self)


class DisableLogger(object):
    """Context Manager that disables logging"""

    def __enter__(self):
        logging.disable(logging.CRITICAL)

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.disable(logging.NOTSET)


class StdoutToLogger(HasLogger):
    """Fake file-like stream object that redirects writes to a logger instance."""
    def __init__(self, logger_name, log_level=logging.INFO):
        self._logger_name = logger_name
        self._log_level = log_level
        self._linebuf = ''
        self._recursion = False
        self._redirection = False
        self._original_steam = None
        #self._logger = logging.getLogger(self._logger_name)
        self._set_logger(name=self._logger_name)

    def __getstate__(self):
        state_dict = super(StdoutToLogger, self).__getstate__()
        # The original stream cannot be pickled
        state_dict['_original_stream'] = None

    def start(self):
        """Starts redirection of `stdout`"""
        if sys.stdout is not self:
            self._original_steam = sys.stdout
            sys.stdout = self
            self._redirection = True
        if self._redirection:
            print('Established redirection of `stdout`.')

    def write(self, buf):
        """Writes data from buffer to logger"""
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
        """Disables redirection"""
        if self._original_steam is not None and self._redirection:
            sys.stdout = self._original_steam
            print('Disabled redirection of `stdout`.')
            self._redirection = False
            self._original_steam = None

