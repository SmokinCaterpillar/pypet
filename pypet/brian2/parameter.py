__author__ = ['Henri Bunting', 'Robert Meyer']

# import brian2
import brian2.numpy_ as np
import pandas as pd
from pypet.parameter import Parameter, Result, ObjectTable
from brian2.units.fundamentalunits import Quantity, get_unit_fast
from pypet.utils.helpful_classes import HashArray
#from pypet.tests.testutils.ioutils import get_root_logger
#from brian2.units.fundamentalunits import is_dimensionless, get_dimensions
#from brian2.core.variables import get_value_with_unit

from brian2.monitors import SpikeMonitor, StateMonitor, PopulationRateMonitor

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
        elif super(Brian2Parameter, self).f_supports(data):
            return True
        return False

    def _values_of_same_type(self, val1, val2):

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
    ''' Identifier String to label brian result '''

    __slots__ = ()

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
        elif super(Brian2Result, self)._supports(data):
            return True
        return False

    def _values_of_same_type(self, val1, val2):

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

        store_dict = {}

        for key in self._data:
            val = self._data[key]
            if isinstance(val, Quantity):
                unit = get_unit_fast(val)
                value = val/unit
                # Potentially the results are very big in contrast to small parameters
                # Accordingly, an ObjectTable might not be the best choice after all for a result
                if isinstance(val, np.ndarray) and len(val.shape) == 0:
                    # Convert 0-dimensional arrays to regular numpy floats
                    value = np.float(value)
                store_dict[key + Brian2Result.IDENTIFIER + 'value'] = value
                store_dict[key + Brian2Result.IDENTIFIER + 'unit'] = repr(unit)

            else:
                store_dict[key] = val

        return store_dict

    def _load(self, load_dict):

        for key in load_dict:
            if Brian2Result.IDENTIFIER in key:

                new_key = key.split(Brian2Result.IDENTIFIER)[0]

                if new_key in self._data:
                    # We already extracted the unit/value pair
                    continue

                # Recreate the brain units from the vale as float and unit as string:
                unit = eval(load_dict[new_key + Brian2Result.IDENTIFIER + 'unit'])
                value = load_dict[new_key + Brian2Result.IDENTIFIER +'value']
                self._data[new_key] = value * unit
            else:
                self._data[key] = load_dict[key]


class Brian2MonitorResult(Brian2Result):

    __slots__ = ('_monitor_type',)

    def __init__(self, full_name, *args, **kwargs):
        self._monitor_type = None
        super(Brian2MonitorResult, self).__init__(full_name, *args, **kwargs)

    def _store(self):
        store_dict = super(Brian2MonitorResult, self)._store()

        if self._monitor_type is not None:
            store_dict['monitor_type'] = self._monitor_type

        return store_dict

    def _load(self, load_dict):
        if 'monitor_type' in load_dict:
            self._monitor_type = load_dict.pop('monitor_type')
        super(Brian2MonitorResult, self)._load(load_dict)

    @property
    def v_monitor_type(self):
        """ The type of the stored monitor. Each MonitorResult can only manage a single Monitor.
        """
        return self._monitor_type

    def f_set_single(self, name, item):
        """ To add a monitor use `f_set_single('monitor', brian_monitor)`.

        Otherwise `f_set_single` works similar to :func:`~pypet.parameter.Result.f_set_single`.
        """
        if type(item) in [SpikeMonitor, StateMonitor, PopulationRateMonitor]:
            if self.v_stored:
                self._logger.warning('You are changing an already stored result. If '
                                     'you not explicitly overwrite the data on disk, '
                                     'this change might be lost and not propagated to disk.')

            self._extract_monitor_data(item)
        else:
            super(Brian2MonitorResult, self).f_set_single(name, item)

    def _extract_monitor_data(self, monitor):

        if self._monitor_type is not None:
            raise TypeError('Your result `%s` already extracted data from a `%s` monitor.'
                             ' Please use a new empty result for a new monitor.')

        self._monitor_type = monitor.__class__.__name__

        if isinstance(monitor, SpikeMonitor):
            self._extract_spike_monitor(monitor)

        elif isinstance(monitor, StateMonitor):
            self._extract_state_monitor(monitor)

        elif isinstance(monitor, PopulationRateMonitor):
            self._extract_population_rate_monitor(monitor)

        else:
            raise ValueError('Monitor Type %s is not supported (yet)' % str(type(monitor)))

    def _extract_state_monitor(self, monitor):

        self.f_set(record_variables=monitor.record_variables)
        self.f_set(record=monitor.record)
        self.f_set(when=monitor.when)
        self.f_set(source=str(monitor.source))

        times=np.array(monitor.t[:])
        if len(times) > 0:
            self.f_set(t=times)

            for varname in monitor.record_variables:
                val = getattr(monitor, varname)
                self.f_set(**{varname: val})

    def _extract_spike_monitor(self, monitor):

        self.f_set(source=str(monitor.source))
        self.f_set(num_spikes=monitor.num_spikes)
        self.f_set(when=monitor.when)

        times = monitor.t[:]

        if len(times) > 0:
            self.f_set(t=times)
            self.f_set(i=monitor.i[:])

            for varname in monitor.record_variables:
                val = getattr(monitor, varname)
                self.f_set(**{varname: val[:]})

    def _extract_population_rate_monitor(self, monitor):

        times = monitor.t[:]
        self.f_set(source=str(monitor.source))
        if len(times) > 0:
            self.f_set(t=times)
            self.f_set(rate=monitor.rate[:])
