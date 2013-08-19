'''
Created on 10.06.2013

@author: robert
'''


from mypet.parameter import Parameter, BaseResult, SimpleResult,ObjectTable
from brian.units import *
from brian.stdunits import *
from brian.fundamentalunits import Unit, Quantity, get_unit
from brian.monitor import SpikeMonitor,SpikeCounter,StateMonitor, \
    PopulationSpikeCounter, PopulationRateMonitor, StateSpikeMonitor,  \
    MultiStateMonitor, ISIHistogramMonitor, VanRossumMetric
from mypet.utils.helpful_functions import nest_dictionary

from inspect import getsource
import numpy as np
import logging


class BrianParameter(Parameter):

    identifier = '__brn__'
    float_mode = 'float'
    string_mode = 'string'


    def __init__(self, fullname, data=None, comment='',storage_mode=''):
        super(BrianParameter,self).__init__(fullname,data,comment)

        if not storage_mode:
            self.set_storage_mode(BrianParameter.float_mode)
        else:
            self.set_storage_mode(storage_mode)

    def set_storage_mode(self, storage_mode):
        assert (storage_mode == BrianParameter.string_mode or storage_mode == BrianParameter.float_mode)
        self._storage_mode = storage_mode

    def get_storage_mode(self):
        return self._storage_mode

    def _set_logger(self):
        self._logger = logging.getLogger('mypet.brian.parameter.BrianParameter=' + self._fullname)


    def _is_supported_data(self, data):
        ''' Simply checks if data is supported '''
        if isinstance(data, Quantity):
            return True
        if super(BrianParameter,self)._is_supported_data(data):
            return True
        return False

    def _values_of_same_type(self,val1, val2):
        if not super(BrianParameter,self)._values_of_same_type(val1, val2):
            return False

        if isinstance(val1,Quantity):
            if not val1.has_same_dimensions(val2):
                return False
        elif isinstance(val2,Quantity):
            if not val2.has_same_dimensions(val1):
                return False

        return True

    def __store__(self):

        if isinstance(self._data,Quantity):
            store_dict={}

            if self._storage_mode == BrianParameter.string_mode:

                valstr = self._data.in_best_unit(python_code=True)
                store_dict['data'] = ObjectTable(data={'data'+BrianParameter.identifier:[valstr],
                                                       'mode' +BrianParameter.identifier:[self._storage_mode] })


                if self.is_array():
                    valstr_list = []
                    for val in self._explored_data:
                        valstr = val.in_best_unit(python_code=True)
                        valstr_list.append(valstr)


                    store_dict['explored_data'] = ObjectTable(data={'data'+BrianParameter.identifier:valstr_list})

            elif self._storage_mode == BrianParameter.float_mode:
                unitstr = repr(get_unit_fast(self._data))
                value = float(self._data)
                store_dict['data'] = ObjectTable(data={'value'+BrianParameter.identifier:[value],
                                                       'unit'+BrianParameter.identifier:[unitstr],
                                                       'mode' +BrianParameter.identifier:[self._storage_mode]})

                if self.is_array():
                    value_list = []
                    for val in self._explored_data:
                        value = float(val)
                        value_list.append(value)


                    store_dict['explored_data'] = ObjectTable(data={'value'+BrianParameter.identifier:value_list})

            else:
                raise RuntimeError('You shall not pass!')




            return store_dict
        else:
            return super(BrianParameter,self).__store__()


    def __load__(self,load_dict):
        data_table = load_dict['data']
        data_name = data_table.columns.tolist()[0]
        if BrianParameter.identifier in data_name:
            self._storage_mode = data_table['mode'+BrianParameter.identifier][0]
            if self._storage_mode == BrianParameter.string_mode:
                valstr = data_table['data'+BrianParameter.identifier][0]

                self._data = eval(valstr)

                if 'explored_data' in load_dict:
                    explore_table = load_dict['explored_data']

                    valstr_col = explore_table['data'+BrianParameter.identifier]
                    explore_list = []
                    for valstr in valstr_col:
                        brian_quantity = eval(valstr)
                        explore_list.append(brian_quantity)

                    self._explored_data=tuple(explore_list)
            elif self._storage_mode == BrianParameter.float_mode:

                # Recreate the brain units from the vale as float and unit as string:
                unit = eval(data_table['unit'+BrianParameter.identifier][0])
                value = data_table['value'+BrianParameter.identifier][0]
                self._data = value*unit

                if 'explored_data' in load_dict:
                    explore_table = load_dict['explored_data']

                    value_col = explore_table['value'+BrianParameter.identifier]
                    explore_list = []
                    for value in value_col:
                        brian_quantity = value*unit
                        explore_list.append(brian_quantity)

                    self._explored_data=tuple(explore_list)


        else:
            super(BrianParameter,self).__load__(load_dict)



class BrianMonitorResult(SimpleResult):


    table_mode = 'table'
    array_mode = 'array'

    def __init__(self, fullname, monitor, *args, **kwargs):
        super(BrianMonitorResult,self).__init__(fullname)

        self._storage_mode = kwargs.pop('storage_mode',BrianMonitorResult.table_mode)

        assert (self._storage_mode == BrianMonitorResult.table_mode or
                self._storage_mode == BrianMonitorResult.array_mode)

        self._extract_monitor_data(monitor)

        self.set(*args,**kwargs)


    
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
        

    def _extract_van_rossum_metric(self,monitor):
        data_dict ={}
        data_dict['source'] = [str(monitor.source)]

        distance = monitor.distance
        self.set(data=data_dict,distance=distance)


    def _extract_isi_hist_monitor(self,monitor):

        data_dict ={}
        data_dict['source'] = [str(monitor.source)]

        bins = monitor.bins
        count = monitor.count

        self.set(data=data_dict,bins=bins,count=count)

    def _extract_state_spike_monitor(self,monitor):
        data_dict = {}
        data_dict['source'] = [str(monitor.source)]

        varnames = monitor._varnames

        if not isinstance(varnames, tuple) :
            varnames = (varnames,)

        data_dict['varnames'] = [np.array(varnames)]

        record =  monitor.record
        if isinstance(record, list):
            record = np.array(record)

        data_dict['record'] = [record]

        if hasattr(monitor, 'function'):
            data_dict['function'] = [getsource(monitor.function)]

        data_dict['nspikes'] = [monitor.nspikes]

        data_dict['time_unit'] = ['second']



        if self._storage_mode==BrianMonitorResult.table_mode:
            spike_dict={}

            if len(monitor.spikes)>0:
                zip_lists = zip(*monitor.spikes)
                time_list = zip_lists[1]

                nounit_list = [np.float64(time) for time in time_list]

                spike_dict['time'] = nounit_list
                spike_dict['index'] = list(zip_lists[0])

                count = 2
                for varname in varnames:

                    var_list = list(zip_lists[count])
                    data_dict[varname+'_unit'] =  [repr(get_unit(var_list[0]))]
                    nounit_list = [np.float64(var) for var in var_list]
                    spike_dict[varname] = nounit_list
                    count = count +1

                self.set(values=spike_dict)

        elif self._storage_mode==BrianMonitorResult.array_mode:
                for neuron in range(len(monitor.source)):
                    spikes = monitor.times(neuron)
                    if len(spikes)>0:
                        key = 'spikes_n%08d' % neuron
                        self.set(**{key:spikes})

                for varname in varnames:
                     for neuron in range(len(monitor.source)):
                         values = monitor.values(varname,neuron)
                         if len(values)>0:
                             if not varname+'_unit' in data_dict:
                                 data_dict[varname+'_unit'] = [repr(get_unit(values[0]))]
                             key = varname+'_n%08d' % neuron
                             self.set(**{key:values})


        else:
                raise RuntimeError('You shall not pass!')

        self.set(data=data_dict)

     
    def _extrac_spike_monitor(self,monitor):
        
        #assert isinstance(monitor, SpikeMonitor)


        data_dict = {}
        data_dict['source'] = [str(monitor.source)]

        record =  monitor.record
        if isinstance(record, list):
            record = np.array(record)

        data_dict['record'] = [record]
        
        if hasattr(monitor, 'function'):
            data_dict['function'] = [getsource(monitor.function)]
        
        data_dict['nspikes'] = [monitor.nspikes]

        data_dict['time_unit'] = ['second']

        if self._storage_mode==BrianMonitorResult.table_mode:
            spike_dict={}

            if len(monitor.spikes)>0:
                zip_lists = zip(*monitor.spikes)
                time_list = zip_lists[1]

                nounit_list = [np.float64(time) for time in time_list]

                spike_dict['time'] = nounit_list
                spike_dict['index'] = list(zip_lists[0])

                self.set(spikes=spike_dict)

        elif self._storage_mode==BrianMonitorResult.array_mode:
                for neuron, spikes in monitor.spiketimes.items():
                    if len(spikes)>0:
                        key = 'spikes_n%08d' % neuron
                        self.set(**{key:spikes})

        else:
                raise RuntimeError('You shall not pass!')

        self.set(data=data_dict)


    def _extract_population_rate_monitor(self,monitor):
        assert isinstance(monitor, PopulationRateMonitor)
        

        data_dict = {}
        data_dict['source'] = [str(monitor.source)]
        data_dict['time_unit'] = ['second']
        data_dict['rate_unit'] = ['Hz']
        #data_dict['bin'] = [monitor.bin]
        
        ### Store times ###

        times = np.expand_dims(monitor.times,axis=0)

        
        ## Store Rate
        rate = np.expand_dims(monitor.rate,axis=0)

        self.set( times= times, rate=rate)
        self.set(data=data_dict)
        

    def _extract_spike_counter(self,monitor):
        data_dict ={}
        data_dict['nspikes'] = [monitor.nspikes]
        data_dict['source'] = str(monitor.source)

        count_array = np.array(monitor.count)
        self.set(data=data_dict, counts = count_array)


    def _extract_population_spike_counter(self,monitor):
        
        assert isinstance(monitor, PopulationSpikeCounter)
 
        data_dict ={}
        data_dict['nspikes'] = [monitor.nspikes]
        data_dict['source'] = [str(monitor.source)]

        self.set(data=data_dict)

    def _extract_multi_state_monitor(self,monitors):
        data_dict = {}


        data_dict['varnames'] = [np.array(monitors.vars)]



        ### Store times ###
        times = np.expand_dims(monitors.times,axis=0)


        ### Store recorded values ###
        for idx,varname in enumerate(monitors.vars):
            monitor = monitors.monitors[varname]
            if idx == 0:

                record =  monitor.record
                if isinstance(record, list):
                    record = [np.array(record)]

                data_dict['record'] = record
                data_dict['when'] = monitor.when

                data_dict['timestep'] = monitor.timestep

                data_dict['source'] = [str(monitor.P)]

            values = monitor.values

            if len(values) > 0:
                self.set(**{varname+'_values':values})
                if idx==0:
                    self.set(times=times)

            ### Store mean and variance ###
            mean = np.expand_dims(monitor.mean,axis=1)
            variances = np.expand_dims(monitor.var,axis=1)

            combined = np.concatenate((mean,variances),axis=1)

            self.set(**{varname+'_mean_var':combined})

        self.set(data=data_dict)

    def _extract_state_monitor(self,monitor):

        data_dict = {}
        

        data_dict['varname'] = [monitor.varname]
        
        record =  monitor.record
        if isinstance(record, list):
            record = [np.array(record)]
            
        data_dict['record'] = record
        
        data_dict['when'] = monitor.when
        
        data_dict['timestep'] = monitor.timestep

        data_dict['source'] = [str(monitor.P)]
        
        ### Store times ###
        times = np.expand_dims(monitor.times,axis=0)

         
        ### Store mean and variance ###
        mean = np.expand_dims(monitor.mean,axis=1)
        variances = np.expand_dims(monitor.var,axis=1)

        combined = np.concatenate((mean,variances),axis=1)

        
        ### Store recorded values ###
        values = monitor.values

        if len(values) > 0:
            self.set(times=times, values = values)

        self.set(data=data_dict, mean_var=combined)
        
        
            
