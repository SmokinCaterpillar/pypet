'''
Created on 17.05.2013

@author: robert
'''
import numpy as np
import logging
import datetime
import time
import tables as pt
import os
from numpy.core.numeric import empty
from mypet.parameter import Parameter, BaseParameter
import importlib as imp

class Trajectory(object):
    '''The trajectory class'''
    
    MAX_NAME_LENGTH = 1024
    
    standard_comment = 'Dude, do you not want to tell us your amazing story about this trajectory?'
    
    class TreeNode(object):
        ''' Standard Object to construct the file tree'''
        def __init__(self, present_wokring_type='Trajectory'):
            self._pwt = present_wokring_type
            
        def store_to_hdf5(self,hdf5file,hdf5group):
            assert isinstance(hdf5file,pt.File)
            assert isinstance(hdf5group, pt.Group)
            
            for key in self.__dict__:
                if key == '_pwt':
                    continue;
                newhdf5group=hdf5file.createGroup(where=hdf5group, name=key, title=key)
                self.__dict__[key].store_to_hdf5(hdf5file,newhdf5group)
        
        def __getattr__(self,name):
            if name == 'pwt':
                return self.__dict__[self._pwt]
            
            raise AttributeError('Trajectory does not have attribute ' + name +'.')
            
     

    
    def __init__(self, name, filename, filetitle='Experiment', dynamicly_imported_classes=[]):
    
        self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        self._givenname = name;
        self._name = name+'_'+str(self._time)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)
        
        self._parameters={}
        self._derivedparameters={}
        self._results={}
        
        self.Parameters = Trajectory.TreeNode()
        self.DerivedParameters = Trajectory.TreeNode()
        self.Results = Trajectory.TreeNode()
        
        self._filename = filename 
        self._filetitle=filetitle
        self._comment= Trajectory.standard_comment
        
        
        self._dynamic_imports=['mypet.parameter.SparseParameter']
        self._dynamic_imports.append(dynamicly_imported_classes)
        
        self._loadedfrom = 'None'
        
        
        
#         try:
#             for key, importlist in dynamic_imports.items():
#                 if not importlist:
#                     execstring = 'from ' + key + ' import *'
#                     exec execstring in globals()
#                 else:
#                     for imp in importlist:
#                         execstring = 'from ' + key + ' import ' + imp
#                         exec execstring in globals()
#         except ImportError:
#             self._logger.error('Failed importing from ' + key +'.')
                
    
    def _load_class(self,full_class_string):
        """
        dynamically load a class from a string
        """
    
        class_data = full_class_string.split(".")
        module_path = ".".join(class_data[:-1])
        class_str = class_data[-1]
    
        module = imp.import_module(module_path)
        # Finally, we retrieve the Class
        return getattr(module, class_str)


        
            
       
    def add_comment(self,comment):
        ''' Extends the existing comment
        :param comment: The comment as string which is added to the existing comment'''
        if self._comment == Trajectory.standard_comment:
            self._comment = comment
        else:
            self._comment = self._comment + '; ' + comment
                  
               
    def add_derived_parameter(self, full_parameter_name, value_dict={}, param_type=Parameter):
        assert isinstance(full_parameter_name, str)
        
        assert isinstance(value_dict, dict)
        
        full_parameter_name = 'DerivedParameters.Trajectory.'+ full_parameter_name
        
        if self._derivedparameters.has_key(full_parameter_name):
            self._logger.warn(full_parameter_name + ' is already part of trajectory, ignoring the adding.')

        param_name = full_parameter_name.split('.')[-1]
        
        instance =   param_type(param_name,full_parameter_name)
        
        instance.set(value_dict)
        
        self._derivedparameters[full_parameter_name] = instance
        
        self._add_to_tree(full_parameter_name, instance)

    
    def add_parameter(self, full_parameter_name, value_dict={}, param_type=Parameter):  
        
        assert isinstance(full_parameter_name, str)
        
        assert isinstance(value_dict, dict)
        
        full_parameter_name = 'Parameters.' + full_parameter_name
        
        if self._parameters.has_key(full_parameter_name):
            self._logger.warn(full_parameter_name + ' is already part of trajectory, ignoring the adding.')

        param_name = full_parameter_name.split('.')[-1]
        
        instance =   param_type(param_name,full_parameter_name)
        
        instance.set(value_dict)
        
        self._parameters[full_parameter_name] = instance
        
        self._add_to_tree(full_parameter_name, instance)
       
    
    def _add_to_tree(self, where, instance):
        
        tokenized_name = where.split('.')
        
        treetokens = tokenized_name[:-1]
        
        param_name = tokenized_name[-1]

        act_inst = self
        for token in treetokens:
            if not hasattr(act_inst, token):
                act_inst.__dict__[token] = Trajectory.TreeNode()
            act_inst = act_inst.__dict__[token]
        act_inst.__dict__[param_name] = instance
        
        
        
            
    def explore(self,build_function,params): 
        
        build_dict = build_function(params) 
        
        for key, builder in build_dict.items():
            act_param = self._parameters[key]
            act_param.explore(builder)
            
    def lock_parameters(self):
        for key, par in self._parameters.items():
            par.lock()
    
            
    def _store_meta_data(self,hdf5file,trajectorygroup):
        
        assert isinstance(hdf5file,pt.File)
        
        loaddict = {'Trajectory' : pt.StringCol(self.MAX_NAME_LENGTH),
                    'Filename' : pt.StringCol(self.MAX_NAME_LENGTH)}
        
        descriptiondict={'Name': pt.StringCol(len(self._name)), 
                         'Timestamp': pt.StringCol(len(self._time)),
                         'Comment': pt.StringCol(len(self._comment)),
                         'Loaded_From': loaddict.copy()}
        
        infotable = hdf5file.createTable(where=trajectorygroup, name='Info', description=descriptiondict, title='Info')
        newrow = infotable.row
        newrow['Name']=self._name
        newrow['Timestamp']=self._time
        newrow['Comment']=self._comment
        newrow['Loaded_From/Trajectory']=self._loadedfrom[0]
        newrow['Loaded_From/Filename']=self._loadedfrom[1]
        
        newrow.append()
        infotable.flush()
        
        
        tostore_dict =  {'ParameterTable':self._parameters, 'DerivedParameterTable':self._derivedparameters}
        for key, dictionary in tostore_dict.items():
            
            paramdescriptiondict={'Full_Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                  'Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                  'Class_Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH)}
            
            paramtable = hdf5file.createTable(where=trajectorygroup, name=key, description=paramdescriptiondict, title=key)
            
            newrow = paramtable.row
            for key, val in dictionary.items():
                newrow['Full_Name'] = key
                newrow['Name'] = val.get_name()[0]
                newrow['Class_Name'] = val.get_class_name()
                newrow.append()
            
            paramtable.flush()
        
    def load_trajectory(self, trajectoryname, filename = None, load_derived_params = True, load_results = True):  
        
        
        
        if filename:
            openfilename = filename
        else:
            openfilename = self._filename
            
        self._loadedfrom = (trajectoryname,os.path.abspath(openfilename))
            
        if not os.path.isfile(openfilename):
            raise AttributeError('Filename ' + openfilename + ' does not exist.')
        
        hdf5file = pt.openFile(filename=openfilename, mode='r')
    
            
        try:
            trajectorygroup = hdf5file.getNode(where='/', name=trajectoryname)
        except Exception:
            raise AttributeError('Trajectory ' + trajectoryname + ' does not exist.')
                
        self._load_meta_data(trajectorygroup)
        self._load_params(trajectorygroup)
        if load_derived_params:
            self._load_derived_params(trajectorygroup)
        if load_results:
            self._load_results(trajectorygroup)
    
    def _load_results(self,trajectorygroup):
        pass #TODO: Write that bitch
        
    def _create_class(self,class_name):
        try:
            new_class = eval(class_name)
            return new_class
        except Exception:
                for dynamic_class in self._dynamic_imports:
                    if class_name in dynamic_class:
                        new_class = self._load_class(dynamic_class)
                        return new_class 
                raise ImportError('Could not create the class named ' + class_name)
    
    def _load_params(self,trajectorygroup):
        paramtable = trajectorygroup.ParameterTable
        self._load_any_param(paramtable,trajectorygroup)
        
    def _load_derived_params(self,trajectorygroup):
        paramtable = trajectorygroup.DerivedParameterTable
        self._load_any_param(paramtable,trajectorygroup)
        
    def _load_any_param(self,paramtable,trajectorygroup):
        assert isinstance(paramtable,pt.Table)
        
        for row in paramtable.iterrows():
            fullname = row['Full_Name']
            name = row['Name']
            class_name = row['Class_Name']
            if fullname in self._parameters:
                self._logger.warn('Paremeter ' + fullname + ' is already in your trajectory, I am overwriting it.')
                del self._parameters[fullname]
                continue
                           
            new_class = self._create_class(class_name)    
            
            paraminstance = new_class(name,fullname)
            
            where = 'trajectorygroup.' + fullname
            paramgroup = eval(where)
            
            assert isinstance(paraminstance, BaseParameter)
            paraminstance.load_from_hdf5(paramgroup)
            
            self._parameters[fullname]=paraminstance
            
            self._add_to_tree(fullname, paraminstance)
                
    def _load_meta_data(self,trajectorygroup): 
        
        
        metatable = trajectorygroup.Info
        metarow = metatable[0]
        
        self.add_comment(metarow['Comment'])
      
                
    def store_to_hdf5(self):
        
        self._logger.info('Start storing Parameters.')
        
        (path, filename)=os.path.split(self._filename)
        if not os.path.exists(path):
            os.makedirs(path)
        
        self.lock_parameters()
        
        
        hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)
        
        trajectorygroup = hdf5file.createGroup(where='/', name=self._name, title=self._name)
        
        self._store_meta_data(hdf5file, trajectorygroup)
        self._store_params(hdf5file,trajectorygroup)
        self._store_derived_params(hdf5file, trajectorygroup)
        
        hdf5file.flush()
        
        hdf5file.close()
        self._logger.info('Finished storing Parameters.')
    
    
    def _store_params(self,hdf5file,trajectorygroup):
        
        paramgroup = hdf5file.createGroup(where=trajectorygroup,name='Parameters', title='Parameters')
        
        self.Parameters.store_to_hdf5(hdf5file, paramgroup)
        
        
    def _store_derived_params(self,hdf5file,trajectorygroup):   
        
        paramgroup = hdf5file.createGroup(where=trajectorygroup,name='DerivedParameters', title='DerivedParameters')
        
        self.DerivedParameters.store_to_hdf5(hdf5file, paramgroup)      
        
    
