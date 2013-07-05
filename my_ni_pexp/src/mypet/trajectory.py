'''
Created on 17.05.2013

@author: robert
'''

import logging
import datetime
import time
import tables as pt
import os
from mypet.parameter import Parameter, BaseParameter, SimpleResult, BaseResult
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
                
                if not hdf5group.__contains__(key):
                    newhdf5group=hdf5file.createGroup(where=hdf5group, name=key, title=key)
                else:
                    newhdf5group = getattr(hdf5group, key)
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
                the current or supplied time, e.g.
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
                                      
    :param init_time: The time exploration was started, float, in seconds from linux start, e.g. 
                     from time.time()
    
                                      
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
    
    def __init__(self, name,filename,  filetitle='Experiment', dynamicly_imported_classes=[], init_time=None):
    
        if init_time is None:
            init_time = time.time()
        
        
        formatted_time = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        
        self._time = init_time
        self._formatted_time = formatted_time
        #self._givenname = name;
        self._name = name+'_'+str(formatted_time)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)
        
        self._parameters={}
        self._derivedparameters={}
        self._results={}
        self._exploredparameters={}  
        
        self._result_ids={} #the numbering of the results, only important if results have been
    
        
        #Even if there are no parameters yet length is 1 for convention
        self._length = 1
        
        self.Parameters = TreeNode('Parameters',self._name)
        self.DerivedParameters = TreeNode('DerivedParameters',self._name)
        self.Results = TreeNode('Results',self._name)
        
        self._filename = filename 
        self._filetitle=filetitle
        self._comment= Trajectory.standard_comment
        
        
        self.last = None
        self._standard_param_type = Parameter
        
        self._dynamic_imports=['mypet.parameter.SparseParameter']
        self._dynamic_imports.extend(dynamicly_imported_classes)
        
        self._loadedfrom = ('None','None')
     
    def set_standard_param_type(self,param_type):   
        ''' Sets the standard parameter type.
        
        If param_type is not specified for add_parameter, than the standard parameter is used.
        '''
        self._standard_param_type = param_type
    
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        # The tree nodes are not pickled, if the trajectory is unpickled a new tree is build
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
        
        #Builds a new tree for the derived and normal parameters
        for key, val in two_dicts.items():
            self._add_to_tree(val.gfn(), val)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)
        
        
    def get_name(self):  
        return self._name                 
    
    def _load_class(self,full_class_string):
        """Dynamically load a class from a string.
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
         
    def add_result(self, full_result_name, *args,**kwargs):  
        ''' Adds a result to the trajectory, 
        
        This is a rather open implementation the user can provide *args as well as **kwargs
        which will be fed to the init function of your result.
        
        If result_type is already the instance of a Result a new instance will not be created.
        
        Does not update the 'last' shortcut of the trajectory.
        ''' 
        
        assert isinstance(full_result_name, str)
        
        
        full_result_name = 'Results.' + self._name+'.'+ full_result_name
        
        if self._results.has_key(full_result_name):
            self._logger.warn(full_result_name + ' is already part of trajectory, I will replace it.')

        result_name = full_result_name.split('.')[-1]
        
        if 'parent_trajectory' in kwargs.keys():
            parent_trajectory = kwargs.pop('parent_trajectory')
        else:
            parent_trajectory = self._name
        
        if 'result' in kwargs or (args and isinstance(args[0], BaseResult)):
            if 'result' in kwargs:
                instance = kwargs.pop('result')
            else:
                instance = args.pop(0)
            
            if not instance._name == result_name or not instance._fullname == full_result_name or not instance._paren_trajectory == self._name or not instance._filename == self._filename:
                self._logger.warn('Something is wrong with the naming and or filename of your result, I will correct that.')
                instance._name = result_name
                instance._fullname = full_result_name
                instance._paren_trajectory = parent_trajectory
                instance._filename = self._filename
            
        else:
            if 'result_type' in kwargs or (args and isinstance(args[0], type) and issubclass(args[0], BaseResult)):
                if 'result_type' in kwargs:
                    result_type = kwargs.pop('result_type')
                else:
                    args = list(args)
                    result_type = args.pop(0)
                instance =  result_type(result_name,full_result_name,parent_trajectory,self._filename,*args,**kwargs)
            else:
                raise AttributeError('No instance of a result or a result type is specified')
        
        self._results[full_result_name] = instance
        
        self._add_to_tree(full_result_name, instance)
        
        return instance
        
        
    def adp(self, full_parameter_name, *args,**kwargs):
        ''' Short for add_derived_parameter
        '''
        return self.add_derived_parameter(full_parameter_name, *args, **kwargs)
                  
    def add_derived_parameter(self, full_parameter_name, *args,**kwargs):
        ''' Adds a new derived parameter. Returns the added parameter.
        
        :param full_parameter_name: The full name of the derived parameter. Grouping is achieved by 
                                    colons'.'. The trajectory will add 'DerivedParameters' and the 
                                    name  of the current trajectory or run to the name.
                                    For example, the parameter named paramgroup.param1 which is 
                                    added in the current run Run_No_00000001_2013_06_03_17h40m24s 
                                    becomes:
                            DerivedParameters.Run_No_00000001_2013_06_03_17h40m24s.paramgroup.param1
                                    
        :param param_type (or args[0]): The type of parameter, should be passed in **kwargs or as first
                            entry in *args.
                            If not specified the standard parameter is chosen.
                            Standard is the Parameter class, another example 
                            would be the SparseParameter class.
                            
         :param param (or args[0]):      If you already have an instance of the parameter (that takes care of
                            proper naming and stuff) you can pass it here, then the instance
                            will be added to the trajectory instead of creating a new
                            instance via calling instance = param(name,full_parameter_name),
                            i.e. instance = param
                            
        :param *args: Any kinds of desired parameter entries.
        
        :param **kwargs: Any kinds of desired parameter entries.
        
        Example use:
        >>> myparam=traj.add_derived_parameter(self, paramgroup.param1, param_type=Parameter, 
                                                entry1 = 42)
            
        >>> print myparam.entry1
        >>> 42
        '''
        
        assert isinstance(full_parameter_name, str)
        
        full_parameter_name = 'DerivedParameters.' + self._name+'.'+ full_parameter_name
        
        param_name = full_parameter_name.split('.')[-1]

        if self._derivedparameters.has_key(full_parameter_name):
            self._logger.warn(full_parameter_name + ' is already part of trajectory, I will replace it.')
        
        if 'param' in kwargs or (args and isinstance( args[0],BaseParameter)):
            if 'param' in kwargs:
                instance = kwargs.pop('param')
            else:
                args = list(args)
                instance = args.pop(0)
                
                
            if not instance.get_full_name() == full_parameter_name or not instance.get_name() == param_name:
                self._logger.warn('The name of the new parameter and the specified name do not match, I will change it(from  %s to %s, and/or from %s to %s).' % (instance.get_full_name(),full_parameter_name,instance.get_name,param_name))
                instance._name = param_name
                instance._fullname = full_parameter_name
        
        else:
        
            if not 'param_type' in kwargs:
                if args and isinstance(args[0], type) and issubclass(args[0] , BaseParameter):
                        args = list(args)
                        param_type = args.pop(0)
                else:
                    param_type = self._standard_param_type
            else:
                param_type = kwargs.pop('param_type')

            instance =   param_type(param_name,full_parameter_name,*args, **kwargs)

        
        self._derivedparameters[full_parameter_name] = instance
        
        self._add_to_tree(full_parameter_name, instance)
        
        self.last = instance
        
        return instance

    def ap(self, full_parameter_name, *args, **kwargs):
        ''' Short for add_parameter.
        '''
        return self.add_parameter( full_parameter_name,*args, **kwargs)
    
    def add_parameter(self, full_parameter_name,  *args, **kwargs):  
        ''' Adds a new parameter. Returns the added parameter.
        
        :param full_parameter_name: The full name of the derived parameter. Grouping is achieved by 
                                    colons'.'. The trajectory will add 'Parameters'.
                                    For example, the parameter named paramgroup1.param1 becomes:
                                    Parameters.paramgroup1.param1
                                    
        :param param_type (or args[0]): The type of parameter, if not specified the standard parameter is chosen.
                            Should be passed in **kwargs or as first entry in *args.
                             The standard parameter is the Parameter, but get be change via
                             the set_standard_param_type method.
                            
        :param param (or args[0]): If you already have an instance of the parameter (that takes care of
                            proper naming and stuff) you can pass it here, than the instance
                            will be added to the trajectory instead of creating a new
                            instance via calling instance = param_type(name,full_parameter_name)
                            i.e. instance = param_type
        
        :param*args: Any kinds of desired parameter entries
        
        :param **kwargs: Any kinds of desired parameter entries.
        
        Example use:
        >>> myparam=traj.add_parameter(self, paramgroup1.param1, param_type=Parameter, 
                                                entry1 = 42)
            
        >>> print myparam.entry1
        >>> 42
        '''
        assert isinstance(full_parameter_name, str)
        
        assert isinstance(full_parameter_name, str)
        
        full_parameter_name = 'Parameters.'+ full_parameter_name
        
        param_name = full_parameter_name.split('.')[-1]

        if self._parameters.has_key(full_parameter_name):
            self._logger.warn(full_parameter_name + ' is already part of trajectory, I will replace it.')
        
        if 'param' in kwargs or (args and isinstance( args[0],BaseParameter)):
            if 'param' in kwargs:
                instance = kwargs.pop('param')
            else:
                args = list(args)
                instance = args.pop(0)
                
                
            if not instance.get_full_name() == full_parameter_name or not instance.get_name() == param_name:
                self._logger.warn('The name of the new parameter and the specified name do not match, I will change it(from  %s to %s, and/or from %s to %s).' % (instance.get_full_name(),full_parameter_name,instance.get_name,param_name))
                instance._name = param_name
                instance._fullname = full_parameter_name
        
        else:
        
            if not 'param_type' in kwargs:
                if args and isinstance(args[0], type) and issubclass(args[0] , BaseParameter):
                        args = list(args)
                        param_type = args.pop(0)
                else:
                    param_type = self._standard_param_type
            else:
                param_type = kwargs.pop('param_type')

            instance =   param_type(param_name,full_parameter_name,*args, **kwargs)

        
        self._parameters[full_parameter_name] = instance
        
        self._add_to_tree(full_parameter_name, instance)
        
        self.last = instance
        
        return instance
        

       
    
    def _add_to_tree(self, where, instance):
        ''' Adds stuff to the trajectory tree to allow natural naming.
        
        For example:
        >>> traj._add_to_tree(self, Parameters.test.testobject, someobject
        
        then using traj.Parameters.test.testobject will return someobject.
        
        '''
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
        ''' Converts a dictionary containing full parameter entry names into a nested dictionary.
        
        The input dictionary {'Parameters.paramgroup1.param1.entry1':42 , 
                              'Parameters.paramgroup1.param1.entry2':43,
                              'Parameters.paramgroup1.param2.entry1':44} will produce the return of
        
        {'Parameters.paramgroup1':{'entry1':42,'entry2':43}, 
         'Parameters.paramgroup1.param2' : {'entry1':44}}
        '''
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
        ''' Creates Parameter Arrays for exploration.
        
        The user needs to supply a builder function 'build_function' and its necessary parameters 
        *params. The builder function is supposed to return a dictionary of parameter entries with
        their fullname and lists of values which are explored.
        
        For fancy recursive builders that return tuples, the first tuple element must be the above 
        named entry list dictionary.
        
        For example the builder could return
        {'Parameters.paramgroup1.param1.entry1':[21,21,21,42,42,42],
         'Parameters.paramgroup1.param2.entry1' : [1.0, 2.0, 3.0, 1.0, 2.0, 3.0]}
         
         which would be the Cartesian product of [21,42] and [1.0,2.0,3.0].

        These values are added to the stored parameters and param1 and param2 would become arrays.
        '''
        build_dict = build_function(*params) 
        
        # if the builder function returns tuples, the first element must be the build dictionary
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
        ''' Stores general information about the trajectory in the hdf5file.
        
        The 'Info' table will contain ththane name of the trajectory, it's timestamp, a comment,
        the length (aka the number of single runs), and if applicable a previous trajectory the
        current one was originally loaded from.
        The name of all derived and normal parameters as well as the results are stored in
        appropriate overview tables.
        Thes include the fullname, the name, the name of the class (e.g. SparseParameter),
        the size (1 for single parameter, >1 for explored parameter arrays).
        In case of a derived parameter or a result, the name of the creator trajectory or run
        and the id (-1 for trajectories) are stored.
        '''
        assert isinstance(hdf5file,pt.File)
        
        loaddict = {'Trajectory' : pt.StringCol(self.MAX_NAME_LENGTH),
                    'Filename' : pt.StringCol(self.MAX_NAME_LENGTH)}
        
        descriptiondict={'Name': pt.StringCol(len(self._name)), 
                         'Time': pt.StringCol(len(self._formatted_time)),
                         'Timestamp' : pt.FloatCol(),
                         'Comment': pt.StringCol(len(self._comment)),
                         'Length':pt.IntCol(),
                         'Loaded_From': loaddict.copy()}
        
        infotable = hdf5file.createTable(where=trajectorygroup, name='Info', description=descriptiondict, title='Info')
        newrow = infotable.row
        newrow['Name']=self._name
        newrow['Timestamp']=self._time
        newrow['Time']=self._formatted_time
        newrow['Comment']=self._comment
        newrow['Length'] = self._length
        newrow['Loaded_From/Trajectory']=self._loadedfrom[0]
        newrow['Loaded_From/Filename']=self._loadedfrom[1]
        
        newrow.append()
        infotable.flush()
        
        
        tostore_dict =  {'ParameterTable':self._parameters, 'DerivedParameterTable':self._derivedparameters, 'ExploredParameterTable' :self._exploredparameters,'ResultsTable' : self._results}
        
        for key, dictionary in tostore_dict.items():
            
            paramdescriptiondict={'Full_Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                  'Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                  'Class_Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH)}
            
            if not key == 'ResultsTable':
                paramdescriptiondict.update({'Size' : pt.IntCol()})
            
            if key in ['DerivedParameterTable', 'ResultsTable']:
                paramdescriptiondict.update({'Creator_Name':pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                             'Parent_Trajectory':pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                             'Creator_ID':pt.IntCol()})
            
            paramtable = hdf5file.createTable(where=trajectorygroup, name=key, description=paramdescriptiondict, title=key)
            
            self._store_single_table(dictionary, paramtable, self._name,-1,self._name)
    
    def _store_single_table(self,paramdict,paramtable, creator_name, creator_id, parent_trajectory):
        ''' Stores a single overview table.
        
        Called from _store_meta_data and store_single_run
        '''
                                 
        assert isinstance(paramtable, pt.Table)    


        #print paramtable._v_name
        
        newrow = paramtable.row
        for key, val in paramdict.items():
            if not paramtable._v_name == 'ResultsTable' :
                newrow['Size'] = len(val)
            else:
                #check if this is simply an added explored parameter to easily comprehend the 
                # hdf5 tree with a viewer
                if 'ExploredParameters' in key:
                    continue;
                
                
            newrow['Full_Name'] = key
            newrow['Name'] = val.get_name()
            newrow['Class_Name'] = val.get_class_name()
            
            
            if paramtable._v_name in ['DerivedParameterTable', 'ResultsTable']:
                newrow['Creator_Name'] = creator_name
                newrow['Creator_ID'] = creator_id
                newrow['Parent_Trajectory'] = parent_trajectory
                
            newrow.append()
        
        paramtable.flush()
   
    def load_trajectory(self, trajectoryname, filename = None, load_derived_params = False, load_results = False, replace = False):  
        ''' Loads a single trajectory from a given file.
        
        Per default derived parameters and results are not loaded. If the filename is not specified
        the file where the current trajectory is supposed to be stored is taken.
        
        If the user wants to load results, the actual data is not loaded, only dummy objects
        are created, which must load their data independently. It is assumed that 
        results of many simulations are large and should not be loaded all together into memory.
        
        If replace is true than the current trajectory name is replaced by the name of the loaded
        trajectory, so is the filename.
        '''
        if filename:
            openfilename = filename
        else:
            openfilename = self._filename
            
        if replace:
            self._name = trajectoryname
            self._filename = filename
            
            
        self._loadedfrom = (trajectoryname,os.path.abspath(openfilename))
            
        if not os.path.isfile(openfilename):
            raise AttributeError('Filename ' + openfilename + ' does not exist.')
        
        hdf5file = pt.openFile(filename=openfilename, mode='r')
    
            
        try:
            trajectorygroup = hdf5file.getNode(where='/', name=trajectoryname)
        except Exception:
            raise AttributeError('Trajectory ' + trajectoryname + ' does not exist.')
                
        self._load_meta_data(trajectorygroup, replace)
        self._load_params(trajectorygroup)
        if load_derived_params:
            self._load_derived_params(trajectorygroup)
        if load_results:
            self._load_results(trajectorygroup,trajectoryname,filename)
        
        hdf5file.close()
    
    def _load_results(self,trajectorygroup,trajectoryname,filename):
        resulttable = trajectorygroup.ResultsTable
        self._load_any_param_or_result(self._results,resulttable,trajectorygroup,True,trajectoryname,filename)
        
    def _create_class(self,class_name):
        ''' Dynamically creates a class.
        
        It is tried if the class can be created by default, if not the list of the dynamically
        loaded classes is used (see __init__).
        '''
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
        self._load_any_param_or_result(self._parameters,paramtable,trajectorygroup)
        
    def _load_derived_params(self,trajectorygroup):
        paramtable = trajectorygroup.DerivedParameterTable
        self._load_any_param_or_result(self._derivedparameters,paramtable,trajectorygroup)
        
    def _load_any_param_or_result(self,wheredict,paramtable,trajectorygroup,creating_result_tree=False, trajectory_name = None, filename = None):
        ''' Loads a single parameter from a pytable.
        
        :param paramtable: The overiew pytable containing all parameters
        :param trajectorygroup: The hdf5 group of the trajectory
        '''
        assert isinstance(paramtable,pt.Table)
        
        for row in paramtable.iterrows():
            fullname = row['Full_Name']
            name = row['Name']
            class_name = row['Class_Name']
            if fullname in wheredict:
                self._logger.warn('Paremeter ' + fullname + ' is already in your trajectory, I am overwriting it.')
                del wheredict[fullname]
                continue
            
            if paramtable._v_name in ['DerivedParameterTable', 'ResultsTable']:
                #creator_name = row['Creator_Name'] 
                creator_id = row['Creator_ID']
                           
            new_class = self._create_class(class_name)    
            
            if not creating_result_tree:
                paraminstance = new_class(name,fullname)
            else:
                paraminstance= new_class(name, fullname, trajectory_name, filename)
                if not creator_id in self._result_ids:
                    self._result_ids[creator_id]=[]
                self._result_ids[creator_id].append(paraminstance)
            
            where = 'trajectorygroup.' + fullname
            paramgroup = eval(where)
            
            assert isinstance(paraminstance, (BaseParameter,BaseResult))
            
            if not creating_result_tree:
                paraminstance.load_from_hdf5(paramgroup)
                
                if len(paraminstance)>1:
                    self._exploredparameters[fullname] = paraminstance
            
            wheredict[fullname]=paraminstance
            
            self._add_to_tree(fullname, paraminstance)
    
    def get_result_ids(self):
        return self._result_ids
    
    def get_results(self):
        return self._results
    
    def get_explored_params(self):  
        return self._exploredparameters
             
    def _load_meta_data(self,trajectorygroup, replace): 
        metatable = trajectorygroup.Info
        metarow = metatable[0]
        
        self._length = metarow['Length']
        
        if replace:
            self._comment = metarow['Comment']
            self._time = metarow['Timestamp']
            self._formatted_time = metarow['Time']
            self._loadedfrom=metarow['Loaded_From']
        else:
            self.add_comment(metarow['Comment'])
            
    
    def store_single_run(self,trajectory_name,n):  
        ''' Stores the derived parameters and results of a single run.
        '''
        hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)
        
        #print 'Storing %d' %n
        trajectorygroup = hdf5file.getNode(where='/', name=trajectory_name)
        
        self.DerivedParameters.store_to_hdf5(hdf5file, trajectorygroup.DerivedParameters) 
        
        paramtable = getattr(trajectorygroup, 'DerivedParameterTable')
        self._store_single_table(self._derivedparameters, paramtable, self.get_name(),n,trajectory_name)
        
        self.Results.store_to_hdf5(hdf5file, trajectorygroup.Results)
        
        paramtable = getattr(trajectorygroup, 'ResultsTable')
        self._store_single_table(self._results, paramtable, self.get_name(),n,trajectory_name)
        
        hdf5file.flush()
        hdf5file.close()
    
                
    def store_to_hdf5(self):
        ''' Stores a trajectory to the in __init__ specified hdf5file.
        '''
        self._logger.info('Start storing Parameters.')
        (path, filename)=os.path.split(self._filename)
        if not os.path.exists(path):
            os.makedirs(path)
        
        self.lock_parameters()
        
        
        hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)
        
        trajectorygroup = hdf5file.createGroup(where='/', name=self._name, title=self._name)
    
        if not trajectorygroup.__contains__('Parameters'):
            hdf5file.createGroup(where= trajectorygroup, name='Parameters', title='Parameters')
        if not trajectorygroup.__contains__('DerivedParameters'):
            hdf5file.createGroup(where= trajectorygroup, name='DerivedParameters', title='DerivedParameters')
        if not trajectorygroup.__contains__('Results'):
            hdf5file.createGroup(where= trajectorygroup, name='Results', title='Results')
        
        self._store_meta_data(hdf5file, trajectorygroup)
        
        self.Parameters.store_to_hdf5(hdf5file, getattr(trajectorygroup,'Parameters'))
        self.DerivedParameters.store_to_hdf5(hdf5file, getattr(trajectorygroup,'DerivedParameters'))
        self.Results.store_to_hdf5(hdf5file, getattr(trajectorygroup,'Results'))
        
        hdf5file.flush()
        
        hdf5file.close()
        self._logger.info('Finished storing Parameters.')
        

      
    
    def get_paramspacepoint(self,n):
        ''' Returns the nth parameter space point of the trajectory.
        
        The returned instance is a a shallow copy of the trajectory without the parameter arrays
        but only single parameters. From every array the nth parameter is used.
        '''
        newtraj = copy.copy(self)
        newtraj._derivedparameters = self._derivedparameters.copy()
        newtraj._parameters = self._parameters.copy()
        newtraj._exploredparameters = {}
        
        newtraj.Parameters = TreeNode('Parameters',self._name)
        newtraj.DerivedParameters = TreeNode('DerivedParameters',self._name)
        newtraj.Results = TreeNode('Results',self._name)
        

        
        assert isinstance(newtraj, Trajectory) #Just for autocompletion
        
        #Do not copy the results, this is way too much in case of multiprocessing
        if config['multiproc']:
            newtraj.Results = TreeNode('Results',self._name)
            
        # extract only one particular paramspacepoint
        for key,val in self._exploredparameters.items():
            assert isinstance(val, BaseParameter)
            newparam = val.access_parameter(n)
            newtraj._exploredparameters[key] = newparam
            if key in newtraj._parameters:
                newtraj._parameters[key] = newparam
            if key in newtraj._derivedparameters:
                newtraj._derivedparameters[key] = newparam
            #newtraj._add_to_tree(key, newparam)
        
        two_dicts = {}
        two_dicts.update(newtraj._parameters)
        two_dicts.update(newtraj._derivedparameters)
        
        #Builds a new tree for the derived and normal parameters
        for key, val in two_dicts.items():
            newtraj._add_to_tree(val.gfn(), val)
            
        
        return newtraj 
    
        
        
        
    def prepare_experiment(self):
        ''' Prepares the trajectory for parameter exploration.
        
        Locks all derived and normal parameters and writes them to the hdf5file.
        '''
        self.lock_parameters()
        self.lock_derived_parameters()
        self.store_to_hdf5()

     
    def make_single_run(self,n):
        ''' Creates a SingleRun object for parameter exploration.
        
        The SingleRun object can used as the parent trajectory. The object contains a shallow
        copy of the parent trajectory but wihtout parameter arrays. From every array only the 
        nth parameter is used.
        '''
        return SingleRun(self._filename, self, n) 
    
    def __getattr__(self,name):
        
        if not hasattr(self, 'Parameters') or not hasattr(self, 'DerivedParameters') or not hasattr(self, 'Results'):
            raise AttributeError('This is to avoid pickling issues!')
     

        if name in self.DerivedParameters.__dict__:
            return self.DerivedParameters.__dict__[name]
        elif name in self.Parameters.__dict__:
            return self.Parameters.__dict__[name]
        else:
            #check if the paramter can be found solely by the name
            for [key,param] in self._derivedparameters.iteritems():
                if name == param.get_name():
                    return param
            for [key,param] in self._parameters.iteritems():
                if name == param.get_name():
                    return param
        
        if name in self.Results.__dict__:
            return self.Results.__dict__[name]
        else:
            for [key, val] in self._results:
                if name == val.get_name():
                    return val
                
        
        raise AttributeError('Trajectory does not contain %s' % name)

    def multiproc(self):
        return self._multiproc

class SingleRun(object):
    ''' Constitutes one specific parameter combination in the whole trajectory.
    
    A SingleRun instance is accessed during the actual run phase of a trajectory. 
    There exists a SignleRun object for each point in the parameter space.
    The object contains a shallow and reduced copy of the trajectory. From each parameter array
    only the nth parameter can be accesses.
    
    Parameters can no longer be added, the parameter set is supposed to be complete before
    a the actual running of the experiment. However, derived parameters can still be added.
    This might be useful, for example, to store a connectivity matrix of neural network,
    that is built new for point in the trajectory.
    
    Natural Naming applies as before. For convenience a SingleRun object is still named traj:
    >>> print traj.Parameters.paramgroup1.param1.entry1
    >>> 42
    
    There are several shortcuts through the parameter tree.
    >>> pint traj.paramgroup1.param1.entry
    
    Would first look for a parameter paramgroup1.param1 in the derived parameters of the current
    run, next the derived parameters of the trajectory would be checked, if that was not 
    successful either, the Parameters of the trajectory are searched.
    
    The instance of a SingleRun is never instantiated by the user but by the parent trajectory.
    From the trajectory it gets assigned the current hdf5filename, a link to the parent trajectory,
    and the corresponding index n within the trajectory, i.e. the index of the parameter space point.
    '''
    
    def __init__(self, filename, parent_trajectory,  n):
        
        assert isinstance(parent_trajectory, Trajectory)

        self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%Hh%Mm%Ss')

        self._n = n
        self._filename = filename 
        
        name = 'Run_No_%08d' % n
        self._small_parent_trajectory = parent_trajectory.get_paramspacepoint(n)
        self._single_run = Trajectory(name=name, filename=filename)
        
        self._logger = logging.getLogger('mypet.trajectory.SingleRun=' + self._single_run.get_name())
    
    def get_n(self): 
        return self._n   
            
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        return result
    
    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.trajectory.SingleRun=' + self._single_run.get_name())
        #self._logger = multip.get_logger()
    
    def adp(self, full_parameter_name, *args,**kwargs):
        ''' Short for add_derived_parameter
        '''
        return self.add_derived_parameter(full_parameter_name, *args, **kwargs)
        
    def add_derived_parameter(self, full_parameter_name,  *args, **kwargs):
        return self._single_run.add_derived_parameter(full_parameter_name, *args, **kwargs)

    
    def ap(self, full_parameter_name, *args, **kwargs):
        ''' Short for add_parameter.
        '''
        return self.add_parameter( full_parameter_name,*args, **kwargs)
    
    
    def add_parameter(self, full_parameter_name, *args, **kwargs): 
        ''' Adds a DERIVED Parameter to the trajectory and emits a warning.
        ''' 
        self._logger.warn('Cannot add Parameters anymore, yet I will add a derived Parameter.')
        return self.add_derived_parameter(full_parameter_name, *args, **kwargs)
       
    def __getattr__(self,name):
        
        if not hasattr(self, '_small_parent_trajectory') or not hasattr(self, '_single_run'):
            raise AttributeError('This is to avoid pickling issues!')
        
        if name == 'pt' or name == 'ParentTrajectory':
            return self._small_parent_trajectory
        
        try:
            return getattr(self._single_run,name)
        except Exception:
            return getattr(self._small_parent_trajectory,name)
           
    def get_parent_name(self):
        return self._small_parent_trajectory.get_name()
    
    def get_name(self):
        return self._single_run.get_name()
    
    def add_result(self, full_result_name, *args,**kwargs):
        kwargs['parent_trajectory'] = self._small_parent_trajectory.get_name()
        return self._single_run.add_result(full_result_name, *args,**kwargs)
    
    def store_to_hdf5(self, lock=None):
        ''' Stores all obtained results a new derived parameters to the hdf5file.
        
        In case of multiprocessing a lock needs to be provided to prevent hdf5file corruption!!!
        '''
        
        if lock:
            lock.acquire()
            #print 'Start storing run %d.' % self._n
            self._logger.debug('Start storing run %d.' % self._n)
            
        self._add_explored_params()
        self._single_run.store_single_run(self._small_parent_trajectory.get_name(), self._n)
        
        if lock:
            #print 'Finished storing run %d,' % self._n
            self._logger.debug('Finished storing run %d,' % self._n)
            lock.release()

    def _add_explored_params(self):
        ''' Stores the explored parameters as a Node in the HDF5File under the results nodes for easier comprehension of the hdf5file.
        '''
        for fullname,param in self._small_parent_trajectory._exploredparameters.items():
            splitname = fullname.split('.')
            
            #remove the Parameters tag
            splitname = ['ExploredParameters']+splitname[1:]
            newfullname = '.'.join(splitname)
            
            # adds the entry 'is_explored_param' to prevent the listing of the parameter again
            # in the ResultsTable list
            self.add_result(full_result_name=newfullname, result_type=SimpleResult,  **param.to_dict())
            
