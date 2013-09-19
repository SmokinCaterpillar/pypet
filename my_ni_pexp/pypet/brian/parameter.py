'''
Created on 10.06.2013

@author: robert
'''


from pypet.parameter import Parameter, BaseResult, Result,ObjectTable
from brian.units import *
from brian.stdunits import *
from brian.fundamentalunits import Unit, Quantity, get_unit
from brian.monitor import SpikeMonitor,SpikeCounter,StateMonitor, \
    PopulationSpikeCounter, PopulationRateMonitor, StateSpikeMonitor,  \
    MultiStateMonitor, ISIHistogramMonitor, VanRossumMetric, Monitor
from pypet.utils.helpful_functions import nest_dictionary

from inspect import getsource
import numpy as np
import logging
import pandas as pd


class BrianParameter(Parameter):
    ''' A Parameter class that supports BRIAN Quantities.

    There are two storage modes:

    * :const:`~my_ni_pexp.brian.parameter.BrianParameter.FLOAT_MODE': ('FLOAT')

        The value is stored as a float and the unit as a sting.

        i.e. `12 mV` is stored as `12.0` and `'1.0 * mV'`

    * :const:`~my_ni_pexp.brian.parameter.BrianParameter.STRING_MODE': ('STRING')

        The value and unit are stored combined together as a string.

        i.e. `12 mV` is stored as `'12.0 * mV'`


    Supports data for the standard :class:`~my_ni_pexp.parameter.Parameter`, too.

    '''

    IDENTIFIER = '__brn__'
    FLOAT_MODE = 'FLOAT'
    STRING_MODE = 'STRING'


    def __init__(self, full_name, data=None, comment='',storage_mode=FLOAT_MODE):
        super(BrianParameter,self).__init__(full_name,data,comment)

        self._storage_mode=None
        self.v_storage_mode = storage_mode

    @property
    def v_storage_mode(self):
        '''
        There are two storage modes:


        * :const:`~my_ni_pexp.brian.parameter.BrianParameter.FLOAT_MODE': ('FLOAT')

            The value is stored as a float and the unit as a sting.

            i.e. `12 mV` is stored as `12.0` and `'1.0 * mV'`

        * :const:`~my_ni_pexp.brian.parameter.BrianParameter.STRING_MODE': ('STRING')

            The value and unit are stored combined together as a string.

            i.e. `12 mV` is stored as `'12.0 * mV'`

        '''
        return self._storage_mode

    @v_storage_mode.setter
    def v_storage_mode(self, storage_mode):
        assert (storage_mode == BrianParameter.STRING_MODE or storage_mode == BrianParameter.FLOAT_MODE)
        self._storage_mode = storage_mode


    def _set_logger(self):
        self._logger = logging.getLogger('my_ni_pexp.brian.parameter.BrianParameter=' + self.v_full_name)


    def f_supports(self, data):
        ''' Simply checks if data is supported '''
        if isinstance(data, Quantity):
            return True
        if super(BrianParameter,self).f_supports(data):
            return True
        return False

    def _values_of_same_type(self,val1, val2):

        if isinstance(val1,Quantity):
            try:
                if not val1.has_same_dimensions(val2):
                    return False
            except AttributeError:
                return False
        elif isinstance(val2,Quantity):
            try:
                if not val2.has_same_dimensions(val1):
                    return False
            except AttributeError:
                return False

        elif not super(BrianParameter,self)._values_of_same_type(val1, val2):
            return False


        return True

    def _store(self):

        if isinstance(self._data,Quantity):
            store_dict={}

            if self._storage_mode == BrianParameter.STRING_MODE:

                valstr = self._data.in_best_unit(python_code=True)
                store_dict['data'] = ObjectTable(data={'data'+BrianParameter.IDENTIFIER:[valstr],
                                                       'mode' +BrianParameter.IDENTIFIER:[self._storage_mode] })


                if self.f_is_array():
                    valstr_list = []
                    for val in self._explored_data:
                        valstr = val.in_best_unit(python_code=True)
                        valstr_list.append(valstr)


                    store_dict['explored_data'] = ObjectTable(data={'data'+BrianParameter.IDENTIFIER:valstr_list})

            elif self._storage_mode == BrianParameter.FLOAT_MODE:
                unitstr = repr(get_unit_fast(self._data))
                value = float(self._data)
                store_dict['data'] = ObjectTable(data={'value'+BrianParameter.IDENTIFIER:[value],
                                                       'unit'+BrianParameter.IDENTIFIER:[unitstr],
                                                       'mode' +BrianParameter.IDENTIFIER:[self._storage_mode]})

                if self.f_is_array():
                    value_list = []
                    for val in self._explored_data:
                        value = float(val)
                        value_list.append(value)


                    store_dict['explored_data'] = ObjectTable(data={'value'+BrianParameter.IDENTIFIER:value_list})

            else:
                raise RuntimeError('You shall not pass!')




            return store_dict
        else:
            return super(BrianParameter,self)._store()


    def _load(self,load_dict):
        data_table = load_dict['data']
        data_name = data_table.columns.tolist()[0]
        if BrianParameter.IDENTIFIER in data_name:
            self._storage_mode = data_table['mode'+BrianParameter.IDENTIFIER][0]
            if self._storage_mode == BrianParameter.STRING_MODE:
                valstr = data_table['data'+BrianParameter.IDENTIFIER][0]

                self._data = eval(valstr)


                if 'explored_data' in load_dict:
                    explore_table = load_dict['explored_data']

                    valstr_col = explore_table['data'+BrianParameter.IDENTIFIER]
                    explore_list = []
                    for valstr in valstr_col:
                        brian_quantity = eval(valstr)
                        explore_list.append(brian_quantity)

                    self._explored_data=tuple(explore_list)
            elif self._storage_mode == BrianParameter.FLOAT_MODE:

                # Recreate the brain units from the vale as float and unit as string:
                unit = eval(data_table['unit'+BrianParameter.IDENTIFIER][0])
                value = data_table['value'+BrianParameter.IDENTIFIER][0]
                self._data = value*unit

                if 'explored_data' in load_dict:
                    explore_table = load_dict['explored_data']

                    value_col = explore_table['value'+BrianParameter.IDENTIFIER]
                    explore_list = []
                    for value in value_col:
                        brian_quantity = value*unit
                        explore_list.append(brian_quantity)

                    self._explored_data=tuple(explore_list)


        else:
            super(BrianParameter,self)._load(load_dict)

        self._default = self._data



class BrianMonitorResult(Result):
    ''' A Result class that supports brian monitors.

    Monitor attributes are extracted and added as results with the attribute names.

    Add monitor on `__init__` via `monitor=` or via `f_set(monitor=brian_monitor)`

    Following monitors are supported:

    * SpikeCounter

    * VanRossumMetric

    * PopulationSpikeCounter

    * StateSpikeMonitor

    * PopulationRateMonitor

    * ISIHistogramMonitor):

    * SpikeMonitor

    *  MultiStateMonitor

    * StateMonitor


    Example:

    >>> brian_result = BrianMonitorResult('example.brian.mymonitor', monitor=SpikeMonitor(...), comment='Im a SpikeMonitor Example!')
    >>> brian_result.nspikes
    1337

    '''

    TABLE_MODE = 'table'
    ARRAY_MODE = 'array'

    keywords=set(['data','values','spikes','times','rate','count','mean_var',])

    def __init__(self, full_name, *args, **kwargs):
        super(BrianMonitorResult,self).__init__(full_name)

        self._storage_mode=None
        storage_mode = kwargs.pop('storage_mode',BrianMonitorResult.TABLE_MODE)
        self.v_storage_mode=storage_mode

        self.f_set(*args,**kwargs)


    @property
    def v_storage_mode(self):
        return self._storage_mode

    @v_storage_mode.setter
    def v_storage_mode(self, storage_mode):
        assert (storage_mode == BrianMonitorResult.ARRAY_MODE or storage_mode == BrianMonitorResult.TABLE_MODE)
        self._storage_mode = storage_mode

    def f_set_single(self, name, item):
        ''' To add a monitor use `f_set_single('monitor',brian_monitor)`.

        Otherwise `f_set_single` works similar to :func:`~my_ni_pexp.parameter.Result.f_set_single`.
        '''

        if name == 'storage_mode':
            self.v_storage_mode=item

        elif isinstance(item, (Monitor, MultiStateMonitor)):
            self._extract_monitor_data(item)
        else:
            super(BrianMonitorResult,self).f_set_single(name,item)


    
    def _extract_monitor_data(self,monitor):
        ## Check for each monitor separately:



        if isinstance(monitor, SpikeCounter):
            self._extract_spike_counter(monitor)

        elif isinstance(monitor, VanRossumMetric):
            self._extract_van_rossum_metric(monitor)

        elif isinstance(monitor, PopulationSpikeCounter):
            self._extract_population_spike_counter(monitor)

        elif isinstance(monitor, StateSpikeMonitor):
            self._extract_state_spike_monitor(monitor)
        
        elif  isinstance(monitor, PopulationRateMonitor):
            self._extract_population_rate_monitor(monitor)


        elif isinstance(monitor, ISIHistogramMonitor):
            self._extract_isi_hist_monitor(monitor)

        elif isinstance(monitor,SpikeMonitor):
            self._extrac_spike_monitor(monitor)

        elif isinstance(monitor, MultiStateMonitor):
            self._extract_multi_state_monitor(monitor)
        
        elif isinstance(monitor,StateMonitor):
            self._extract_state_monitor(monitor)

            
        else:
            raise ValueError('Monitor Type %s is not supported (yet)' % str(type(monitor)))

    def _extract_spike_counter(self,monitor):
        self.f_set(count=monitor.count)
        self.f_set(source = str(monitor.source))
        self.f_set(delay = monitor.delay)
        self.f_set(nspikes = monitor.nspikes)


    def _extract_van_rossum_metric(self,monitor):

        self.f_set(source = str(monitor.source))
        self.f_set(N=monitor.N)
        self.f_set(tau=float(monitor.tau))
        self.f_set(tau_unit = 'second')
        #self.f_set(timestep = monitor.timestep)

        self.f_set(distance = monitor.distance)



    def _extract_isi_hist_monitor(self,monitor):

        self.f_set(source = str(monitor.source))
        self.f_set(count = monitor.count)
        self.f_set(bins = monitor.bins)
        self.f_set(delay = monitor.delay)
        self.f_set(nspikes = monitor.nspikes)



    def _extract_state_spike_monitor(self,monitor):

        self.f_set(source = str(monitor.source))



        varnames = monitor._varnames
        if not isinstance(varnames, tuple) :
            varnames = (varnames,)

        self.f_set(varnames = varnames)

        #self.f_set(record = monitor.record)
        self.f_set(delay=monitor.delay)
        self.f_set(nspikes = monitor.nspikes)

        # if hasattr(monitor, 'function'):
        #     data_dict['function'] = [getsource(monitor.function)]

        self.f_set(nspikes = monitor.nspikes)
        self.f_set(times_unit = 'second')

        if self._storage_mode==BrianMonitorResult.TABLE_MODE:
            spike_dict={}

            if len(monitor.spikes)>0:
                zip_lists = zip(*monitor.spikes)
                time_list = zip_lists[1]

                nounit_list = [np.float64(time) for time in time_list]

                spike_dict['times'] = nounit_list
                spike_dict['neuron'] = list(zip_lists[0])

                count = 2
                for varname in varnames:

                    var_list = list(zip_lists[count])
                    self.f_set(**{varname+'_unit':  repr(get_unit(var_list[0]))})
                    nounit_list = [np.float64(var) for var in var_list]
                    spike_dict[varname] = nounit_list
                    count = count +1

                self.f_set(spikes=pd.DataFrame(data=spike_dict))

        elif self._storage_mode==BrianMonitorResult.ARRAY_MODE:
                for neuron in range(len(monitor.source)):
                    spikes = monitor.times(neuron)
                    if len(spikes)>0:
                        key = 'spiketimes_%08d' % neuron
                        self.f_set(**{key:spikes})

                for varname in varnames:
                     for neuron in range(len(monitor.source)):
                         values = monitor.values(varname,neuron)
                         if len(values)>0:
                             key = varname+'_unit'
                             if not  key in self:
                                 self.f_set(**{key:  repr(get_unit(values[0]))})
                             key = varname+'_idx%08d' % neuron
                             self.f_set(**{key:values})


        else:
                raise RuntimeError('You shall not pass!')


     
    def _extrac_spike_monitor(self,monitor):
        
        #assert isinstance(monitor, SpikeMonitor)


        self.f_set(source = str(monitor.source))

        self.f_set(record = monitor.record)

        self.f_set(nspikes = monitor.nspikes)

        self.f_set(times_unit='second')

        self.f_set(delay=monitor.delay)


        if self._storage_mode==BrianMonitorResult.TABLE_MODE:
            spike_dict={}

            if len(monitor.spikes)>0:
                zip_lists = zip(*monitor.spikes)
                time_list = zip_lists[1]

                nounit_list = [np.float64(time) for time in time_list]

                spike_dict['times'] = nounit_list
                spike_dict['neuron'] = list(zip_lists[0])

                spikeframe = pd.DataFrame(data=spike_dict)
                self.f_set(spikes=spikeframe)

        elif self._storage_mode==BrianMonitorResult.ARRAY_MODE:
                for neuron, spikes in monitor.spiketimes.items():
                    if len(spikes)>0:
                        key = 'spiketimes_%08d' % neuron
                        self.f_set(**{key:spikes})

        else:
                raise RuntimeError('You shall not pass!')



    def _extract_population_rate_monitor(self,monitor):
        assert isinstance(monitor, PopulationRateMonitor)
        

        self.f_set(source = str(monitor.source))
        self.f_set(times_unit = 'second', rate_unit='Hz')
        self.f_set(times = monitor.times)
        self.f_set(rate = monitor.rate)
        self.f_set(delay = monitor.delay)
        self.f_set(bin=monitor._bin)
        

    def _extract_spike_counter(self,monitor):

        self.f_set(nspikes = monitor.nspikes)
        self.f_set(source = str(monitor.source))
        self.f_set(count=monitor.count)
        self.f_set(delay=monitor.delay)



    def _extract_population_spike_counter(self,monitor):
        
        assert isinstance(monitor, PopulationSpikeCounter)

        self.f_set(nspikes = monitor.nspikes)
        self.f_set(source = str(monitor.source))
        self.f_set(delay=monitor.delay)




    def _extract_multi_state_monitor(self,monitors):

        self.f_set(vars = monitors.vars)


        if len(monitors.times)>0:
            self.f_set(times = monitors.times)
            self.f_set(times_unit = 'second')

        ### Store recorded values ###
        for idx,varname in enumerate(monitors.vars):
            monitor = monitors.monitors[varname]
            if idx == 0:


                self.f_set(record = monitor.record)

                self.f_set(when = monitor.when)

                self.f_set(timestep = monitor.timestep)

                self.f_set(source = str(monitor.P))


            self.f_set(**{varname+'_mean':monitor.mean})
            self.f_set(**{varname+'_var' : monitor.var})
            if len(monitors.times)>0:
                self.f_set(**{varname+'_values' : monitor.values})
            self.f_set (**{varname+'_unit' : repr(monitor.unit)})


    def _extract_state_monitor(self,monitor):

        self.f_set(varname = monitor.varname)
        self.f_set(unit = repr(monitor.unit))

            
        self.f_set(record = monitor.record)
        
        self.f_set(when = monitor.when)
        
        self.f_set(timestep = monitor.timestep)

        self.f_set(source = str(monitor.P))
        

        self.f_set(mean = monitor.mean)
        self.f_set(var = monitor.var)
        if len(monitor.times)>0:
            self.f_set(times = monitor.times)
            self.f_set(values = monitor.values)
            self.f_set(times_unit = 'second')

            
