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
    
    MAX_NAME_LENGTH = 1024
    
    standard_comment = 'Dude, do you not want to tell us your amazing story about this trajectory?'
    
    class TreeNode(object):
        ''' Standard Object to construct the file tree'''
        def store_to_hdf5(self,hdf5file,hdf5group):
            assert isinstance(hdf5file,pt.File)
            assert isinstance(hdf5group, pt.Group)
            
            for key in self.__dict__:
                newhdf5group=hdf5file.createGroup(where=hdf5group, name=key, title=key)
                self.__dict__[key].store_to_hdf5(hdf5file,newhdf5group)
     
    
    def add_comment(self,comment):
        ''' Extends the existing comment
        :param comment: The comment as string which is added to the existing comment'''
        if self._comment == Trajectory.standard_comment:
            self._comment = comment
        else:
            self._comment = self._comment + '; ' + comment
                  
        
    
    def __init__(self, name, filename, filetitle='Experiment'):
        self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        self._givenname = name;
        self._name = name+'_'+str(self._time)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)
        self._parameters={}
        self.Parameters = Trajectory.TreeNode()
        self._filename = filename
        
        self._filetitle=filetitle
        
        self._comment= Trajectory.standard_comment
        
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
    
#     def _get_longest_name(self):
#         maxlength= 0
#         for key in self._parameters.iterkeys():
#             maxlength = max(maxlength,len(key))
#         return maxlength
            
    def _store_meta_data(self,hdf5file,trajectorygroup):
        
        assert isinstance(hdf5file,pt.File)
        
        descriptiondict={'Name': pt.StringCol(len(self._name)), 
                         'Timestamp': pt.StringCol(len(self._time)),
                         'Comment': pt.StringCol(len(self._comment))}
        
        infotable = hdf5file.createTable(where=trajectorygroup, name='Info', description=descriptiondict, title='Info')
        newrow = infotable.row()
        newrow['Name']=self._name
        newrow['Timestamp']=self._time
        newrow['Comment']=self._comment
        newrow.append()
        infotable.flush()
        
        
        name_length = self._get_longest_name()
        
        paramdescriptiondict={'Full_Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                              'Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                              'Constructor': pt.StringCol(Trajectory.MAX_NAME_LENGTH)}
        
        paramtable = hdf5file.createArray(where=trajectorygroup, name='ParameterTable', description=paramdescriptiondict, title='ParameterTable')
        
        newrow = paramtable.row()
        for key, val in self._parameters#ToDo!!!!!!!!!!!!!!!!!!!
        
        
                
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
        
              
        
    
