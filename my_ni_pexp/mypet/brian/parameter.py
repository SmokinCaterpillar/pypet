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

import tables as pt
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

    def _convert_data(self, val):
        if isinstance(val, Quantity):
            return val

        return super(BrianParameter,self)._convert_data(val)


    def set_single(self,name,val,pos=0):
        if BrianParameter.separator in name:
            raise AttributeError('Sorry your entry cannot contain >>%s<< this is reserved for storing brian units and values.' % BrianParameter.separator)

        super(BrianParameter,self).set_single(name,val,pos)

    def _load_data(self, load_dict):

        briandata = {}


        for key, val in load_dict[self._name].items():
            if BrianParameter.separator in key:
                briandata[key] = val
                del load_dict[self._name][key]

        briandata = nest_dictionary(briandata, BrianParameter.separator)



        for brianname, vd_dict in briandata.items():
            arunit = vd_dict['unit']
            arval = vd_dict['value']

            brianlist = []
            for idx in range(len(arunit)):
                unit = arunit[idx]
                value= arval[idx]
                evalstr = 'value * ' + unit
                brian_quantity = eval(evalstr)
                brianlist.append(brian_quantity)

            load_dict[self._name][brianname] = brianlist

        super(BrianParameter,self)._load_data(load_dict)


    def _store_data(self,store_dict):
        super(SparseParameter,self)._store_data(store_dict)
        data_dict = store_dict[self._name]

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
        self.val = None

    
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
        
        
            
