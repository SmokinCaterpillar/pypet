'''
Created on 10.06.2013

@author: robert
'''


from mypet.parameter import Parameter, BaseResult, SparseParameter
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


    def set_single(self,name,val,pos=0):
        if BrianParameter.separator in name:
            raise AttributeError('Sorry your entry cannot contain >>%s<< this is reserved for storing brian units and values.' % BrianParameter.separator)

        super(BrianParameter,self).set_single(name,val,pos)

    def _load_data(self, load_dict):

        briandata = {}


        for key, val in load_dict['Data'].items():
            if BrianParameter.separator in key:
                briandata[key] = val
                del load_dict['Data'][key]

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

            load_dict['Data'][brianname] = brianlist

        super(BrianParameter,self)._load_data(load_dict)


    def _store_data(self,store_dict):
        super(BrianParameter,self)._store_data(store_dict)
        data_dict = store_dict['Data']

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

class BrianMonitorResult(BaseResult):  
    
    def __init__(self, fullname, monitor, comment ='No comment'):
        super(BrianMonitorResult,self).__init__(fullname)
        self._comment = comment
        self._monitor = monitor

    
    def __getattr__(self,name):
        if name =='Comment' or name == 'comment':
            return self._comment
        
        raise AttributeError('Result ' + self._name + ' does not have attribute ' + name +'.')
    
    def __setattr__(self,name,value):
        
        if name[0]=='_':
            self.__dict__[name] = value
        elif name == 'Comment' or 'comment':
            self._comment = value
        else:
            raise TypeError('You are not allowed to assign new attributes to %s.' % self._name)
      
    def _string_length_large(self,string):  
        return  int(len(string)+1*1.5)
    

    def _store_meta_data(self,store_dict):

        store_dict['Info'] = {'Name':[self._name],
                   'Location':[self._location],
                   'Comment':[self._comment],
                   'Type':[str(type(self))],
                   'Class_Name': [self.__class__.__name__]}

    
    def __store__(self):
        ## Check for each monitor separately:
        store_dict ={}
        self._store_meta_data(store_dict)
        if isinstance(self._monitor,SpikeMonitor):
            self._store_spike_monitor(store_dict)
        
        elif isinstance(self._monitor, PopulationSpikeCounter):
            self._store_population_spike_counter(store_dict)
        
        elif  isinstance(self._monitor, PopulationRateMonitor):
            self._store_population_rate_monitor(store_dict)
        
        elif isinstance(self._monitor,StateMonitor):
            self._store_state_monitor(store_dict)
            
        else:
            raise ValueError('Monitor Type %s is not supported (yet)' % str(type(self._monitor)))
        
        return store_dict
    
     
    def _store_spike_monitor(self,store_dict):
        
        assert isinstance(self._monitor, SpikeMonitor)

        store_dict['Data'] = {}
        data_dict=store_dict['Data']
        
        record =  self._monitor.record
        if isinstance(record, list):
            record = np.array(record)

        data_dict['record'] = record
        
        if hasattr(self._monitor, 'function'):
            data_dict['function'] = getsource(self._monitor.function)
        
        data_dict['nspikes'] = self._monitor.nspikes

        store_dict['Info']['Time_Unit'] = 'second'

        store_dict['spikes'] = {}
        spike_dict=store_dict['spikes']

        zip_lists = zip(*self._monitor.spikes)
        time_list = zip_lists[1]

        nounit_list = [np.float64(time) for time in time_list]

        spike_dict['time'] = nounit_list
        spike_dict['index'] = list(zip_lists[0])

        
    def _store_population_rate_monitor(self,store_dict):
        assert isinstance(self._monitor, PopulationRateMonitor)
        
        store_dict['Data'] = {}
        data_dict = store_dict['Data']
        data_dict['bin'] = self._monitor.bin
        
        ### Store times ###

        times = np.expand_dims(self._monitor.times,axis=0)
        store_dict['times'] = times

        
        ## Store Rate
        rate = np.expand_dims(self._monitor.rate,axis=0)
        store_dict['rate'] = rate
        
        
    def _store_population_spike_counter(self,store_dict):
        
        assert isinstance(self._monitor, PopulationSpikeCounter)
 
        store_dict['Data'] ={}
        store_dict['Data']['nspikes'] = self._monitor.nspikes
        store_dict['Data']['source'] = str(self._monitor.source)

        
    def _store_state_monitor(self,store_dict):

        store_dict['Data'] ={}
        data_dict = store_dict['Data']
        

        data_dict['varname'] = self._monitor.varname
        
        record =  self._monitor.record
        if isinstance(record, list):
            record = np.array(record)
            
        data_dict['record'] = record
        
        data_dict['when'] = self._monitor.when
        
        data_dict['timestep'] = self._monitor.timestep

        
        
        ### Store times ###
        times = np.expand_dims(self._monitor.times,axis=0)
        store_dict['times'] = times
         
        ### Store mean and variance ###
        mean = np.expand_dims(self._monitor.mean,axis=1)
        variances = np.expand_dims(self._monitor.var,axis=1)

        combined = np.concatenate((mean,variances),axis=1)
        store_dict['mean_var'] = combined
        
        ### Store recorded values ###
        values = self._monitor.values
        store_dict['values']=values

        
        
            
