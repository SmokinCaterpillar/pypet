'''
Created on 10.06.2013

@author: robert
'''


from mypet.parameter import Parameter, BaseResult, SparseParameter, SimpleResult
from brian.units import *
from brian.stdunits import *
from brian.fundamentalunits import Unit, Quantity
from brian.monitor import SpikeMonitor,SpikeCounter,StateMonitor, PopulationSpikeCounter, PopulationRateMonitor
from mypet.utils.helpful_functions import nest_dictionary

from inspect import getsource
import numpy as np

class BrianParameter(SparseParameter):

    separator = '_brian_'

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

    # def _convert_data(self, val):
    #     if isinstance(val, Quantity):
    #         return val
    #
    #     return super(BrianParameter,self)._convert_data(val)


    def set_single(self,name,val):
        if BrianParameter.separator in name:
            raise AttributeError('Sorry your entry cannot contain >>%s<< this is reserved for storing brian units and values.' % BrianParameter.separator)

        super(BrianParameter,self).set_single(name,val)


    def _load_data(self, load_dict):

        data_dict =load_dict['Data']

        self._load_brian_data(data_dict)

        if 'ExploredData' in load_dict:
            explored_dict = load_dict['ExploredData']
            self._load_brian_data(explored_dict)

        super(BrianParameter,self)._load_data(load_dict)

    def _load_brian_data(self, data_dict):

        briandata = {}


        for key, val in data_dict.items():
            if BrianParameter.separator in key:
                briandata[key] = val
                del data_dict[key]

        briandata = nest_dictionary(briandata, BrianParameter.separator)



        for brianname, vd_dict in briandata.items():
            arunit = vd_dict['unit']
            arval = vd_dict['value']

            brianlist = []
            for idx in range(len(arunit)):
                unit = arunit[idx]
                value= arval[idx]
                value = eval(value)
                evalstr = 'value * ' + unit
                brian_quantity = eval(evalstr)
                brianlist.append(brian_quantity)

            data_dict[brianname] = brianlist


    def _store_data(self, store_dict):
        super(BrianParameter,self)._store_data(store_dict)
        data_dict = store_dict['Data']
        self._store_brian_data(data_dict)

        if 'ExploredData' in store_dict:
            explored_dict = store_dict['ExploredData']
            self._load_brian_data(explored_dict)


    def _store_brian_data(self,data_dict):


        for key, val_list in data_dict.items():
            if isinstance(val_list[0],Quantity):
                del data_dict[key]
                data_dict[key+BrianParameter.separator+'unit']=[]
                data_dict[key+BrianParameter.separator+'value']=[]

                for val in val_list:
                    assert isinstance(val, Quantity)
                    valstr = val.in_best_unit(python_code=True)
                    split_val = valstr.split('*')
                    value = split_val.pop(0)
                    unit = '*'.join(split_val)
                    data_dict[key+BrianParameter.separator+'unit'].append(unit)
                    data_dict[key+BrianParameter.separator+'value'].append(value)

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

        spike_dict={}

        if len(monitor.spikes)>0:
            zip_lists = zip(*monitor.spikes)
            time_list = zip_lists[1]

            nounit_list = [np.float64(time) for time in time_list]

            spike_dict['time'] = nounit_list
            spike_dict['index'] = list(zip_lists[0])

            self.set(Spikes=spike_dict)

        self.set(Data=data_dict)

        
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

        
        
            
