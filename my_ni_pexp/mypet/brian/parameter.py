'''
Created on 10.06.2013

@author: robert
'''


from mypet.parameter import Parameter, BaseResult, Result,ObjectTable
from brian.units import *
from brian.stdunits import *
from brian.fundamentalunits import Unit, Quantity, get_unit
from brian.monitor import SpikeMonitor,SpikeCounter,StateMonitor, \
    PopulationSpikeCounter, PopulationRateMonitor, StateSpikeMonitor,  \
    MultiStateMonitor, ISIHistogramMonitor, VanRossumMetric, Monitor
from mypet.utils.helpful_functions import nest_dictionary

from inspect import getsource
import numpy as np
import logging
import pandas as pd


class BrianParameter(Parameter):

    IDENTIFIER = '__brn__'
    FLOAT_MODE = 'float'
    STRING_MODE = 'string'


    def __init__(self, fullname, data=None, comment='',storage_mode=''):
        super(BrianParameter,self).__init__(fullname,data,comment)

        if not storage_mode:
            self.set_storage_mode(BrianParameter.FLOAT_MODE)
        else:
            self.set_storage_mode(storage_mode)

    def set_storage_mode(self, storage_mode):
        assert (storage_mode == BrianParameter.STRING_MODE or storage_mode == BrianParameter.FLOAT_MODE)
        self._storage_mode = storage_mode

    def get_storage_mode(self):
        return self._storage_mode

    def _set_logger(self):
        self._logger = logging.getLogger('mypet.brian.parameter.BrianParameter=' + self._fullname)


    def supports(self, data):
        ''' Simply checks if data is supported '''
        if isinstance(data, Quantity):
            return True
        if super(BrianParameter,self).supports(data):
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


                if self.is_array():
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

                if self.is_array():
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


    table_mode = 'table'
    array_mode = 'array'

    keywords=set(['data','values','spikes','times','rate','count','mean_var',])

    def __init__(self, fullname, *args, **kwargs):
        super(BrianMonitorResult,self).__init__(fullname)

        self._storage_mode = kwargs.pop('storage_mode',BrianMonitorResult.table_mode)

        assert (self._storage_mode == BrianMonitorResult.table_mode or
                self._storage_mode == BrianMonitorResult.array_mode)


        self.set(*args,**kwargs)

    def set_single(self, name, item):

        if name == 'storage_mode':
            self._storage_mode = item
            assert (self._storage_mode == BrianMonitorResult.table_mode or
                self._storage_mode == BrianMonitorResult.array_mode)

        elif isinstance(item, (Monitor, MultiStateMonitor)):
            self._extract_monitor_data(item)
        else:
            super(BrianMonitorResult,self).set_single(name,item)


    
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
        self.set(count=monitor.count)
        self.set(source = str(monitor.source))
        self.set(delay = monitor.delay)
        self.set(nspikes = monitor.nspikes)


    def _extract_van_rossum_metric(self,monitor):

        self.set(source = str(monitor.source))
        self.set(N=monitor.N)
        self.set(tau=float(monitor.tau))
        self.set(tau_unit = 'second')
        #self.set(timestep = monitor.timestep)

        self.set(distance = monitor.distance)



    def _extract_isi_hist_monitor(self,monitor):

        self.set(source = str(monitor.source))
        self.set(count = monitor.count)
        self.set(bins = monitor.bins)
        self.set(delay = monitor.delay)
        self.set(nspikes = monitor.nspikes)



    def _extract_state_spike_monitor(self,monitor):

        self.set(source = str(monitor.source))



        varnames = monitor._varnames
        if not isinstance(varnames, tuple) :
            varnames = (varnames,)

        self.set(varnames = varnames)

        #self.set(record = monitor.record)
        self.set(delay=monitor.delay)
        self.set(nspikes = monitor.nspikes)

        # if hasattr(monitor, 'function'):
        #     data_dict['function'] = [getsource(monitor.function)]

        self.set(nspikes = monitor.nspikes)
        self.set(times_unit = 'second')

        if self._storage_mode==BrianMonitorResult.table_mode:
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
                    self.set(**{varname+'_unit':  repr(get_unit(var_list[0]))})
                    nounit_list = [np.float64(var) for var in var_list]
                    spike_dict[varname] = nounit_list
                    count = count +1

                self.set(spikes=pd.DataFrame(data=spike_dict))


        elif self._storage_mode==BrianMonitorResult.array_mode:
                for neuron in range(len(monitor.source)):
                    spikes = monitor.times(neuron)
                    if len(spikes)>0:
                        key = 'spiketimes_n%08d' % neuron
                        self.set(**{key:spikes})

                for varname in varnames:
                     for neuron in range(len(monitor.source)):
                         values = monitor.values(varname,neuron)
                         if len(values)>0:
                             key = varname+'_unit'
                             if not  key in self:
                                 self.set(**{key:  repr(get_unit(values[0]))})
                             key = varname+'_id%08d' % neuron
                             self.set(**{key:values})


        else:
                raise RuntimeError('You shall not pass!')


     
    def _extrac_spike_monitor(self,monitor):
        
        #assert isinstance(monitor, SpikeMonitor)


        self.set(source = str(monitor.source))

        self.set(record = monitor.record)

        self.set(nspikes = monitor.nspikes)

        self.set(times_unit='second')

        self.set(delay=monitor.delay)


        if self._storage_mode==BrianMonitorResult.table_mode:
            spike_dict={}

            if len(monitor.spikes)>0:
                zip_lists = zip(*monitor.spikes)
                time_list = zip_lists[1]

                nounit_list = [np.float64(time) for time in time_list]

                spike_dict['times'] = nounit_list
                spike_dict['neuron'] = list(zip_lists[0])

                spikeframe = pd.DataFrame(data=spike_dict)
                self.set(spikes=spikeframe)

        elif self._storage_mode==BrianMonitorResult.array_mode:
                for neuron, spikes in monitor.spiketimes.items():
                    if len(spikes)>0:
                        key = 'spiketimes_n%08d' % neuron
                        self.set(**{key:spikes})

        else:
                raise RuntimeError('You shall not pass!')



    def _extract_population_rate_monitor(self,monitor):
        assert isinstance(monitor, PopulationRateMonitor)
        

        self.set(source = str(monitor.source))
        self.set(times_unit = 'second', rate_unit='Hz')
        self.set(times = monitor.times)
        self.set(rate = monitor.rate)
        self.set(delay = monitor.delay)
        self.set(bin=monitor._bin)
        

    def _extract_spike_counter(self,monitor):

        self.set(nspikes = monitor.nspikes)
        self.set(source = str(monitor.source))
        self.set(count=monitor.count)
        self.set(delay=monitor.delay)



    def _extract_population_spike_counter(self,monitor):
        
        assert isinstance(monitor, PopulationSpikeCounter)

        self.set(nspikes = monitor.nspikes)
        self.set(source = str(monitor.source))
        self.set(delay=monitor.delay)




    def _extract_multi_state_monitor(self,monitors):

        self.set(vars = monitors.vars)


        if len(monitors.times)>0:
            self.set(times = monitors.times)
            self.set(times_unit = 'second')

        ### Store recorded values ###
        for idx,varname in enumerate(monitors.vars):
            monitor = monitors.monitors[varname]
            if idx == 0:


                self.set(record = monitor.record)

                self.set(when = monitor.when)

                self.set(timestep = monitor.timestep)

                self.set(source = str(monitor.P))


            self.set(**{varname+'_mean':monitor.mean})
            self.set(**{varname+'_var' : monitor.var})
            if len(monitors.times)>0:
                self.set(**{varname+'_values' : monitor.values})
            self.set (**{varname+'_unit' : repr(monitor.unit)})


    def _extract_state_monitor(self,monitor):

        self.set(varname = monitor.varname)
        self.set(unit = repr(monitor.unit))

            
        self.set(record = monitor.record)
        
        self.set(when = monitor.when)
        
        self.set(timestep = monitor.timestep)

        self.set(source = str(monitor.P))
        

        self.set(mean = monitor.mean)
        self.set(var = monitor.var)
        if len(monitor.times)>0:
            self.set(times = monitor.times)
            self.set(values = monitor.values)
            self.set(times_unit = 'second')

            
