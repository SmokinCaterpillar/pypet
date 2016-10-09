"""Helper module that allows parsing of `.ini` files"""

__author__ = 'Robert Meyer'

import functools
import ast
import os
import configparser as cp

from pypet.pypetlogging import use_simple_logging


def parse_config(init_func):
    """Decorator wrapping the environment to use a config file"""
    @functools.wraps(init_func)
    def new_func(env, *args, **kwargs):
        config_interpreter = ConfigInterpreter(kwargs)
        # Pass the config data to the kwargs
        new_kwargs = config_interpreter.interpret()
        init_func(env, *args, **new_kwargs)
        # Add parameters and config data from the `.ini` file
        config_interpreter.add_parameters(env.traj)
    return new_func


class ConfigInterpreter(object):
    """ Helper class that parses an `.ini` file and passes the data to an environment."""
    def __init__(self, kwargs):
        self.kwargs = kwargs
        self.config_file = kwargs.pop('config', None)
        self.parser = None
        if self.config_file:
            if isinstance(self.config_file, str):
                # Check if the config file exists
                if not os.path.isfile(self.config_file):
                    raise ValueError('`%s` does not exist.' % self.config_file)
                # If yes parse it with a config parser
                self.parser = cp.ConfigParser()
                self.parser.read(self.config_file)
            elif isinstance(self.config_file, cp.RawConfigParser):
                # Already instantiaded parsers are also accepted
                self.parser = self.config_file
            else:
                raise RuntimeError('Your config file/parser format `%s` '
                                   'is not understood.' % str(self.config_file))

    def _collect_section(self, section):
        """Collects all settings within a section"""
        kwargs = {}
        try:
            if self.parser.has_section(section):
                options = self.parser.options(section)
                for option in options:
                    str_val = self.parser.get(section, option)
                    val = ast.literal_eval(str_val)
                    kwargs[option] = val
            return kwargs
        except:
            raise  # You can set a break point here for debugging!

    def _collect_config(self):
        """Collects all info from three sections"""
        kwargs = {}
        sections = ('storage_service', 'trajectory', 'environment')
        for section in sections:
            kwargs.update(self._collect_section(section))
        return kwargs

    def interpret(self):
        """Copies parsed arguments into the kwargs passed to the environment"""
        if self.config_file:
            new_kwargs = self._collect_config()
            for key in new_kwargs:
                # Already specified kwargs take precedence over the ini file
                if key not in self.kwargs:
                    self.kwargs[key] = new_kwargs[key]
            if not use_simple_logging(self.kwargs) and 'log_config' not in self.kwargs:
                self.kwargs['log_config'] = self.config_file
        return self.kwargs

    def add_parameters(self, traj):
        """Adds parameters and config from the `.ini` file to the trajectory"""
        if self.config_file:
            parameters = self._collect_section('parameters')
            for name in parameters:
                value = parameters[name]
                if not isinstance(value, tuple):
                    value = (value,)
                traj.f_add_parameter(name, *value)
            config = self._collect_section('config')
            for name in config:
                value = config[name]
                if not isinstance(value, tuple):
                    value = (value,)
                traj.f_add_config(name, *value)
