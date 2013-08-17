'''
Created on 10.06.2013

@author: robert
'''


from mypet.parameter import Parameter, BaseResult, SimpleResult,ObjectTable
from brian.units import *
from brian.stdunits import *
from brian.fundamentalunits import Unit, Quantity
from brian.monitor import SpikeMonitor,SpikeCounter,StateMonitor, PopulationSpikeCounter, PopulationRateMonitor
from mypet.utils.helpful_functions import nest_dictionary

from inspect import getsource
import numpy as np



class BrianParameter(Parameter):

    identifier = '__brn__'

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
            valstr = self._data.in_best_unit(python_code=True)
            store_dict['Data'] = ObjectTable(data={'data'+BrianParameter.identifier:[valstr]})


            if self.is_array():
                valstr_list = []
                for val in self._explored_data:
                    valstr = val.in_best_unit(python_code=True)
                    valstr_list.append(valstr)


                store_dict['ExploredData'] = ObjectTable(data={'data'+BrianParameter.identifier:valstr_list})

            return store_dict
        else:
            return super(BrianParameter,self).__store__()


    def __load__(self,load_dict):
        data_table = load_dict['Data']
        data_name = data_table.columns.tolist()[0]
        if BrianParameter.identifier in data_name:
            valstr = data_table['data'+BrianParameter.identifier][0]

            self._data = eval(valstr)

            if 'ExploredData' in load_dict:
                explore_table = load_dict['ExploredData']

                valstr_col = explore_table['data'+BrianParameter.identifier]
                explore_list = []
                for valstr in valstr_col:
                    brian_quantity = eval(valstr)
                    explore_list.append(brian_quantity)

                self._explored_data=tuple(explore_list)
        else:
            super(BrianParameter,self).__load__(load_dict)



class BrianMonitorResult(SimpleResult):
    
    def __init__(self, fullname, monitor, *args, **kwargs):
        super(BrianMonitorResult,self).__init__(fullname)

        self._extract_monitor_data(monitor)

        self.set(*args,**kwargs)


    
    def _extract_monitor_data(self,monitor):
        ## Check for each monitor separately:

        if isinstance(monitor,SpikeMonitor):
            self._extrac_spike_monitor(monitor)
        
        elif isinstance(monitor, PopulationSpikeCounter):
            self._extract_population_spike_counter(monitor)
        
        elif  isinstance(monitor, PopulationRateMonitor):
            self._extract_population_rate_monitor(monitor)
        
        elif isinstance(monitor,StateMonitor):
            self._extract_state_monitor(monitor)
            
        else:
            raise ValueError('Monitor Type %s is not supported (yet)' % str(type(monitor)))
        

     
    def _extrac_spike_monitor(self,monitor):
        
        #assert isinstance(monitor, SpikeMonitor)


        data_dict = {}

        record =  monitor.record
        if isinstance(record, list):
            record = np.array(record)

        data_dict['record'] = [record]
        
        if hasattr(monitor, 'function'):
            data_dict['function'] = [getsource(monitor.function)]
        
        data_dict['nspikes'] = [monitor.nspikes]

        data_dict['Time_Unit'] = ['second']

        data_table = ObjectTable(data=data_dict)

        spike_dict={}

        if len(monitor.spikes)>0:
            zip_lists = zip(*monitor.spikes)
            time_list = zip_lists[1]

            nounit_list = [np.float64(time) for time in time_list]

            spike_dict['time'] = nounit_list
            spike_dict['index'] = list(zip_lists[0])

            spike_table = ObjectTable(data=spike_dict)
            self.set(spikes=spike_dict)

        self.set(Data=data_table)

        
    def _extract_population_rate_monitor(self,monitor):
        assert isinstance(monitor, PopulationRateMonitor)
        

        data_dict = {}
        data_dict['bin'] = [monitor.bin]
        
        ### Store times ###

        times = np.expand_dims(monitor.times,axis=0)

        
        ## Store Rate
        rate = np.expand_dims(monitor.rate,axis=0)

        self.set(Data = data_dict, Times= times, Rate=rate)
        
        
    def _extract_population_spike_counter(self,monitor):
        
        assert isinstance(monitor, PopulationSpikeCounter)
 
        data_dict ={}
        data_dict['nspikes'] = [monitor.nspikes]
        data_dict['source'] = str(monitor.source)

        self.set(Data=data_dict)

        
    def _extract_state_monitor(self,monitor):

        data_dict = {}
        

        data_dict['varname'] = [monitor.varname]
        
        record =  monitor.record
        if isinstance(record, list):
            record = np.array(record)
            
        data_dict['record'] = record
        
        data_dict['when'] = monitor.when
        
        data_dict['timestep'] = monitor.timestep

        
        
        ### Store times ###
        times = np.expand_dims(monitor.times,axis=0)

         
        ### Store mean and variance ###
        mean = np.expand_dims(monitor.mean,axis=1)
        variances = np.expand_dims(monitor.var,axis=1)

        combined = np.concatenate((mean,variances),axis=1)

        
        ### Store recorded values ###
        values = monitor.values

        self.set(Data=data_dict, Times=times, Mean_Var=combined, Values = values)

        
        
            
