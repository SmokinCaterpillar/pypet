'''
Created on 17.05.2013

@author: robert
'''
import numpy as np
from parameter import Parameter
import logging
import datetime
import time
import tables as pt
import os

class Trajectory(object):
    '''The trajectory class'''
    
    class TreeNode(object):
        ''' Standard Object to construct the file tree'''
        def store_to_hdf5(self,hdf5file,hdf5group):
            assert isinstance(hdf5file,pt.File)
            assert isinstance(hdf5group, pt.Group)
            
            for key in self.__dict__:
                newhdf5group=hdf5file.createGroup(where=hdf5group, name=key, title=key)
                self.__dict__[key].store_to_hdf5(hdf5file,newhdf5group)
                
        
    
    def __init__(self, name, filename, filetitle='Experiment'):
        self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        self._givenname = name;
        self._name = name+'_'+str(self._time)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)
        self._parameters={}
        self.Parameters = Trajectory.TreeNode()
        self._filename = filename
        
        self._filetitle=filetitle
        
        self._logger.debug('Created the Trajectory ' + self._name)
    
    
    def add_parameter(self, full_parameter_name, value_dict={}, param_type=Parameter):  
        
        assert isinstance(full_parameter_name, str)
        
        assert isinstance(value_dict, dict)
        
        if self._parameters.has_key(full_parameter_name):
            self._logger.warn('Parameter ' + full_parameter_name + ' is already part of trajectory, ignoring the adding.')
            return
        
        tokenized_name = full_parameter_name.split('.')
        
        treetokens = tokenized_name[:-1]
        
        param_name = tokenized_name[-1]
        
        self._parameters[full_parameter_name] = param_type(param_name,full_parameter_name)
        
        act_inst = self.Parameters
        for token in treetokens:
            if not hasattr(act_inst, token):
                act_inst.__dict__[token] = Trajectory.TreeNode()
            act_inst = act_inst.__dict__[token]
        act_inst.__dict__[param_name] = self._parameters[full_parameter_name]
        
        
        self._parameters[full_parameter_name].set(value_dict)
            
    def explore(self,build_function,params): 
        
        build_dict = build_function(params) 
        
        for key, builder in build_dict.items():
            act_param = self._parameters[key]
            act_param.explore(builder)
            
    def lock_parameters(self):
        for key, par in self._parameters.items():
            par.lock()
            
    def store_to_hdf5(self):
        
        self._logger.info('Start storing Parameters.')
        
        (path, filename)=os.path.split(self._filename)
        if not os.path.exists(path):
            os.makedirs(path)
        
        self.lock_parameters()
        
        
        hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)
        
        trajectorygroup = hdf5file.createGroup(where='/', name=self._name, title=self._name)
        
        
        self._store_params(hdf5file,trajectorygroup)
        
        hdf5file.flush()
        
        hdf5file.close()
        self._logger.info('Finished storing Parameters.')
    
    def _store_params(self,hdf5file,trajectorygroup):
        
        paramgroup = hdf5file.createGroup(where=trajectorygroup,name='Parameters', title='Parameters')
        
        self.Parameters.store_to_hdf5(hdf5file, paramgroup)
        
              
        
    
