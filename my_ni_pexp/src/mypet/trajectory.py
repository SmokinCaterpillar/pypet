'''
Created on 17.05.2013

@author: robert
'''
import numpy as np
from parameter import *
import logging
import datetime
import time

class Trajectory(object):
    '''The trajectory class'''
    
    class TreeNode(object):
        ''' Standard Object to construct the file tree'''
        pass
        
    
    def __init__(self, name):
        self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H:%M:%S')
        self._givenname = name;
        self._name = name+'_'+str(self._time)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)
        self._parameters={}
        self.Parameters = Trajectory.TreeNode()
        
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
            
                
        
    
