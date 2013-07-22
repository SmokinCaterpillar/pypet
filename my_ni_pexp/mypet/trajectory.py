'''
Created on 17.05.2013

@author: robert
'''

import logging
import datetime
import time
import os
from twisted.python.deprecate import _fullyQualifiedName
from mypet.parameter import Parameter, BaseParameter, SimpleResult, BaseResult
import importlib as imp
import copy
from mypet.configuration import config




#from multiprocessing.synchronize import Lock

class NaturalNamingInterface(object):

    
    def __init__(self, working_trajectory_name, parent_trajectory_name):   
        self._quick_access = False
        #self._double_checking = True
        self._working_trajectory_name=working_trajectory_name
        self._parent_trajectory_name=parent_trajectory_name
        
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._working_trajectory_name)
        
        #self._debug = {}
        self._storage_dict =  {} 
        self._nodes_and_leaves = set()

        
        self._root = TreeNode(self,'_root')
        self._root._dict_list = [self._storage_dict]
        
    def __getattr__(self,name):
         
        if not hasattr(self, '_root') or \
             not hasattr(self,'_shortcut') or \
             not hasattr(self, '_find') or \
             not hasattr(self, '_find_candidates') or \
             not hasattr(self, '_find_recursively') or \
             not hasattr(self, '_select') or \
             not hasattr(self, '_sort_according_to_type') or \
             not hasattr(self, '_get_result') or \
             not hasattr(self, '_nodes_and_leaves') or \
             not hasattr(self, '_storage_dict'):

            raise AttributeError('This is to avoid pickling issues and problems with internal variables!')
             
        return getattr(self._root, name)
        
    def _shortcut(self, name):
        
        expanded = None
        
        if name in ['wt', 'WorkingTrajectory', 'workintrajectory', 'Working_Trajectory', 'working_trajectory']:
            expanded= self._working_trajectory_name
            
        
        if name in ['pt', 'ParentTrajectory', 'parenttrajectory', 'Parent_Trajectory', 'parent_trajectory']:
            expanded = self._parent_trajectory_name
        
        return expanded
         
        
    
    def _add_to_nninterface(self, fullname, data):
        
        split_name = fullname.split('.')
        
        for name in split_name:
            
            if not self._shortcut(name) == None:
                raise AttributeError('%s is already an important shortcut, cannot add it.' % name)
        
            
    
        leaf = split_name.pop()
        
        self._add_to_storage_dict(split_name, leaf, data)

        split_name.append(leaf) 
        
        for name in split_name:
            self._nodes_and_leaves.add(name)
        
    
    def _add_to_storage_dict(self, where_list, leaf, data):
        act_dict = self._storage_dict
        for name in where_list:
            if not name in act_dict:
                act_dict[name] ={}

            act_dict = act_dict[name]
        
        if leaf in act_dict and isinstance(act_dict[leaf], dict):
            raise AttributeError('Your addition does not work, you would have a tree node called %s as well as a leaf containing data, both hanging below %s.' % (leaf,name))
                
        act_dict[leaf] = data
            


        
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        del result['_root'] 
        result['_storage_dict'] = self._recursive_shallow_copy(self._storage_dict)
        result['_nodes_and_leaves'] = self._nodes_and_leaves.copy()
        return result
    
    def _recursive_shallow_copy(self, dictionary):
        
        new_dict = dictionary.copy()
        for key, val in dictionary.items():
            if isinstance(val, dict):
                new_dict[key] = self._recursive_shallow_copy(val)
        
        return new_dict
    
    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' +  self._working_trajectory_name)
        self._root = TreeNode(nninterface=self, name='_root')
        self._root._dict_list = [self._storage_dict]
      
    def _find(self, node, dict_list): 
        
        assert isinstance(node, TreeNode)
        
        candidate_list = self._find_candidates(node._name, dict_list)
        
        return self._select(candidate_list, node)

                
     
    def _find_candidates(self,name, dict_list):
        
        result_list = []
        for dictionary in dict_list:
            result_list.extend(self._find_recursively(dictionary, name))    
        
        return result_list  
    
    def _find_recursively(self,dictionary, name): 
        result_list = []
        for key, val in dictionary.items():
            if key == name:
                result_list.append(val)
            
            if isinstance(val, dict):
                result_list.extend(self._find_recursively(val, name))
        
        return result_list

    def _select(self, candidate_list, node):
        
        dict_list, item_list = self._sort_according_to_type(candidate_list)
        
        items = len(item_list)
        if dict_list:
            node._dict_list = dict_list
            items = items +1
        
        if items > 0:
            
            if items > 1:
                name_list = [item.get_fullname() for item in item_list]
                
                if dict_list:
                    name_list.append('Another TreeNode')
                    item_list.append(node)

                self._logger.warning('There are %d solutions for your query >>%s<<. The following list has been found: %s. You will get the full list!' %(items,node._fullname,str(name_list)))
            
                return item_list
            
            elif item_list:
                return self._get_result(item_list[0])
            else:
                return node
        else:
            raise AttributeError('Your query >>%s<< failed, it is not contained in the trajectory.' % node._fullname)
        
        
    
    
    def _sort_according_to_type(self, candidate_list):
        
        dict_list = []
        result_list = []
        parameter_list=[]
        derived_traj_list=[]
        derived_run_list = []
        
        for candidate in candidate_list:
            if isinstance(candidate, dict):
                dict_list.append(candidate)
            else:
                fullname = candidate.get_fullname()
                split_name = fullname.split('.')
                first = split_name[0]
                second = split_name[1]
                if first == 'Results':
                    result_list.append(candidate)
                elif first == 'Parameters':
                    parameter_list.append(candidate)
                else:
                    if second == self._parent_trajectory_name:
                        derived_traj_list.append(candidate)
                    else:
                        derived_run_list.append(candidate)
        
        return dict_list, derived_run_list+derived_traj_list+parameter_list+result_list
     
       
    def _get_result(self, data):
        
        if self._quick_access and isinstance(data, BaseParameter) and not isinstance(data, BaseResult):
            return data()
        else:
            return data

            

        

class TreeNode(object):
        '''Object to construct the file tree.
        
        The recursive structure allows access to parameters via natural naming.
        '''
        def __init__(self, nninterface, name, parents_fullname=''):
            
            self._nninterface = nninterface
            self._name = name
            
            if parents_fullname == '':
                self._fullname = self._name
            else:
                self._fullname = parents_fullname+'.'+self._name
         
            self._dict_list =[]
      
        def __getattr__(self,name):
            
            if not hasattr(self, '_nninterface') or not hasattr(self, '_fullname') or not hasattr(self, '_name') or not hasattr(self,'_dict_list'):
                raise AttributeError('This is to avoid pickling issues')
            
            shortcut = self._nninterface._shortcut(name) 
            if not shortcut == None:
                name = shortcut 
            
            if not name in self._nninterface._nodes_and_leaves:
                raise AttributeError('%s is not part of your trajectory or it\'s tree.' % name)
        
            
                
                
            new_node = TreeNode(self._nninterface, name, self._fullname) 

            return self._nninterface._find(new_node, self._dict_list)

 

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
    

    
    standard_comment = 'Dude, do you not want to tell us your amazing story about this trajectory?'

    def store(self):
        self.lock_parameters()
        self._storageservice.store(self,type='Trajectory')


    def store_single_run(self,trajectory_name,n):
        self._storageservice.store(self,type='SingleRun', n=n)
   
    def __len__(self): 
        return self._length      
    
    def __init__(self, storageservice, dynamicly_imported_classes=[], init_time=None):
    
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
        
        self._nninterface = NaturalNamingInterface(working_trajectory_name=self._name, parent_trajectory_name = self._name)
        
        
        self._storageservice = storageservice

        self._comment= Trajectory.standard_comment
        
        self._quick_access = False
        self._double_checking = True
        
        self.last = None
        self._standard_param_type = Parameter
        
        
        self._dynamic_imports=['mypet.parameter.SparseParameter']
        self._dynamic_imports.extend(dynamicly_imported_classes)
        
        self._loadedfrom = ('None','None')

    def set_quick_access(self, val):
        assert isinstance(val,bool)
        self._nninterface._quick_access = val
    
#     def set_double_checking(self, val):
#         assert isinstance(val,bool)
#         self._nninterface._double_checking=val
    
    def set_standard_param_type(self,param_type):   
        ''' Sets the standard parameter type.
        
        If param_type is not specified for add_parameter, than the standard parameter is used.
        '''
        self._standard_param_type = param_type
    
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        result['_nninterface'] =copy.copy(self._nninterface)
        result['_derivedparameters']=self._derivedparameters.copy()
        result['_parameters'] = self._parameters.copy()
        result['_results'] = self._results.copy()
        return result
    
    def __setstate__(self, statedict):
        self.__dict__.update(statedict)

        #self._tree= TreeNode(parent_trajectory=self, predecessors=[], depth=0, name='root')
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
         
    def add_result(self, *args,**kwargs):
        ''' Adds a result to the trajectory, 
        
        This is a rather open implementation the user can provide *args as well as **kwargs
        which will be fed to the init function of your result.
        
        If result_type is already the instance of a Result a new instance will not be created.
        
        Does not update the 'last' shortcut of the trajectory.
        '''
        
        
        if 'parent_trajectory' in kwargs.keys():
            parent_trajectory = kwargs.pop('parent_trajectory')
        else:
            parent_trajectory = self._name
        
        if 'result' in kwargs or (args and isinstance(args[0], BaseResult)):
            if 'result' in kwargs:
                instance = kwargs.pop('result')
            else:
                instance = args.pop(0)
            

            
        else:
            if not 'result_name' in kwargs:
                raise ValueError('Your new Parameter needs a name, please call the function with result_name=...')

            full_result_name = kwargs.pop('result_name')

            if 'result_type' in kwargs or (args and isinstance(args[0], type) and issubclass(args[0], BaseResult)):
                if 'result_type' in kwargs:
                    result_type = kwargs.pop('result_type')
                else:
                    args = list(args)
                    result_type = args.pop(0)
                instance =  result_type(full_result_name,parent_trajectory,self._filename,*args,**kwargs)
            else:
                raise AttributeError('No instance of a result or a result type is specified')


        full_result_name = instance._fullname
        split_name = full_result_name.split('.')
        if not split_name[0] == 'Results':
            instance._fullname = 'Results.'+instance._fullname
            instance._location = 'Results.'+instance._location
            self._logger.debug('I added %s to the result name it is now: %s.' % (where, instance._fullname))


        if full_result_name in self._results:
            self._logger.warn(full_result_name + ' is already part of trajectory, I will replace it.')


        self._results[full_result_name] = instance
        
        self._nninterface._add_to_nninterface(full_result_name, instance)
        
        return instance
        
        
    def adp(self,  *args,**kwargs):
        ''' Short for add_derived_parameter
        '''
        return self.add_derived_parameter( *args, **kwargs)
                  
    def add_derived_parameter(self, *args,**kwargs):
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

        return self._add_any_param(where = 'DerivedParameters',where_dict=self._derivedparameters,*args,**kwargs)
        
    def _add_any_param(self, where, where_dict, *args,**kwargs):

        
        if 'param_replace' in kwargs:
            param_replace = kwargs.pop('param_replace')
        else:
            param_replace = False


        if 'param' in kwargs or (args and isinstance( args[0],BaseParameter)):
            if 'param' in kwargs:
                instance = kwargs.pop('param')
            else:
                args = list(args)
                instance = args.pop(0)

        else:

            if not 'param_name' in kwargs:
                raise ValueError('Your new Parameter needs a name, please call the function with param_name=...')

            full_parameter_name = kwargs.pop('param_name')

            if not 'param_type' in kwargs:
                if args and isinstance(args[0], type) and issubclass(args[0] , BaseParameter):
                        args = list(args)
                        param_type = args.pop(0)
                else:
                    param_type = self._standard_param_type
            else:
                param_type = kwargs.pop('param_type')


            instance =   param_type(full_parameter_name,*args, **kwargs)


        full_parameter_name = instance._fullname
        split_name = full_parameter_name.split('.')
        if not where == split_name[0]:
            instance._fullname = where+'.'+instance._fullname
            instance._location = where+'.'+instance._location
            self._logger.debug('I added %s to the parameter name it is now: %s.' % (where, instance._fullname))


        if full_parameter_name in where_dict:
            if param_replace:
                self._logger.debug(full_parameter_name + ' is already part of trajectory, I will replace it since you called with param_replace=True!')
            else:
                self._logger.warn(full_parameter_name + ' is already part of trajectory, I will keep the old one. If you want to replace the parameter, call the adding with param_replace=True!')
                return where_dict[full_parameter_name]


        where_dict[full_parameter_name] = instance
        
        
        #self._nninterface.peter ='Dubb'
        self._nninterface._add_to_nninterface(full_parameter_name, instance)
        
        
        self.last = instance
        
        return instance
    
    

    def ap(self, *args, **kwargs):
        ''' Short for add_parameter.
        '''
        return self.add_parameter( *args, **kwargs)
    
    def add_parameter(self,   *args, **kwargs):
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

        
        return self._add_any_param('Parameters',self._parameters, *args,**kwargs)
        

        
        
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
    
    def explore(self,build_function,*args,**kwargs): 
        ''' Creates Parameter Arrays for exploration.
        
        The user needs to supply a builder function 'build_function' and its necessary parameters 
        *args or **kwargs. The builder function is supposed to return a dictionary of parameter entries with
        their fullname and lists of values which are explored.
        
        For fancy recursive builders that return tuples, the first tuple element must be the above 
        named entry list dictionary.
        
        For example the builder could return
        {'Parameters.paramgroup1.param1.entry1':[21,21,21,42,42,42],
         'Parameters.paramgroup1.param2.entry1' : [1.0, 2.0, 3.0, 1.0, 2.0, 3.0]}
         
         which would be the Cartesian product of [21,42] and [1.0,2.0,3.0].

        These values are added to the stored parameters and param1 and param2 would become arrays.
        '''
        build_dict = build_function(*args,**kwargs) 
        
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
            

    def load(self,trajectoryname, filename = None, load_derived_params = False, load_results = False, replace = False):
        self._storageservice.load(self,trajectoryname, filename, load_derived_params, load_results, replace)

   


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
    

        

    
    def get_result_ids(self):
        return self._result_ids
    
    def get_results(self):
        return self._results
    
    def get_explored_params(self):  
        return self._exploredparameters
             

            
    

    
                

        


    def get_paramspacepoint(self,n):
        ''' Returns the nth parameter space point of the trajectory.
        
        The returned instance is a a shallow copy of the trajectory without the parameter arrays
        but only single parameters. From every array the nth parameter is used.
        '''
        #self._collector=PickleDummy
        newtraj = copy.copy(self)
        #self._collector = NameCollector(self)
        
        #newtraj._derivedparameters = self._derivedparameters.copy()
       #newtraj._parameters = self._parameters.copy()
        #newtraj._exploredparameters = self._results.copy()
        #newtraj._NNtree = self._tree._rebuild()
        #newtraj.Parameters = TreeNode('Parameters',self._name)
        #newtraj.DerivedParameters = TreeNode('DerivedParameters',self._name)
        #newtraj.Results = TreeNode('Results',self._name)
        

        
        assert isinstance(newtraj, Trajectory) #Just for autocompletion
        

#         two_dicts = {}
#         two_dicts.update(self._derivedparameters)
#         two_dicts.update(self._parameters)

        # extract only one particular paramspacepoint

        for key,val in self._exploredparameters.items():
            assert isinstance(val, BaseParameter)
            newparam = val.access_parameter(n)
            newtraj._exploredparameters[key] = newparam
            if key in newtraj._parameters:
                newtraj._parameters[key] = newparam
            if key in newtraj._derivedparameters:
                newtraj._derivedparameters[key] = newparam
            
            newtraj._nninterface._add_to_nninterface(newparam.get_fullname(), newparam)
       
    
            
        
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
        
        if not hasattr(self, '_nninterface'):
            raise AttributeError('This is to avoid pickling issues!')
   
        return getattr(self._nninterface, name)
        



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
        
        self._nninterface = self._small_parent_trajectory._nninterface
        del self._single_run._nninterface
        self._single_run._nninterface = self._nninterface
        
        self._nninterface._parent_trajectory_name = self._small_parent_trajectory.get_name()
        self._nninterface._working_trajectory_name = self._single_run.get_name()
        
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
        
        if not hasattr(self, '_nninterface'):
            raise AttributeError('This is to avoid pickling issues!')
        
        return getattr(self._nninterface, name)
        
     
    def get_parent_name(self):
        return self._small_parent_trajectory.get_name()
    
    def get_name(self):
        return self._single_run.get_name()
    
    def add_result(self, full_result_name, *args,**kwargs):
        kwargs['parent_trajectory'] = self._small_parent_trajectory.get_name()
        return self._single_run.add_result(full_result_name, *args,**kwargs)
    
    def set_quick_access(self,val):
        assert isinstance(val, bool)
        self._nninterface._quick_access=val
        
#     def set_double_checking(self,val):
#         assert isinstance(val, bool)
#         self._nninterface._double_checking=val
        
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
            
