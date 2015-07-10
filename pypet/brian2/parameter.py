__author__ = 'Henri Bunting'

# import brian2
import brian2.numpy_ as np
import pandas as pd
from pypet.parameter import Parameter, Result, ObjectTable
from brian2.units.fundamentalunits import Quantity, get_unit_fast
from pypet.utils.helpful_classes import HashArray
#from pypet.tests.testutils.ioutils import get_root_logger
#from brian2.units.fundamentalunits import is_dimensionless, get_dimensions
#from brian2.core.variables import get_value_with_unit

from brian2.monitors import SpikeMonitor
from brian2.monitors import StateMonitor

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
                store_dict[key + Brian2Result.IDENTIFIER] = ObjectTable(data={'value': [value], 'unit': [repr(unit)]})

            else:
                store_dict[key] = val

        return store_dict


    def _load(self, load_dict):

        for key in load_dict:
            if Brian2Result.IDENTIFIER in key:
                data_table = load_dict[key]

                new_key = key.split(Brian2Result.IDENTIFIER)[0]

                # Recreate the brain units from the vale as float and unit as string:
                unit = eval(data_table['unit'][0])
                value = data_table['value'][0]
                self._data[new_key] = value * unit
            else:
                self._data[key] = load_dict[key]



class Brian2MonitorResult(Result):

    TABLE_MODE = 'TABLE'
    '''Table storage mode for SpikeMonitor and StateSpikeMonitor'''

    ARRAY_MODE = 'ARRAY'
    '''Array storage mode, not recommended if you have many neurons!'''

    #keywords=set(['data','values','spikes','times','rate','count','mean_var',])
    __slots__ = ('_storage_mode', '_monitor_type')

    def __init__(self, full_name, *args, **kwargs):

        self._storage_mode = None
        self._monitor_type = None
        storage_mode = kwargs.pop('storage_mode', Brian2MonitorResult.TABLE_MODE)
        self.v_storage_mode = storage_mode

        super(Brian2MonitorResult, self).__init__(full_name, *args, **kwargs)

    def _store(self):
        store_dict = super(Brian2MonitorResult, self)._store()

        if self._monitor_type is not None:
            store_dict['monitor_type'] = self._monitor_type
        if self._monitor_type in ['SpikeMonitor']:
            store_dict['storage_mode'] = self.v_storage_mode

        return store_dict

    def _load(self, load_dict):
        if 'monitor_type' in load_dict:
            self._monitor_type = load_dict.pop('monitor_type')
        if self._monitor_type in ['SpikeMonitor', 'StateSpikeMonitor']:
            self._storage_mode = load_dict.pop('storage_mode')

        super(Brian2MonitorResult, self)._load(load_dict)

    @property
    def v_storage_mode(self):
        """The storage mode for SpikeMonitor and StateSpikeMonitor

        There are two storage modes:

        * :const:`~pypet.brian.parameter.BrianMonitorResult.TABLE_MODE`: ('TABLE')

            Default, information is stored into a single table where
            the first column is the neuron index,
            second column is the spike time
            following columns contain variable values (in case of the StateSpikeMonitor)
            This is a very compact storage form.

        * :const:`~pypet.brian.parameter.BrianMonitorResult.ARRAY_MODE`: ('ARRAY')

            For each neuron there will be a new hdf5 array,
            i.e. if you have many neurons your result node will have many entries.
            Note that this mode does sort everything according to the neurons but
            reading and writing of data might take muuuuuch longer compared to
            the other mode.

        """
        return self._storage_mode

    @property
    def v_monitor_type(self):
        """ The type of the stored monitor. Each MonitorResult can only manage a single Monitor.
        """
        return self._monitor_type

    @v_storage_mode.setter
    def v_storage_mode(self, storage_mode):

        if self._monitor_type is not None:
            raise TypeError('Cannot change the storage mode if you already extracted a monitor.')

        assert (storage_mode == Brian2MonitorResult.ARRAY_MODE or
                storage_mode == Brian2MonitorResult.TABLE_MODE)
        self._storage_mode = storage_mode

    def f_set_single(self, name, item):
        """ To add a monitor use `f_set_single('monitor', brian_monitor)`.

        Otherwise `f_set_single` works similar to :func:`~pypet.parameter.Result.f_set_single`.
        """

        if type(item) in [SpikeMonitor, StateMonitor]:

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

        #elif isinstance(monitor, PopulationRateMonitor):
        #    self._extract_population_rate_monitor(monitor)

        else:
            raise ValueError('Monitor Type %s is not supported (yet)' % str(type(monitor)))


    def _extract_state_monitor(self, monitor):

        self.f_set(vars=monitor.record_variables)

        times=np.array(monitor.t_)
        if len(times) > 0:
            self.f_set(times=times)
            self.f_set(times_unit='second')

        ### Store recorded values ###
        for idx, varname in enumerate(monitor.record_variables):
            if idx == 0:
                self.f_set(record=monitor.record)
                self.f_set(when=monitor.when)
                self.f_set(source=str(monitor.source))

            self.f_set(**{varname + '_values': ObjectTable(data=getattr(monitor, varname))})

    @staticmethod
    def _get_format_string(monitor):
        digits = len(str(len(monitor.source)))
        format_string = '%0' + str(digits) + 'd'
        return format_string


    def _extract_spike_monitor(self, monitor):
        self.f_set(source=str(monitor.source))

        self.f_set(record=monitor.record)

        self.f_set(num_spikes=monitor.num_spikes)

        self.f_set(spiketimes_unit='second')

        dataframe = pd.DataFrame(data=zip(monitor.i, monitor.t_))
        neurons = [spike_num for spike_num in range(0, len(monitor.count))]
        spikes_by_neuron = dict()
        for neuron_num in neurons:
            spikes_by_neuron[neuron_num] = dataframe[dataframe[0] == neuron_num][1].astype(np.float64).tolist()

        if self._storage_mode == Brian2MonitorResult.TABLE_MODE:

            spikeframe = pd.DataFrame(data=zip(monitor.i, monitor.t_))
            spikeframe.columns=['neuron', 'spiketimes']
            #spikeframe['neuron']=spikeframe['neuron']
            spikeframe['neuron']=spikeframe['neuron'].astype(np.int32)
            #spikeframe['spiketimes']=spikeframe['spiketimes'].astype(np.float64)

            self.f_set(spikes=spikeframe)
            self.f_set(neurons_with_spikes=neurons)

        elif self._storage_mode == Brian2MonitorResult.ARRAY_MODE:
            format_string = self._get_format_string(monitor)
            self.f_set(format_string=format_string)

            spiked_neurons = set()

            for neuron in neurons:
                if len(spikes_by_neuron[neuron]) > 0:

                    spiked_neurons.add(neuron)

                    key = 'spiketimes_' + format_string % neuron
                    self.f_set(**{key: spikes_by_neuron[neuron]})

            spiked_neurons = sorted(list(spiked_neurons))
            if spiked_neurons:
                self.f_set(neurons_with_spikes=spiked_neurons)

        else:
            raise RuntimeError('You shall not pass!')

