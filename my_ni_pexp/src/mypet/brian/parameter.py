'''
Created on 10.06.2013

@author: robert
'''


from mypet.parameter import Parameter, BaseResult
from brian.units import *
from brian.stdunits import *
from brian.fundamentalunits import Unit, Quantity
from brian.monitor import SpikeMonitor,SpikeCounter,StateMonitor, PopulationSpikeCounter, PopulationRateMonitor
from inspect import getsource

import tables as pt
import numpy as np

class BrianParameter(Parameter):
    ''' The standard Brian Parameter that has a value and a unit
    
    The unit has to be set via param.unit = unit,
    e.g.
    >>> param.unit = mV
    
    the corresponding value is set as
    >>> param.value = 10
    
    If both have been specified
    a call to the param returns the corresponding brian quantity:
    >>> print param()
    >>> 10*mvolt
    
    The brian quantity can also be accessed via param.val
    
    '''
    def __init__(self,name,location,*value_list,**value_dict):
        value_list = list(value_list)
        unit = None
        
        if value_list and isinstance(value_list[0],Quantity):
            unit = value_list.pop(0)
    
        super(BrianParameter,self).__init__(name,location,*value_list,**value_dict)
    
        if unit:
            self._add_brian_quantity(unit)
            
    
    def _add_brian_quantity(self,unit):
        assert isinstance(unit, Quantity)
        unitstr = unit.in_best_unit(python_code=True)
        
        splitunit = unitstr.split('*')
        value = splitunit.pop(0)
        self.value=float(value)
        unit = '*'.join(splitunit)
        self.unit = unit
        
       

    def __call__(self,valuename=None):
        if not valuename or valuename == 'val':
            if not self.has_value('unit') or  not self.has_value('value'):
                self._logger.info('Brian Parameter has no unit or value.')
                return None
            unit = eval(self.unit)
            value = self.value
            return value*unit   
        else:
            super(BrianParameter,self).__call__(valuename)
            
    def get(self, name):
        
        if name == 'val':
            return self()
            
        return super(BrianParameter,self).get(name)
    
    def _set_single(self,name,val):
        
        if name == 'val' and isinstance(val, Quantity):
            self._add_brian_quantity(val)
            return 
        
        ## Check if unit exists
        if name == 'unit':
            unit = eval(val)
            if not isinstance(unit, Unit):
                raise ValueError('Not a unit!')
        
        super(BrianParameter,self)._set_single(name,val)


class BrianMonitorResult(BaseResult):  
    
    def __init__(self, name, location, parent_trajectory_name, filename, monitor, comment =''): 


        self._comment = comment
        self._monitor = monitor
        
        super(BrianMonitorResult,self).__init__(name,location,parent_trajectory_name,filename)
    
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
            raise AttributeError('You are not allowed to assign new attributes to %s.' % self._name)
      
    def _string_length_large(self,string):  
        return  int(len(string)+1*1.5)
    
    def _store_information(self,hdf5file,hdf5group):
        infodict= {'Name':pt.StringCol(self._string_length_large(self._name)), 
                   'Location': pt.StringCol(self._string_length_large(self._location)), 
                   'Comment':pt.StringCol(self._string_length_large(self._comment)),
                   'Type':pt.StringCol(self._string_length_large(str(type(self)))),
                   'Class_Name': pt.StringCol(self._string_length_large(self.__class__.__name__)),
                   'Monitor_Type':pt.StringCol(self._string_length_large(self._monitor.__class__.__name__))}
        
        infotable=hdf5file.createTable(where=hdf5group, name='Info', description=infodict, title='Info')
        
        newrow = infotable.row
        newrow['Name'] = self._name
        newrow['Location'] = self._location
        newrow['Comment'] = self._comment
        newrow['Type'] = str(type(self))
        newrow['Class_Name'] = self.__class__.__name__
        newrow['Monitor_Type'] = self._monitor.__class__.__name__
        
        newrow.append()
        
        infotable.flush()
    
    def store_to_hdf5(self, hdf5file, hdf5group):
        ## Check for each monitor separately:
        if isinstance(self._monitor,SpikeMonitor):
            self._store_spike_monitor(hdf5file,hdf5group)
        
        elif isinstance(self._monitor, PopulationSpikeCounter):
            self._store_population_spike_counter(hdf5file,hdf5group)
        
        elif  isinstance(self._monitor, PopulationRateMonitor):
            self._store_population_rate_monitor(hdf5file,hdf5group)
        
        elif isinstance(self._monitor,StateMonitor):
            self._store_state_monitor(hdf5file,hdf5group)
            
        else:
            raise ValueError('Monitor Type %s is not supported (yet)' % str(type(self._monitor)))
        
        self._store_information(hdf5file, hdf5group)
    
     
    def _store_spike_monitor(self,hdf5file, hdf5group):
        
        assert isinstance(self._monitor, SpikeMonitor)
         
        store_param = Parameter(name='monitor_data', location='')
        store_param.source = str(self._monitor.source)
        
        record =  self._monitor.record
        if isinstance(record, list):
            record = np.array(record)
            
        store_param.record = record
        
        if hasattr(self._monitor, 'function'):
            store_param.function = getsource(self._monitor.function)
        
        store_param.nspikes = self._monitor.nspikes
        store_param.store_data(hdf5file, hdf5group)
        
        neuron_param = Parameter(name='spike_data', location='')
        neuron_param.time = self._monitor.spikes[0][1]
        neuron_param.index = self._monitor.spikes[0][0]
        
        result_list = []
        for neuron_spike in self._monitor.spikes[1:]:
            temp_dict ={}
            temp_dict['time'] = neuron_spike[1]
            temp_dict['index'] = neuron_spike[0]
            result_list.append(temp_dict)
        
        neuron_param.become_array()
        neuron_param.add_items_as_list(result_list)
        
        neuron_param.store_data(hdf5file, hdf5group)
        
    def _store_population_rate_monitor(self,hdf5file,hdf5group):
        assert isinstance(self._monitor, PopulationRateMonitor)
        assert isinstance(hdf5file,pt.File)
        
        store_param =  Parameter(name='monitor_data', location='')
        store_param.bin = self._monitor.bin
        
        ### Store times ###
        times = np.expand_dims(self._monitor.times,axis=0)
        atom = pt.Atom.from_dtype(times.dtype)
        carray=hdf5file.createCArray(where=hdf5group, name='times',atom=atom,shape=times.shape)
        carray[:]=times
        hdf5file.flush()
        
        ## Store Rate
        rate = np.expand_dims(self._monitor.rate,axis=0)
        atom = pt.Atom.from_dtype(rate.dtype)
        carray=hdf5file.createCArray(where=hdf5group, name='rate',atom=atom,shape=rate.shape)
        carray[:]=rate
        hdf5file.flush()
        
        
    def _store_population_spike_counter(self,hdf5file,hdf5group):
        
        assert isinstance(self._monitor, PopulationSpikeCounter)
 
        store_param = Parameter(name='monitor_data', location='')
        store_param.nspikes = self._monitor.nspikes
        store_param.source = str(self._monitor.source)
        
        store_param.store_to_hdf5(hdf5file, hdf5group)
        
    def _store_state_monitor(self,hdf5file, hdf5group):
        
        assert isinstance(self._monitor, StateMonitor)
        assert isinstance(hdf5file,pt.File)
        
        store_param =  Parameter(name='monitor_data', location='')
        store_param.varname = self._monitor.varname
        
        record =  self._monitor.record
        if isinstance(record, list):
            record = np.array(record)
            
        store_param.record = record
        
        store_param.when = self._monitor.when
        
        store_param.timestep = self._monitor.timestep
        
        store_param.store_data(hdf5file, hdf5group)
        
        
        ### Store times ###
        times = np.expand_dims(self._monitor.times,axis=0)
        atom = pt.Atom.from_dtype(times.dtype)
        carray=hdf5file.createCArray(where=hdf5group, name='times',atom=atom,shape=times.shape)
        carray[:]=times
        hdf5file.flush()
         
        ### Store mean and variance ###
        mean = np.expand_dims(self._monitor.mean,axis=1)
        variances = np.expand_dims(self._monitor.var,axis=1)

        combined = np.concatenate((mean,variances),axis=1)
        carray=hdf5file.createCArray(where=hdf5group, name='mean_variance',atom=atom,shape=combined.shape)
        carray[:]=combined
        hdf5file.flush()
        
        ### Store recorded values ###
        values = self._monitor.values
        atom = pt.Atom.from_dtype(values.dtype)
        carray=hdf5file.createCArray(where=hdf5group, name='values',atom=atom,shape=values.shape)
        carray[:]=values
        hdf5file.flush()
        
        
            
