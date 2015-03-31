"""Module that handles dynamic imports of classes.

This is done in an independent module to avoid cluttered name spaces.

"""

__author__ = 'Robert Meyer'

import importlib
import inspect

from pypet.naturalnaming import ResultGroup, ParameterGroup, \
    DerivedParameterGroup, ConfigGroup, NNGroupNode, NNLeafNode
from pypet.parameter import BaseParameter, BaseResult, Parameter, Result, ArrayParameter, \
    PickleResult, SparseParameter, SparseResult
from pypet.shareddata import SharedResult


def load_class(full_class_string):
    """Loads a class from a string naming the module and class name.

    For example:
    >>> load_class(full_class_string = 'pypet.brian.parameter.BrianParameter')
    <BrianParameter>

    """

    class_data = full_class_string.split(".")
    module_path = ".".join(class_data[:-1])
    class_str = class_data[-1]
    module = importlib.import_module(module_path)

    # We retrieve the Class from the module
    return getattr(module, class_str)


def create_class(class_name, dynamic_imports):
    """Dynamically creates a class.

    It is tried if the class can be created by the already given imports.
    If not the list of the dynamically loaded classes is used.

    """
    try:
        new_class = globals()[class_name]

        if not inspect.isclass(new_class):
            raise TypeError('Not a class!')

        return new_class
    except (KeyError, TypeError):
        for dynamic_class in dynamic_imports:
            # Dynamic classes can be provided directly as a Class instance,
            # for example as `MyCustomParameter`,
            # or as a string describing where to import the class from,
            # for instance as `'mypackage.mymodule.MyCustomParameter'`.
            if inspect.isclass(dynamic_class):
                if class_name == dynamic_class.__name__:
                    return dynamic_class
            else:
                # The class name is always the last in an import string,
                # e.g. `'mypackage.mymodule.MyCustomParameter'`
                class_name_to_test = dynamic_class.split('.')[-1]
                if class_name == class_name_to_test:
                    new_class = load_class(dynamic_class)
                    return new_class
        raise ImportError('Could not create the class named `%s`.' % class_name)

