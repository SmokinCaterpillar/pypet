"""Module containing results and parameters that can be used to store `BRIAN data`_.

Parameters handling BRIAN data are instantiated by the
:class:`~pypet.brian.parameter.BrianParameter` class for any BRIAN Quantity.

The :class:`~pypet.brian.parameter.BrianResult` can store BRIAN Quantities
and the :class:`~pypet.brian.parameter.BrianMonitorResult` extracts data from
BRIAN Monitors.

All these can be combined with the experimental framework in `pypet.brian.network` to allow
fast setup of large scale BRIAN experiments.

.. _`BRIAN data`: http://briansimulator.org/

"""

___author__ = 'Robert Meyer'


from pypet.parameter import Parameter, Result, ObjectTable
# Unfortunately I have to do this for read the docs to be able to mock brian
from pypet.utils.decorators import copydoc
import pypet.pypetexceptions as pex

try:
    from brian.units import *
    from brian.stdunits import *
except TypeError:
    pass

from brian.fundamentalunits import Quantity, get_unit_fast
from brian.monitor import SpikeMonitor, SpikeCounter, StateMonitor, \
    PopulationSpikeCounter, PopulationRateMonitor, StateSpikeMonitor,  \
    MultiStateMonitor, ISIHistogramMonitor, VanRossumMetric, Monitor

import numpy as np
import pandas as pd


class BrianParameter(Parameter):
    """A Parameter class that supports BRIAN Quantities.

    Note that only scalar BRIAN quantities are supported, lists, tuples or dictionaries
    of BRIAN quantities cannot be handled.

    There are two storage modes, that can be either passed to constructor or changed
    via `v_storage_mode`:

    * :const:`~pypet.brian.parameter.BrianParameter.FLOAT_MODE`: ('FLOAT')

        The value is stored as a float and the unit as a sting.

        i.e. `12 mV` is stored as `12.0` and `'1.0 * mV'`

    * :const:`~pypet.brian.parameter.BrianParameter.STRING_MODE`: ('STRING')

        The value and unit are stored combined together as a string.

        i.e. `12 mV` is stored as `'12.0 * mV'`


    Supports data for the standard :class:`~pypet.parameter.Parameter`, too.

    """

    IDENTIFIER = '__brn__'
    ''' Identification string stored into column title of hdf5 table'''

    FLOAT_MODE = 'FLOAT'
    '''Float storage mode'''
    STRING_MODE = 'STRING'
    '''String storage mode'''


    def __init__(self, full_name, data=None, comment='', storage_mode=FLOAT_MODE):
        super(BrianParameter, self).__init__(full_name, data, comment)

        self._storage_mode = None
        self.v_storage_mode = storage_mode

    @property
    def v_storage_mode(self):
        """
        There are two storage modes:


        * :const:`~pypet.brian.parameter.BrianParameter.FLOAT_MODE`: ('FLOAT')

            The value is stored as a float and the unit as a sting.

            i.e. `12 mV` is stored as `12.0` and `'1.0 * mV'`

        * :const:`~pypet.brian.parameter.BrianParameter.STRING_MODE`: ('STRING')

            The value and unit are stored combined together as a string.

            i.e. `12 mV` is stored as `'12.0 * mV'`

        """
        return self._storage_mode

    @v_storage_mode.setter
    def v_storage_mode(self, storage_mode):
        assert (storage_mode == BrianParameter.STRING_MODE or
                storage_mode == BrianParameter.FLOAT_MODE)
        self._storage_mode = storage_mode


    def f_supports(self, data):
        """ Simply checks if data is supported """
        if isinstance(data, Quantity):
            return True
        if super(BrianParameter, self).f_supports(data):
            return True
        return False

    def _values_of_same_type(self, val1, val2):

        if isinstance(val1, Quantity):
            try:
                if not val1.has_same_dimensions(val2):
                    return False
            except AttributeError:
                return False
        elif isinstance(val2, Quantity):
            try:
                if not val2.has_same_dimensions(val1):
                    return False
            except AttributeError:
                return False

        elif not super(BrianParameter, self)._values_of_same_type(val1, val2):
            return False


        return True

    def _store(self):

        if isinstance(self._data, Quantity):
            store_dict = {}

            if self._storage_mode == BrianParameter.STRING_MODE:

                valstr = self._data.in_best_unit(python_code=True)
                store_dict['data' + BrianParameter.IDENTIFIER] = ObjectTable(
                    data={'data': [valstr]})


                if self.f_has_range():
                    valstr_list = []
                    for val in self._explored_range:
                        valstr = val.in_best_unit(python_code=True)
                        valstr_list.append(valstr)


                    store_dict['explored_data' + BrianParameter.IDENTIFIER] = \
                        ObjectTable(data={'data': valstr_list})

            elif self._storage_mode == BrianParameter.FLOAT_MODE:
                unitstr = repr(get_unit_fast(self._data))
                value = float(self._data)
                store_dict['data' + BrianParameter.IDENTIFIER] = ObjectTable(
                    data={'value': [value], 'unit': [unitstr]})

                if self.f_has_range():
                    value_list = []
                    for val in self._explored_range:
                        value = float(val)
                        value_list.append(value)


                    store_dict['explored_data' + BrianParameter.IDENTIFIER] = \
                        ObjectTable(data={'value': value_list})

            else:
                raise RuntimeError('You shall not pass!')

            self._locked = True

            return store_dict
        else:
            return super(BrianParameter, self)._store()


    def _load(self, load_dict):
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter `%s` is locked!' % self.v_full_name)

        try:
            data_table = load_dict['data' + BrianParameter.IDENTIFIER]

            if 'unit' in data_table:
                self._storage_mode = BrianParameter.FLOAT_MODE
            else:
                self._storage_mode = BrianParameter.STRING_MODE

            if self._storage_mode == BrianParameter.STRING_MODE:
                valstr = data_table['data'][0]

                self._data = eval(valstr)


                if 'explored_data' + BrianParameter.IDENTIFIER in load_dict:
                    explore_table = load_dict['explored_data' + BrianParameter.IDENTIFIER]

                    valstr_col = explore_table['data']
                    explore_list = []
                    for valstr in valstr_col:
                        brian_quantity = eval(valstr)
                        explore_list.append(brian_quantity)

                    self._explored_range = tuple(explore_list)
                    self._explored = True

            elif self._storage_mode == BrianParameter.FLOAT_MODE:

                # Recreate the brain units from the vale as float and unit as string:
                unit = eval(data_table['unit'][0])
                value = data_table['value'][0]
                self._data = value * unit

                if 'explored_data' + BrianParameter.IDENTIFIER in load_dict:
                    explore_table = load_dict['explored_data' + BrianParameter.IDENTIFIER]

                    value_col = explore_table['value']
                    explore_list = []
                    for value in value_col:
                        brian_quantity = value * unit
                        explore_list.append(brian_quantity)

                    self._explored_range = tuple(explore_list)
                    self._explored = True


        except KeyError:
            super(BrianParameter, self)._load(load_dict)

        self._default = self._data
        self._locked = True


class BrianDurationParameter(BrianParameter):
    """Special BRIAN parameter to specify orders and durations of subruns.

    The :class:`~pypet.brian.network.NetworkRunner` extracts the individual subruns
    for a given network from such duration parameters.
    The order of execution is defined by the property `v_order`.
    The exact values do not matter only the rank ordering.

    A Duration Parameter should be in time units (ms or s, for instance).

    DEPRECATED: Please use a normal :class:`~pypet.brian.BrianParameter` instead and
    add the property `order` to it's :class:`~pypet.annotations.Annotations`.
    No longer use:

        >>> subrun = BrianDurationParameter('mysubrun', 10 * s, order=42)

    But use:

        >>> subrun = BrianParameter('mysubrun', 10 * s)
        >>> subrun.v_annotations.order=42

    """
    def __init__(self, full_name, data=None, order=0, comment='',
                 storage_mode=BrianParameter.FLOAT_MODE):
        super(BrianDurationParameter, self).__init__(full_name, data, comment, storage_mode)
        self.v_annotations.order = order

    @property
    def v_order(self):
        """The order in which the subrun with a particular duration will be run
        by the network runner"""
        return self.v_annotations.order

    @v_order.setter
    def v_order(self, order):
        self.v_annotations.order = order

    def _load(self, load_dict):
        if 'order' in load_dict:
            self.v_annotations.order = load_dict['order']
        super(BrianDurationParameter, self)._load(load_dict)


class BrianResult(Result):
    """ A result class that can handle BRIAN quantities.

    Note that only scalar BRIAN quantities are supported, lists, tuples or dictionaries
    of BRIAN quantities cannot be handled.

    Supports also all data supported by the standard :class:`~pypet.parameter.Result`.

    Storage mode works as for :class:`~pypet.brian.parameter.BrianParameter`.

    """

    IDENTIFIER = BrianParameter.IDENTIFIER
    ''' Identifier String to label brian data '''

    FLOAT_MODE = 'FLOAT'
    '''Float storage mode'''

    STRING_MODE = 'STRING'
    '''String storage mode'''

    def __init__(self, full_name, *args, **kwargs):
        self._storage_mode = None
        storage_mode = kwargs.pop('storage_mode', BrianResult.FLOAT_MODE)
        self.v_storage_mode = storage_mode

        super(BrianResult, self).__init__(full_name, *args, **kwargs)

    @property
    def v_storage_mode(self):
        """
        There are two storage modes:


        * :const:`~pypet.brian.parameter.BrianResult.FLOAT_MODE`: ('FLOAT')

            The value is stored as a float and the unit as a sting,

            i.e. `12 mV` is stored as `12.0` and `'1.0 * mV'`

        * :const:`~pypet.brian.parameter.BrianResult.STRING_MODE`: ('STRING')

            The value and unit are stored combined together as a string,

            i.e. `12 mV` is stored as `'12.0 * mV'`

        """
        return self._storage_mode

    @v_storage_mode.setter
    def v_storage_mode(self, storage_mode):
        assert (storage_mode == BrianResult.STRING_MODE or storage_mode == BrianResult.FLOAT_MODE)
        self._storage_mode = storage_mode

    @copydoc(Result.f_set_single)
    def f_set_single(self, name, item):
        if BrianResult.IDENTIFIER in name:
            raise AttributeError('Your result name contains the identifier for brian data,'
                                 ' please do not use %s in your result names.' %
                                 BrianResult.IDENTIFIER)
        elif name == 'storage_mode':
            self.v_storage_mode = item
        else:
            super(BrianResult, self).f_set_single(name, item)

    def _supports(self, data):
        if isinstance(data, Quantity):
            return True
        else:
            return super(BrianResult, self)._supports(data)


    def _store(self):
        store_dict = {}
        for key in self._data:
            val = self._data[key]
            if isinstance(val, Quantity):

                if self._storage_mode == BrianResult.STRING_MODE:

                    valstr = val.in_best_unit(python_code=True)
                    store_dict[key + BrianResult.IDENTIFIER] = ObjectTable(
                        data={'data': [valstr]})

                elif self._storage_mode == BrianResult.FLOAT_MODE:
                    unitstr = repr(get_unit_fast(val))
                    value = float(val)
                    store_dict[key + BrianResult.IDENTIFIER] = ObjectTable(
                        data={'value': [value], 'unit': [unitstr]})

                else:
                    raise RuntimeError('You shall not pass!')

            else:
                store_dict[key] = val

        return store_dict


    def _load(self, load_dict):

        for key in load_dict:
            if BrianResult.IDENTIFIER in key:
                data_table = load_dict[key]

                if 'unit' in data_table:
                    self._storage_mode = BrianResult.FLOAT_MODE
                else:
                    self._storage_mode = BrianResult.STRING_MODE

                new_key = key.split(BrianResult.IDENTIFIER)[0]

                if self._storage_mode == BrianResult.STRING_MODE:
                    valstr = data_table['data'][0]

                    self._data[new_key] = eval(valstr)

                elif self._storage_mode == BrianResult.FLOAT_MODE:

                    # Recreate the brain units from the vale as float and unit as string:
                    unit = eval(data_table['unit'][0])
                    value = data_table['value'][0]
                    self._data[new_key] = value * unit
            else:
                self._data[key] = load_dict[key]


class BrianMonitorResult(Result):
    """ A Result class that supports brian monitors.

    Subclasses :class:`~pypet.parameter.Result`, NOT :class:`~pypet.brian.parameter.BrianResult`.
    The storage mode here works slightly different than in
    :class:`~pypet.brian.parameter.BrianResult` and :class:`~pypet.brian.parameter.BrianParameter`,
    see below.

    Monitor attributes are extracted and added as results with the attribute names.
    Note the original monitors are NOT stored, only their attribute/property values are kept.

    Add monitor on `__init__` via `monitor=` or via `f_set(monitor=brian_monitor)`

    **IMPORTANT**: You can only use 1 result per monitor. Otherwise a 'TypeError' is thrown.


    Example:

    >>> brian_result = BrianMonitorResult('example.brian_test_test.mymonitor',
                                            monitor=SpikeMonitor(...),
                                            storage_mode='TABLE',
                                            comment='Im a SpikeMonitor Example!')
    >>> brian_result.nspikes
    1337


    There are two storage modes in case you use the SpikeMonitor and StateSpikeMonitor:

    * :const:`~pypet.brian.parameter.BrianMonitorResult.TABLE_MODE`: ('TABLE')

        Default, information is stored into a single table where
        one column contains the neuron index, another the spiketimes and
        following columns contain variable values (in case of the StateSpikeMonitor)
        This is a very compact storage form.

    * :const:`~pypet.brian.parameter.BrianParameter.ARRAY_MODE`: ('ARRAY')

        For each neuron there will be a new hdf5 array,
        i.e. if you have many neurons your result node will have many entries.
        Note that this mode does sort everything according to the neurons but
        reading and writing of data might take muuuuuch longer compared to
        the other mode.

    Following monitors are supported and the following values are extraced:

    * SpikeCounter

        * count

            Array of spike counts for each neuron

        * nspikes

            Number of recorded spikes

        * source

            Name of source recorded from as string.

    * VanRossumMetric

        * tau

            Time constant of kernel.

        * tau_unit

            'second'

        * distance

            A square symmetric matrix containing the distances

        * N

            Number of neurons.

        * source

    * PopulationSpikeCounter

        * delay

            Recording delay

        * nspikes

        * source

    * StateSpikeMonitor

        * delay

        * nspikes

        * source

        * varnames

            Names of recorded variables as tuple of strings.

        * spiketimes_unit

            'second'

        * variablename_unit

            Unit of recorded variable as a string.
            'variablename' is mapped to the name of a recorded variable. For instance,
            if you recorded the membrane potential named 'vm' you would get a field named
            'vm_unit'.

        If you use v_storage_mode = :const:`~pypet.brian.parameter.BrianMonitorResult.TABLE_MODE`

            * spikes

                pandas DataFrame containing in the columns:

                'neuron': neuron indices

                'spiketimes': times of spiking

                'variablename': values of the recorded variables

        If you use v_storage_mode = :const:`~pypet.brian.parameter.BrianMonitorResult.ARRAY_MODE`

            * spiketimes_XXX

                spiketimes of neuron 'XXX' for each neuron you recorded from. The number of digits
                used to represent and format the neuron index are chosen automatically.

            * variablename_XXX

                Value of the recorded variable at spiketimes for neuron `XXX`

            * format_string

                String used to format the neuron index, for example `'%03d'`.


    * PopulationRateMonitor

        * times

            The times of the bins.

        * times_unit

            'second'

        * rate

            An array of rates in Hz

        * rate_unit

            'Hz'

        * source

        * bin

            The duration of a bin (in second).

        * delay

    * ISIHistogramMonitor:

        * source

        * delay

        * nspikes

        * bins

            The bins array passed at initialisation of the monitor.

        * count

            An array of length `len(bins)` counting how many ISIs were in each bin.

    * SpikeMonitor

        * delay

        * nspikes

        * source


        * spiketimes_unit

            'second'

        If you use v_storage_mode = :const:`~pypet.brian.parameter.BrianMonitorResult.TABLE_MODE`

            * spikes

                pandas DataFrame containing in the columns:

                'neuron': neuron indices

                'spiketimes': times of spiking

        If you use v_storage_mode = :const:`~pypet.brian.parameter.BrianMonitorResult.ARRAY_MODE`

            * spiketimes_XXX

                spiketimes of neuron 'XXX' for each neuron you recorded from. The number of digits
                used to represent and format the neuron index are chosen automatically.

            * format_string

                String used to format the neuron index, for example `'%03d'`.

    * StateMonitor

        * source

        * record

            What to record. Can be 'True' to record from all neurons. A single integer value
            or a list of integers.

        * when

            When recordings were made, for a list of potential values see BRIAN_.

        .. _BRIAN: http://briansimulator.org/docs/reference-monitors.html

        * timestep

            Integer defining the clock timestep a recording was made.

        * times

            Array of recording times

        * times_unit

            'second'

        * mean

            Mean value of the state variable for every neuron in the group. Only extracted if
            mean values are calculated by BRIAN. Note that for newer versions of BRIAN, means
            and variances are no longer extracted if `record` is NOT set to `False`.

        * var

            Unbiased estimated of variances of state variable for each neuron. Only extracted if
            variance values are calculated by BRIAN.

        * values

            A 2D array of the values of all recorded neurons, each row is a single neuron's value

        * unit

            The unit of the values as a string

        * varname

            Name of recorded variable

    * MultiStateMonitor

        As above but instead of values and unit, the result contains
        'varname_values' and 'varname_unit',
        where 'varname' is the name of the recorded variable.

    """

    TABLE_MODE = 'TABLE'
    '''Table storage mode for SpikeMonitor and StateSpikeMonitor'''

    ARRAY_MODE = 'ARRAY'
    '''Array storage mode, not recommended if you have many neurons!'''

    #keywords=set(['data','values','spikes','times','rate','count','mean_var',])

    def __init__(self, full_name, *args, **kwargs):

        self._storage_mode = None
        self._monitor_type = None
        storage_mode = kwargs.pop('storage_mode', BrianMonitorResult.TABLE_MODE)
        self.v_storage_mode = storage_mode

        super(BrianMonitorResult, self).__init__(full_name, *args, **kwargs)


    def _store(self):
        store_dict = super(BrianMonitorResult, self)._store()

        if self._monitor_type is not None:
            store_dict['monitor_type'] = self._monitor_type
        if self._monitor_type in ['SpikeMonitor', 'StateSpikeMonitor']:
            store_dict['storage_mode'] = self.v_storage_mode

        return store_dict

    def _load(self, load_dict):
        if 'monitor_type' in load_dict:
            self._monitor_type = load_dict.pop('monitor_type')
        if self._monitor_type in ['SpikeMonitor', 'StateSpikeMonitor']:
            self._storage_mode = load_dict.pop('storage_mode')

        super(BrianMonitorResult, self)._load(load_dict)

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

        assert (storage_mode == BrianMonitorResult.ARRAY_MODE or
                storage_mode == BrianMonitorResult.TABLE_MODE)
        self._storage_mode = storage_mode

    def f_set_single(self, name, item):
        """ To add a monitor use `f_set_single('monitor', brian_monitor)`.

        Otherwise `f_set_single` works similar to :func:`~pypet.parameter.Result.f_set_single`.
        """

        if isinstance(item, (Monitor, MultiStateMonitor)):

            if self.v_stored:
                self._logger.warning('You are changing an already stored result. If '
                                     'you not explicitly overwrite the data on disk, '
                                     'this change might be lost and not propagated to disk.')

            self._extract_monitor_data(item)
        else:
            super(BrianMonitorResult, self).f_set_single(name, item)


    
    def _extract_monitor_data(self, monitor):

        if self._monitor_type is not None:
            raise TypeError('Your result `%s` already extracted data from a `%s` monitor.'
                             ' Please use a new empty result for a new monitor.')

        self._monitor_type = monitor.__class__.__name__

        ## Check for each monitor separately:
        if isinstance(monitor, SpikeCounter):
            self._extract_spike_counter(monitor)

        elif isinstance(monitor, VanRossumMetric):
            self._extract_van_rossum_metric(monitor)

        elif isinstance(monitor, PopulationSpikeCounter):
            self._extract_population_spike_counter(monitor)

        elif isinstance(monitor, StateSpikeMonitor):
            self._extract_state_spike_monitor(monitor)
        
        elif isinstance(monitor, PopulationRateMonitor):
            self._extract_population_rate_monitor(monitor)

        elif isinstance(monitor, ISIHistogramMonitor):
            self._extract_isi_hist_monitor(monitor)

        elif isinstance(monitor, SpikeMonitor):
            self._extract_spike_monitor(monitor)

        elif isinstance(monitor, MultiStateMonitor):
            self._extract_multi_state_monitor(monitor)
        
        elif isinstance(monitor, StateMonitor):
            self._extract_state_monitor(monitor)

            
        else:
            raise ValueError('Monitor Type %s is not supported (yet)' % str(type(monitor)))

    def _extract_spike_counter(self, monitor):
        self.f_set(count=monitor.count)
        self.f_set(source=str(monitor.source))
        self.f_set(delay=monitor.delay)
        self.f_set(nspikes=monitor.nspikes)


    def _extract_van_rossum_metric(self, monitor):

        self.f_set(source=str(monitor.source))
        self.f_set(N=monitor.N)
        self.f_set(tau=float(monitor.tau))
        self.f_set(tau_unit='second')
        #self.f_set(timestep = monitor.timestep)

        self.f_set(distance=monitor.distance)



    def _extract_isi_hist_monitor(self, monitor):

        self.f_set(source=str(monitor.source))
        self.f_set(count=monitor.count)
        self.f_set(bins=monitor.bins)
        self.f_set(delay=monitor.delay)
        self.f_set(nspikes=monitor.nspikes)

    @staticmethod
    def _get_format_string(monitor):
        digits = len(str(len(monitor.source)))
        format_string = '%0' + str(digits) + 'd'
        return format_string

    def _extract_state_spike_monitor(self, monitor):

        self.f_set(source=str(monitor.source))

        varnames = monitor._varnames
        if not isinstance(varnames, tuple):
            varnames = (varnames,)

        for idx, varname in enumerate(varnames):
            unit = repr(get_unit_fast(monitor.spikes[0][idx + 2]))
            self.f_set(**{varname + '_unit': unit})


        self.f_set(varnames=varnames)

        #self.f_set(record = monitor.record)
        self.f_set(delay=monitor.delay)
        self.f_set(nspikes=monitor.nspikes)
        self.f_set(spiketimes_unit='second')


        if self._storage_mode == BrianMonitorResult.TABLE_MODE:
            spike_dict = {}

            if len(monitor.spikes) > 0:
                zip_lists = list(zip(*monitor.spikes))
                time_list = zip_lists[1]

                nounit_list = [np.float64(time) for time in time_list]

                spike_dict['spiketimes'] = nounit_list
                spike_dict['neuron'] = list(zip_lists[0])

                spiked_neurons = sorted(list(set(spike_dict['neuron'])))
                if spiked_neurons:
                    self.f_set(neurons_with_spikes=spiked_neurons)

                    count = 2
                    for varname in varnames:

                        var_list = list(zip_lists[count])

                        nounit_list = [np.float64(var) for var in var_list]
                        spike_dict[varname] = nounit_list
                        count += 1

                    self.f_set(spikes=pd.DataFrame(data=spike_dict))

        elif self._storage_mode == BrianMonitorResult.ARRAY_MODE:

            format_string = self._get_format_string(monitor)
            self.f_set(format_string=format_string)

            spiked_neurons = set()

            for neuron in range(len(monitor.source)):
                spikes = monitor.times(neuron)
                if len(spikes) > 0:

                    spiked_neurons.add(neuron)

                    key = 'spiketimes_' + format_string % neuron
                    self.f_set(**{key: spikes})

            spiked_neurons = sorted(list(spiked_neurons))
            if spiked_neurons:
                self.f_set(neurons_with_spikes=spiked_neurons)

            for varname in varnames:
                for neuron in range(len(monitor.source)):
                    values = monitor.values(varname, neuron)
                    if len(values) > 0:
                        key = varname + '_' + format_string % neuron
                        self.f_set(**{key: values})
        else:
            raise RuntimeError('You shall not pass!')

    def _extract_spike_monitor(self, monitor):
        
        #assert isinstance(monitor, SpikeMonitor)


        self.f_set(source=str(monitor.source))

        self.f_set(record=monitor.record)

        self.f_set(nspikes=monitor.nspikes)

        self.f_set(spiketimes_unit='second')


        self.f_set(delay=monitor.delay)


        if self._storage_mode == BrianMonitorResult.TABLE_MODE:
            spike_dict = {}

            if len(monitor.spikes) > 0:
                zip_lists = list(zip(*monitor.spikes))
                time_list = zip_lists[1]

                nounit_list = [np.float64(time) for time in time_list]

                spike_dict['spiketimes'] = nounit_list
                spike_dict['neuron'] = list(zip_lists[0])

                spiked_neurons = sorted(list(set(spike_dict['neuron'])))
                if spiked_neurons:
                    self.f_set(neurons_with_spikes=spiked_neurons)

                    spikeframe = pd.DataFrame(data=spike_dict)
                    self.f_set(spikes=spikeframe)

        elif self._storage_mode == BrianMonitorResult.ARRAY_MODE:
            format_string = self._get_format_string(monitor)
            self.f_set(format_string=format_string)

            spiked_neurons = set()

            for neuron, spikes in monitor.spiketimes.items():
                if len(spikes) > 0:

                    spiked_neurons.add(neuron)

                    key = 'spiketimes_' + format_string % neuron
                    self.f_set(**{key: spikes})

            spiked_neurons = sorted(list(spiked_neurons))
            if spiked_neurons:
                self.f_set(neurons_with_spikes=spiked_neurons)

        else:
            raise RuntimeError('You shall not pass!')

    def _extract_population_rate_monitor(self, monitor):
        assert isinstance(monitor, PopulationRateMonitor)
        

        self.f_set(source=str(monitor.source))
        self.f_set(times_unit='second', rate_unit='Hz')
        self.f_set(times=monitor.times)
        self.f_set(rate=monitor.rate)
        self.f_set(delay=monitor.delay)
        self.f_set(bin=monitor._bin)

    def _extract_population_spike_counter(self, monitor):
        
        assert isinstance(monitor, PopulationSpikeCounter)

        self.f_set(nspikes=monitor.nspikes)
        self.f_set(source=str(monitor.source))
        self.f_set(delay=monitor.delay)




    def _extract_multi_state_monitor(self, monitors):

        self.f_set(vars=monitors.vars)


        if len(monitors.times) > 0:
            self.f_set(times=monitors.times)
            self.f_set(times_unit='second')

        ### Store recorded values ###
        for idx, varname in enumerate(monitors.vars):
            monitor = monitors.monitors[varname]
            if idx == 0:


                self.f_set(record=monitor.record)

                self.f_set(when=monitor.when)

                self.f_set(timestep=monitor.timestep)

                self.f_set(source=str(monitor.P))

            if np.mean(monitor.mean) != 0.0:
                self.f_set(**{varname + '_mean': monitor.mean})
                self.f_set(**{varname + '_var': monitor.var})
            if len(monitors.times) > 0:
                self.f_set(**{varname + '_values': monitor.values})
            self.f_set(**{varname + '_unit': repr(monitor.unit)})


    def _extract_state_monitor(self, monitor):

        self.f_set(varname=monitor.varname)
        self.f_set(unit=repr(monitor.unit))

            
        self.f_set(record=monitor.record)
        
        self.f_set(when=monitor.when)
        
        self.f_set(timestep=monitor.timestep)

        self.f_set(source=str(monitor.P))
        self.f_set(times_unit='second')

        if np.mean(monitor.mean) != 0.0:
            self.f_set(mean=monitor.mean)
            self.f_set(var=monitor.var)
        if len(monitor.times) > 0:
            self.f_set(times=monitor.times)
            self.f_set(values=monitor.values)

