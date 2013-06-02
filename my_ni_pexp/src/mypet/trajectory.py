'''
Created on 17.05.2013

@author: robert
'''

import logging
import datetime
import time
import tables as pt
import os
from mypet.parameter import Parameter, BaseParameter
import importlib as imp
import copy
from mypet.configuration import config
import multiprocessing as multip
#from multiprocessing.synchronize import Lock


class TreeNode(object):
        '''Object to construct the file tree.
        
        The recursive structure allows acces to parameters via natural naming.
        '''
        def __init__(self, name, present_working_type='None'):
            self._name = name
            self._pwt = present_working_type
      
            
        def store_to_hdf5(self,hdf5file,hdf5group):
            assert isinstance(hdf5file,pt.File)
            assert isinstance(hdf5group, pt.Group)
            
            for key in self.__dict__:
                if key == '_pwt' or key == '_name':
                    continue;
                newhdf5group=hdf5file.createGroup(where=hdf5group, name=key, title=key)
                self.__dict__[key].store_to_hdf5(hdf5file,newhdf5group)
        
        def __getattr__(self,name):
                       
            if self._name in ['DerivedParameters', 'Results']:
                if name == 'pwt':
                    return self.__dict__[self._pwt]
                else:
                    return self.__dict__[self._pwt].name
             
            raise AttributeError('%s does not have attribute %s' % (self._pwt,name))
            

class Trajectory(object):
    '''The trajectory manages the handling of simulation parameters and results.
    
    :param name: Name of trajectory, the real name is a concatenation of the user specified name and
                the current timestamp, e.g.
                name = MyTrajectory is modified to MyTrajectory_xxY_xxm_xxd_xxh_xxm_xxs
    
    :param filename: The path and filename of the hdf5 file where everything will be stored.
    
    :param filetitle: If the file has to be created, this is added as the filetitle to the hdf5file
                    meta information
                    
    :param dynamicly_imported_classes: If the user has a custom parameter that needs to be loaded
                                      dynamically during runtime, the module containing the class 
                                      needs to be specified here.
                                      For example:
                                      dynamicly_imported_classes=['mypet.parameter.SparseParameter']
                                      (Note that in __init__ the SparseParameter is actually added
                                      to the potentially dynamically loaded classes.)
    
                                      
    As soon as a parameter is added to the trajectory it can be accessed via natural naming:
    >>> traj.add_parameter('paramgroup.param1')
    
    >>> traj.Parameters.paramgroup.param1.entry1 = 42
    
    >>> print traj.Parameters.paramgroup.param1.entry1
    >>> 42
    
    Derived Parameters are stored under the group DerivedParameters.Name_of_trajectory_or_run.
    
    There are several shortcuts implemented. The expression traj.DerivedParameters.pwt
    maps to DerivedParameters.Name_of_current_trajectory_or_run.
    
    If no main group like 'Results','Parameters','DerivedParameters' is specified, 
    like accessing traj.paramgroup.param1
    It is first checked if paramgroup.param1 can be found in the DerivedParameters, if not is looked 
    for in the Parameters. 
    For example, traj.paramgroup.param1 would map to print traj.Parameters.paramgroup.param1                     
    '''
    
    MAX_NAME_LENGTH = 1024
    
    standard_comment = 'Dude, do you not want to tell us your amazing story about this trajectory?'
    
   
    def __len__(self): 
        return self._length      
    
    def __init__(self, name, filename, filetitle='Experiment', dynamicly_imported_classes=[]):
    
        self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        self._givenname = name;
        self._name = name+'_'+str(self._time)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)
        
        self._parameters={}
        self._derivedparameters={}
        self._results={}
        self._exploredparameters={}  
        
        #Even if there are no parameters yet length is 1 for convention
        self._length = 1
        
        self.Parameters = TreeNode('Parameters',self._name)
        self.DerivedParameters = TreeNode('DerivedParameters',self._name)
        self.Results = TreeNode('Results',self._name)
        
        self._filename = filename 
        self._filetitle=filetitle
        self._comment= Trajectory.standard_comment
        
        
        self.last = None
        
        
        self._dynamic_imports=['mypet.parameter.SparseParameter']
        self._dynamic_imports.append(dynamicly_imported_classes)
        
        self._loadedfrom = 'None'
        
    
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        del result['Parameters']
        del result['DerivedParameters']
        del result['Results']
        return result
    
    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        
        self.Parameters = TreeNode('Parameters',self._name)
        self.DerivedParameters = TreeNode('DerivedParameters',self._name)
        self.Results = TreeNode('Results',self._name)
        
        two_dicts = {}
        two_dicts.update(self._parameters)
        two_dicts.update(self._derivedparameters)
        
        for key, val in two_dicts.items():
            self._add_to_tree(val.gfn(), val)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)
        
        
    def get_name(self):  
        return self._name                 
    
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
            
    def adp(self, full_parameter_name, param_type=Parameter,**value_dict):
        return self.add_derived_parameter(full_parameter_name, param_type, **value_dict)
                  
    def add_derived_parameter(self, full_parameter_name, param_type=Parameter,**value_dict):
        
        assert isinstance(full_parameter_name, str)
        
        assert isinstance(value_dict, dict)
        
        full_parameter_name = 'DerivedParameters.' + self._name+'.'+ full_parameter_name
        
        if self._derivedparameters.has_key(full_parameter_name):
            self._logger.warn(full_parameter_name + ' is already part of trajectory, ignoring the adding.')

        param_name = full_parameter_name.split('.')[-1]
        
        instance =   param_type(param_name,full_parameter_name)
        
        if value_dict:
            instance.set(**value_dict)
        
        self._derivedparameters[full_parameter_name] = instance
        
        self._add_to_tree(full_parameter_name, instance)
        
        self.last = instance
        
        return instance

    def ap(self, full_parameter_name, param_type=Parameter, **value_dict):
        return self.add_parameter( full_parameter_name,param_type, **value_dict)
    
    def add_parameter(self, full_parameter_name,  param_type=Parameter, **value_dict):  
        
        assert isinstance(full_parameter_name, str)
        
        assert isinstance(value_dict, dict)
        
        full_parameter_name = 'Parameters.' + full_parameter_name
        
        if self._parameters.has_key(full_parameter_name):
            self._logger.warn(full_parameter_name + ' is already part of trajectory, ignoring the adding.')

        param_name = full_parameter_name.split('.')[-1]
        
        instance =   param_type(param_name,full_parameter_name)
        if value_dict:
            instance.set(**value_dict)
        
        self._parameters[full_parameter_name] = instance
        
        self._add_to_tree(full_parameter_name, instance)
        
        self.last = instance
        
        return instance
        

       
    
    def _add_to_tree(self, where, instance):
        
        tokenized_name = where.split('.')
        
        treetokens = tokenized_name[:-1]
        
        param_name = tokenized_name[-1]

        act_inst = self
        for token in treetokens:
            if not hasattr(act_inst, token):
                act_inst.__dict__[token] = TreeNode(token,self._name)
            act_inst = act_inst.__dict__[token]
        act_inst.__dict__[param_name] = instance
        
        
    def _split_dictionary(self, tosplit_dict):
        result_dict={}
        for param,val in tosplit_dict.items():
            name_data = param.split(".")
            param_name = ".".join(name_data[:-1])
            value_str = name_data[-1]
            
            if not param_name in result_dict:
                result_dict[param_name]={}
            
            result_dict[param_name][value_str] = val
        
        return result_dict     
    
    def explore(self,build_function,*params): 
        
        build_dict = build_function(*params) 
        
        if isinstance(build_dict, tuple):
            build_dict, dummy = build_dict
        
        split_dict = self._split_dictionary(build_dict)   
            
        count = 0#Don't like it but ok
        for key, builder in split_dict.items():
            act_param = self._parameters[key]
            if isinstance(builder, list):
                act_param.explore(*builder)
            elif isinstance(builder,dict):
                act_param.explore(**builder)
            else: raise TypeError('Your parameter exploration function returns something weird.')
            self._exploredparameters[key] = self._parameters[key]
            
            if count == 0:
                self._length = len(self._parameters[key])#Not so nice, but this should always be the same numbert
            else:
                if not self._length == len(self._parameters[key]):
                    raise ValueError('The Parameters to explore have not the same size!')
       
            
        
            
    def lock_parameters(self):
        for key, par in self._parameters.items():
            par.lock()
    
    def lock_derived_parameters(self):
        for key, par in self._derivedparameters.items():
            par.lock()
            
    def _store_meta_data(self,hdf5file,trajectorygroup):
        
        assert isinstance(hdf5file,pt.File)
        
        loaddict = {'Trajectory' : pt.StringCol(self.MAX_NAME_LENGTH),
                    'Filename' : pt.StringCol(self.MAX_NAME_LENGTH)}
        
        descriptiondict={'Name': pt.StringCol(len(self._name)), 
                         'Timestamp': pt.StringCol(len(self._time)),
                         'Comment': pt.StringCol(len(self._comment)),
                         'Length':pt.IntCol(),
                         'Loaded_From': loaddict.copy()}
        
        infotable = hdf5file.createTable(where=trajectorygroup, name='Info', description=descriptiondict, title='Info')
        newrow = infotable.row
        newrow['Name']=self._name
        newrow['Timestamp']=self._time
        newrow['Comment']=self._comment
        newrow['Length'] = self._length
        newrow['Loaded_From/Trajectory']=self._loadedfrom[0]
        newrow['Loaded_From/Filename']=self._loadedfrom[1]
        
        newrow.append()
        infotable.flush()
        
        
        tostore_dict =  {'ParameterTable':self._parameters, 'DerivedParameterTable':self._derivedparameters, 'ExploredParameterTable' :self._exploredparameters}
        
        for key, dictionary in tostore_dict.items():
            
            paramdescriptiondict={'Full_Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                  'Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                  'Class_Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                  'Size' : pt.IntCol()}
            
            if key in ['DerivedParameterTable', 'Results']:
                paramdescriptiondict.update({'Creator_Name':pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                             'Creator_ID':pt.IntCol()})
            
            paramtable = hdf5file.createTable(where=trajectorygroup, name=key, description=paramdescriptiondict, title=key)
            
            self._store_single_table(dictionary, paramtable, self._name,-1)
    
    def _store_single_table(self,paramdict,paramtable, creator_name, creator_id):
                                 
            assert isinstance(paramtable, pt.Table)    


            newrow = paramtable.row
            for key, val in paramdict.items():
                newrow['Full_Name'] = key
                newrow['Name'] = val.get_name()[0]
                newrow['Class_Name'] = val.get_class_name()
                newrow['Size'] = len(val)
                
                if key in ['DerivedParameterTable', 'Results']:
                    newrow['Creator_Name'] = creatorname
                    newrow['Creator_ID'] = id
                    
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
            
            if len(paraminstance>1):
                self._exploredparameters[fullname] = paraminstance
            
            self._add_to_tree(fullname, paraminstance)
                
    def _load_meta_data(self,trajectorygroup): 
        
        
        metatable = trajectorygroup.Info
        metarow = metatable[0]
        
        self._length = metarow['Length']
        self.add_comment(metarow['Comment'])
    
    def store_single_run(self,trajectory_name,n):  

            
        hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)
        
        trajectorygroup = hdf5file.getNode(where='/', name=trajectory_name)
        
        self.DerivedParameters.store_to_hdf5(hdf5file, trajectorygroup.DerivedParameters) 
        
        paramtable = getattr(trajectorygroup, 'DerivedParameterTable')
        self._store_single_table(self._derivedparameters, paramtable, trajectory_name,n)
        
        hdf5file.flush()
        hdf5file.close()
    
                
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
    
    def get_paramspacepoint(self,n):
        
        newtraj = copy.copy(self)
        
        assert isinstance(newtraj, Trajectory) #Just for autocompletion
        
        #Do not copy the results, this is way too much in case of multiprocessing
        if config['multiproc']:
            newtraj.Results = TreeNode('Results',self._name)
            
        # extract only one particular paramspacepoint
        for key,val in newtraj._exploredparameters.items():
            assert isinstance(val, BaseParameter)
            newparam = val.access_parameter(n)
            newtraj._exploredparameters[key] = newparam
            if key in newtraj._parameters:
                newtraj._parameters[key] = newparam
            if key in newtraj._derivedparameters:
                newtraj._derivedparameters[key] = newparam
            self._add_to_tree(key, newparam)
            
        
        return newtraj 
    
        
        
        
    def prepare_experiment(self):
        self.lock_parameters()
        self.lock_derived_parameters()
        self.store_to_hdf5()

     
    def make_single_run(self,n):  
        return SingleRun(self._filename, self, n) 
    
    def __getattr__(self,name):
        
        if not hasattr(self, 'Parameters') or not hasattr(self, 'DerivedParameters'):
            raise AttributeError('This is to avoid pickling issues!')
     

        if name in self.DerivedParameters.__dict__:
            return self.DerivedParameters.__dict__[name]
        elif name in self.Parameters.__dict__:
            return self.Parameters.__dict__[name]
        
        raise AttributeError('Trajectory does not contain %s' % name)

    def multiproc(self):
        return self._multiproc

class SingleRun(object):
    
    def __init__(self, filename, parent_trajectory,  n):
        
        assert isinstance(parent_trajectory, Trajectory)

        self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%Hh%Mm%Ss')

        self._n = n
        self._filename = filename 
        
        name = 'Run_No_%08d' % n
        self._small_parent_trajectory = parent_trajectory.get_paramspacepoint(n)
        self._single_run = Trajectory(name=name, filename=filename)
        
        self._logger = logging.getLogger('mypet.trajectory.SingleRun=' + self._single_run.get_name())
        
            
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        return result
    
    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.trajectory.SingleRun=' + self._single_run.get_name())
        #self._logger = multip.get_logger()
        
    def add_derived_parameter(self, full_parameter_name,  param_type=Parameter, **value_dict):
        self._single_run.add_derived_parameter(full_parameter_name, param_type, **value_dict)

    
    def add_parameter(self, full_parameter_name, param_type=Parameter, **value_dict):  
        self._logger.warn('Cannot add Parameters anymore, yet I will add a derived Parameter.')
        self.add_derived_parameter(full_parameter_name, param_type, **value_dict)
       
    def __getattr__(self,name):
        
        if not hasattr(self, '_small_parent_trajectory') or not hasattr(self, '_single_run'):
            raise AttributeError('This is to avoid pickling issues!')
        
        if name == 'pt' or name == 'ParentTrajectory':
            return self._small_parent_trajectory
        
        try:
            return getattr(self._single_run,name)
        except Exception:
            return getattr(self._small_parent_trajectory,(name))
    
    
    def store_to_hdf5(self, lock=None):
        if lock:
            lock.acquire()
            #print 'Start storing run %d.' % self._n
            self._logger.debug('Start storing run %d.' % self._n)
            
        self._single_run.store_single_run(self._small_parent_trajectory.get_name(), self._n)
        
        if lock:
            #print 'Finished storing run %d,' % self._n
            self._logger.debug('Finished storing run %d,' % self._n)
            lock.release()

