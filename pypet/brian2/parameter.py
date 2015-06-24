__author__ = 'Henri Bunting'

# import brian2
import brian2.numpy_ as np
from pypet.parameter import Parameter, Result, ObjectTable
from brian2.units.fundamentalunits import Quantity, get_unit_fast
from pypet.utils.helpful_classes import HashArray
#from pypet.tests.testutils.ioutils import get_root_logger
#from brian2.units.fundamentalunits import is_dimensionless, get_dimensions
#from brian2.core.variables import get_value_with_unit

import pypet.pypetexceptions as pex

try:
    from brian2.units.allunits import *
except TypeError:
    pass


class Brian2Parameter(Parameter):

    IDENTIFIER = '__brn2__'
    ''' Identification string stored into column title of hdf5 table'''

    __slots__ = ()

    def __init__(self, full_name, data=None, comment=''):
        super(Brian2Parameter, self).__init__(full_name, data, comment)

    def f_supports(self, data):
        """ Simply checks if data is supported """
        if isinstance(data, Quantity):
            return True
        # Is not needed either, parameters do not allow for lists
        # elif isinstance(data, list):
        #     for value in data:
        #         if not self.f_supports(value):
        #             return False
        #     return True
        elif super(Brian2Parameter, self).f_supports(data):
            return True
        return False

    def _values_of_same_type(self, val1, val2):

        ### This does not work, if one is a list and the other is not they
        #  are not of the same type
        # if isinstance(val2, list) and not isinstance(val1, list):
        #     return self._values_of_same_type([val1], val2)
        # if isinstance(val1, list) and not isinstance(val2, list):
        #     return self._values_of_same_type(val1, [val2])

        if isinstance(val1, Quantity):
            try:
                if not val1.has_same_dimensions(val2):
                    return False
            except TypeError:
                return False

        elif isinstance(val2, Quantity):
            try:
                if not val2.has_same_dimensions(val1):
                    return False
            except TypeError:
                return False

        elif not super(Brian2Parameter, self)._values_of_same_type(val1, val2):
            return False

        return True

    def _store(self):

        if type(self._data) not in [Quantity, list]:
            return super(Brian2Parameter, self)._store()
        else:
            store_dict = {}

            unit = get_unit_fast(self._data)
            value = self._data/unit
            store_dict['data' + Brian2Parameter.IDENTIFIER] = ObjectTable(data={'value': [value], 'unit': [repr(unit)]})

            if self.f_has_range():
                value_list = [value_with_unit/unit for value_with_unit in self._explored_range]
                store_dict['explored_data' + Brian2Parameter.IDENTIFIER] = ObjectTable(data={'value': value_list})

            self._locked = True

            return store_dict

    def _load(self, load_dict):
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter `%s` is locked!' % self.v_full_name)

        try:
            data_table = load_dict['data' + Brian2Parameter.IDENTIFIER]

            unit = eval(data_table['unit'][0])
            value = data_table['value'][0]
            self._data = value * unit

            if 'explored_data' + Brian2Parameter.IDENTIFIER in load_dict:
                explore_table = load_dict['explored_data' + Brian2Parameter.IDENTIFIER]

                value_col = explore_table['value']
                explore_list = [value * unit for value in value_col]

                self._explored_range = tuple(explore_list)
                self._explored = True

        except KeyError:
            super(Brian2Parameter, self)._load(load_dict)

        self._default = self._data
        self._locked = True



class Brian2Result(Result):

    IDENTIFIER = Brian2Parameter.IDENTIFIER
    ''' Identifier String to label brian data '''

    __slots__ = ('_storage_mode',)

    def __init__(self, full_name, *args, **kwargs):
        super(Brian2Result, self).__init__(full_name, *args, **kwargs)


    def f_set_single(self, name, item):
        if Brian2Result.IDENTIFIER in name:
            raise AttributeError('Your result name contains the identifier for brian data,'
                                 ' please do not use %s in your result names.' %
                                 Brian2Result.IDENTIFIER)
        else:
            super(Brian2Result, self).f_set_single(name, item)

    def _supports(self, data):
        """ Simply checks if data is supported """
        if isinstance(data, Quantity):
            return True
        # results do not check lists, sometimes to expensive
        # elif isinstance(data, list):
        #     for value in data:
        #         if not self._supports(value):
        #             return False
        #     return True
        elif super(Brian2Result, self)._supports(data):
            return True
        return False

    def _values_of_same_type(self, val1, val2):

        # What do you have about these lists all the time :-)
        # if isinstance(val2, list) and not isinstance(val1, list):
        #     return self._values_of_same_type([val1], val2)
        # if isinstance(val1, list) and not isinstance(val2, list):
        #     return self._values_of_same_type(val1, [val2])

        if isinstance(val1, Quantity):
            try:
                if not val1.has_same_dimensions(val2):
                    return False
            except TypeError:
                return False

        elif isinstance(val2, Quantity):
            try:
                if not val2.has_same_dimensions(val1):
                    return False
            except TypeError:
                return False

        elif not super(Brian2Result, self)._values_of_same_type(val1, val2):
            return False

        return True

    def _store(self):

        if type(self._data) not in [Quantity, list]:
            return super(Brian2Result, self)._store()
        else:
            store_dict = {}

            unit = get_unit_fast(self._data)
            value = self._data/unit
            store_dict['data' + Brian2Result.IDENTIFIER] = ObjectTable(data={'value': [value], 'unit': [repr(unit)]})

            return store_dict

    def _load(self, load_dict):

        try:
            data_table = load_dict['data' + Brian2Result.IDENTIFIER]

            unit = eval(data_table['unit'][0])
            value = data_table['value'][0]
            self._data = value * unit

        except KeyError:
            super(Brian2Result, self)._load(load_dict)
