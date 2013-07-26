'''
Created on 17.05.2013

@author: robert
'''

import logging
import datetime
import time
from mypet.parameter import Parameter, BaseParameter, SimpleResult, BaseResult
import importlib as imp
import copy
import mypet.petexceptions as pex






#from multiprocessing.synchronize import Lock

class NaturalNamingInterface(object):

    
    def __init__(self, working_trajectory_name, parent_trajectory_name):   
        self._fast_access = False
        #self._double_checking = True
        self._working_trajectory_name=working_trajectory_name
        self._parent_trajectory_name=parent_trajectory_name
        
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._working_trajectory_name)
        
        #self._debug = {}
        self._storage_dict =  {} 
        self._nodes_and_leaves = set()

        
        self._root = TreeNode(self,'_root')
        self._root._dict_list = [self._storage_dict]


    def to_dict(self, evaluate = False, short_names=False):
        return self._root.to_dict(evaluate, short_names)






    def __getattr__(self,name):
         
        if (not  '_root' in self.__dict__ or
             not '_shortcut' in self.__class__.__dict__ or
             not  '_find' in self.__class__.__dict__ or
             not  '_find_candidates' in self.__class__.__dict__ or
             not  '_find_recursively' in self.__class__.__dict__ or
             not  '_select' in self.__class__.__dict__ or
             not  '_sort_according_to_type' in self.__class__.__dict__ or
             not  '_get_result' in self.__class__.__dict__ or
             not  '_nodes_and_leaves' in self.__dict__ or
             not  '_storage_dict' in self.__dict__):

            raise AttributeError('This is to avoid pickling issues and problems with internal variables!')
             
        return getattr(self._root, name)

    def get(self, name, evaluate = False):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>evaluate<<.

        :param name: The Name of the Parameter,Result or TreeNode that is requested.
        :param evaluate: If the default evaluation of a parameter should be returned.
        :return: The requested object or it's default evaluation. Returns None if object could not be found.
        '''
        return self._root.get(name, evaluate)


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
                return self._get_result(item_list[0], self._fast_access)
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
     
       
    def _get_result(self, data, fast_access):
        
        if fast_access and isinstance(data, BaseParameter) and not isinstance(data, BaseResult):
            return data.return_default()
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

        if (not  '_nninterface' in self.__dict__ or
            not  '_fullname' in self.__dict__ or
            not  '_name' in self.__dict__ or
            not '_dict_list' in self.__dict__):
            raise AttributeError('This is to avoid pickling issues')

        shortcut = self._nninterface._shortcut(name)
        if shortcut:
            name = shortcut

        if not name in self._nninterface._nodes_and_leaves:
            raise AttributeError('%s is not part of your trajectory or it\'s tree.' % name)

        new_node = TreeNode(self._nninterface, name, self._fullname)

        return self._nninterface._find(new_node, self._dict_list)

    def to_dict(self, evaluate = False, short_names=False):
        ''' This method returns all parameters reachable from this node as a dict.
        The keys are the full names of the parameters and the values of the dict are the parameters
        themselves or the default evaluation of the parameters.
        :param evaluate: Boolean to determine whether the dictionary entries are parameter objects or the default
         evaluation of the parameter.
        :param short_names: Determines the keys of the result dictionary, if short_names is True, the keys are only
        the names of the Prameters (i.e. traj.group.param becomes only param). If there are dublicate entries, an Error
         is thrown.
        :return: A dictionary
        '''
        result_dict = {}
        for succesor_dict in self._dict_list:
            result_dict.update(self._walk_dict(succesor_dict, evaluate, short_names))

        return result_dict


    def _walk_dict(self, dictionary, evaluate, short_names):
        result_dict={}
        for val in dictionary.itervalues():
            if isinstance(val, dict):
                result_dict.update(self._walk_dict(val,evaluate, short_names))
            else:
                if short_names:
                    key = val.get_name()
                    if key in result_dict:
                        val2 = result_dict[key]
                        raise AttributeError('''Short name %s has been found twice, for %s as well as %s,
                        I don not know which one to take.''' % (key, val2.get_fullname(),val.get_fullname() ))
                else:
                    key = val.get_fullname()

                result_dict[key] = self._nninterface._get_result(val,evaluate)
        return result_dict


    def get(self, name, evaluate=False):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>evaluate<<.

        :param name: The Name of the Parameter,Result or TreeNode that is requested.
        :param evaluate: If the default evaluation of a parameter should be returned.
        :return: The requested object or it's default evaluation. Returns None if object could not be found.
        '''
        old_fast_access = self._nninterface._fast_access
        try:
            self._nninterface._fast_access = evaluate
            result = eval('self.' + name)
            self._nninterface._fast_access = old_fast_access
            return result
        except:
            self._nninterface._fast_access = old_fast_access
            self._nninterface._logger.warning('No parameter or result found in your trajectory with name %s.' %name)
            return None



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

    def __init__(self, name,  dynamicly_imported_classes=[], init_time=None):
    
        if init_time is None:
            init_time = time.time()


        
        formatted_time = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        
        self._time = init_time
        self._formatted_time = formatted_time


        self._name = name+'_'+str(formatted_time)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)
        
        self._parameters={}
        self._derivedparameters={}
        self._results={}
        self._exploredparameters={}
        self._config={}
        
        self._result_ids={} #the numbering of the results, only important if results have been

        self._changed_default_params={}
        
        #Even if there are no parameters yet length is 1 for convention
        self._length = 1
        
        self._nninterface = NaturalNamingInterface(working_trajectory_name=self._name, parent_trajectory_name = self._name)
        
        
        self._storageservice = None

        self._comment= Trajectory.standard_comment

        
        self.last = None
        self._standard_param_type = Parameter
        
        
        self._dynamic_imports=set(['mypet.parameter.SparseParameter'])
        self._dynamic_imports.update(dynamicly_imported_classes)
        
        self._loadedfrom = ('None','None')


    def set_storage_service(self, service):
        self._storageservice = service


    def change_config(self, config_name,*args,**kwargs):
        ''' Similar to change_parameter.
        '''
        config_name = 'Config'+'.'+config_name
        if config_name in self._config:
            self._configs[config_name].set(*args,**kwargs)
        else:
            self._changed_default_params[config_name] = (args,kwargs)

    def change_parameter(self, param_name,*args,**kwargs ):
        ''' Can be called before parameters are added to the Trajectory in order to change the values that are stored
        into the parameter.

        After creation of a Parameter, the instance of the parameter is called with param.set(*args,**kwargs).
        The prefix 'Parameters.' is also automatically added to 'param_name'. If the parameter already exists,
        when change_parameter is called, the parameter is changed directly.

        Before experiment is carried out it is checked if all changes are actually carried out.

        :param param_name: The name of the parameter that is to be changed after it's creation, the prefix 'Parameters.'
                            is automatically added, i.e. param_name = 'Parameters.'+param_name
        :param args:
        :param kwargs:
        :return:
        '''
        param_name = 'Parameters'+'.'+param_name
        if param_name in self._parameters:
            self._parameters[param_name].set(*args,**kwargs)
        else:
            self._changed_default_params[param_name] = (args,kwargs)

    def prepare_experiment(self):

        if len(self._changed_default_params):
            raise pex.DefaultReplacementError('The following parameters were supposed to replace a default value, but it was never tried to add default values with these names: %s' % str(self._changed_default_params))

        self.lock_parameters()
        self.lock_derived_parameters()
        self.store()

    def store(self):
        self._storageservice.store(self)


    def to_dict(self, evaluate = False, short_names=False):
        ''' This method returns all parameters reachable from this node as a dict.
        The keys are the full names of the parameters and the values of the dict are the parameters
        themselves or the default evaluation of the parameters.
        :param evaluate: Boolean to determine whether the dictionary entries are parameter objects or the default
         evaluation of the parameter.
        :return: A dictionary
        '''
        return self._nninterface.to_dict(evaluate, short_names)


    def __len__(self):
        return self._length


    def set_fast_access(self, val):
        assert isinstance(val,bool)
        self._nninterface._fast_access = val
    
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
        result['_exploredparameters'] = self._exploredparameters.copy()
        result['_config']=self._config.copy()
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

    def ar(self,*args,**kwargs):
        ''' Short for add_result.
        '''
        return self.add_result(*args, **kwargs)

    def add_result(self, *args,**kwargs):
        ''' Adds a result to the trajectory, 
        
        This is a rather open implementation the user can provide *args as well as **kwargs
        which will be fed to the init function of your result.
        
        If result_type is already the instance of a Result a new instance will not be created.
        Adding of naming is similar to DerivedParameters.
        
        Does not update the 'last' shortcut of the trajectory.
        '''
        prefix = 'Results.'+self._name+'.'

        if 'result' in kwargs or (args and isinstance(args[0], BaseResult)):
            if 'result' in kwargs:
                instance = kwargs.pop('result')
            else:
                instance = args.pop(0)
                instance._rename(prefix+instance.get_fullname())
                full_result_name = instance.get_fullname()

        elif 'result_name' in kwargs or (args and isinstance(args[0],str)):

            if 'result_name' in kwargs:
                full_result_name = kwargs.pop('result_name')
            else:
                full_result_name = args.pop(0)
                full_result_name = prefix+full_result_name

            if 'result_type' in kwargs or (args and isinstance(args[0], type) and issubclass(args[0], BaseResult)):
                if 'result_type' in kwargs:
                    result_type = kwargs.pop('result_type')
                else:
                    args = list(args)
                    result_type = args.pop(0)
                instance =  result_type(full_result_name,*args,**kwargs)
            else:
                raise AttributeError('No instance of a result or a result type is specified')
        else:
            raise AttributeError('You did not supply a new Result or a name for a new result')

        faulty_names = self._check_name(full_result_name)

        if faulty_names:
            raise AttributeError('Your Parameter %s contains the following not admittable names: %s please choose other names')


        if full_result_name in self._results:
            self._logger.warn(full_result_name + ' is already part of trajectory, I will replace it.')

        self._results[full_result_name] = instance
        
        self._nninterface._add_to_nninterface(full_result_name, instance)
        
        return instance

    def add_config(self, *args, **kwargs):
        return self._add_any_param('Config.',self._config,*args,**kwargs)

    def ac(self, *args, **kwargs):
        return self.add_config(*args,**kwargs)
        
    def adp(self,  *args,**kwargs):
        ''' Short for add_derived_parameter
        '''
        return self.add_derived_parameter( *args, **kwargs)



    def add_derived_parameter(self, *args,**kwargs):
        ''' Adds a new derived parameter. Returns the added parameter.
        
        :param full_parameter_name: The full name of the derived parameter. Grouping is achieved by colons'.'. The
        trajectory will add 'DerivedParameters' and the  name  of the current trajectory or run to the name. For
        example, the parameter named paramgroup.param1 which is  added in the current run
        Run_No_00000001_2013_06_03_17h40m24s becomes:
                            DerivedParameters.Run_No_00000001_2013_06_03_17h40m24s.paramgroup.param1
                                    
        :param param_type (or args[0]): The type of parameter, should be passed in **kwargs or as first entry in
        *args.n If not specified the standard parameter is chosen. Standard is the Parameter class,
        another example would be the SparseParameter class.
                            
        :param param (or args[0]):      If you already have an instance of the parameter you can pass it here,
        then the instance will be added to the trajectory instead of creating a new instance via calling instance =
        param(name,full_parameter_name), i.e. instance = param. Note that your added parameters will be renamed as
        mentioned above.
                            
        :param *args: Any kinds of desired parameter entries.
        
        :param **kwargs: Any kinds of desired parameter entries.
        
        Example use:
        >>> myparam=traj.add_derived_parameter(self, paramgroup.param1, param_type=Parameter, 
                                                entry1 = 42)
            
        >>> print myparam.entry1
        >>> 42
        '''

        return self._add_any_param('DerivedParameters.'+self._name+'.',self._derivedparameters,
                                   *args,**kwargs)

    def _add_any_param(self, prefix, where_dict, *args,**kwargs):

        args = list(args)

        if 'param' in kwargs or (args and isinstance( args[0],BaseParameter)):
            if 'param' in kwargs:
                instance = kwargs.pop('param')
            else:
                args = list(args)
                instance = args.pop(0)
                instance._rename(prefix+instance._fullname)
                full_parameter_name = instance.get_fullname()

        elif 'param_name' in kwargs or (args and isinstance(args[0],str)):

            if  'param_name' in kwargs:
                full_parameter_name = kwargs.pop('param_name')
            else:
                full_parameter_name = args.pop(0)

            full_parameter_name = prefix+full_parameter_name

            if not 'param_type' in kwargs:
                if args and isinstance(args[0], type) and issubclass(args[0] , BaseParameter):
                        args = list(args)
                        param_type = args.pop(0)
                else:
                    param_type = self._standard_param_type
            else:
                param_type = kwargs.pop('param_type')


            instance = param_type(full_parameter_name,*args, **kwargs)
        else:
            raise ValueError('You did not supply a new Parameter or a name for a new Parameter.')

        faulty_names = self._check_name(full_parameter_name)

        if faulty_names:
            raise AttributeError('Your Parameter %s contains the following not admittable names: %s please choose other names.'
                                 % (full_parameter_name, faulty_names))

        if full_parameter_name in where_dict:
            self._logger.warn(full_parameter_name + ' is already part of trajectory, I will replace the old one.')

        if full_parameter_name in self._changed_default_params:
            self._logger.info('You have marked parameter %s for change before, so here you go!' % full_parameter_name)
            change_args, change_kwargs = self._changed_default_params.pop(full_parameter_name)
            instance.set(*change_args,**change_kwargs)

        where_dict[full_parameter_name] = instance

        self._nninterface._add_to_nninterface(full_parameter_name, instance)

        self.last = instance
        
        return instance
    
    def _check_name(self, name):
        split_names = name.split('.')
        faulty_names = ''
        not_admissable_names = set(dir(self) + dir(self._nninterface) + dir(self._nninterface._root))

        for split_name in split_names:
            if split_name in not_admissable_names:
                faulty_names = '%s %s is a method/attribute of the trajectory/treenode/naminginterface,' \
                                %(faulty_names, split_name)

            if split_name[0] == '_':
                faulty_names = '%s %s starts with a leading underscore,' %(faulty_names,split_name)

        return faulty_names

    def ap(self, *args, **kwargs):
        ''' Short for add_parameter.
        '''
        return self.add_parameter( *args, **kwargs)
    
    def add_parameter(self,   *args, **kwargs):
        ''' Adds a new parameter. Returns the added parameter.

        :param full_parameter_name: The full name of the parameter. Grouping is achieved by colons'.'. The
        trajectory will add 'Parameters' to the name. For example, the parameter named paramgroup.param1 which is becomes:
                            Parameters.paramgroup.param1

        :param param_type (or args[0]): The type of parameter, should be passed in **kwargs or as first entry in
        *args.n If not specified the standard parameter is chosen. Standard is the Parameter class,
        another example would be the SparseParameter class.

        :param param (or args[0]):      If you already have an instance of the parameter you can pass it here,
        then the instance will be added to the trajectory instead of creating a new instance via calling instance =
        param(name,full_parameter_name), i.e. instance = param. Note that your added parameters will be renamed as
        mentioned above.

        :param *args: Any kinds of desired parameter entries.

        :param **kwargs: Any kinds of desired parameter entries.

        Example use:
        >>> myparam=traj.add_derived_parameter(self, paramgroup.param1, param_type=Parameter,
                                                entry1 = 42)
            
        >>> print myparam.entry1
        >>> 42
        '''

        
        return self._add_any_param('Parameters.',self._parameters, *args,**kwargs)
        

        
        
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
        return self._result_ids.copy()
    
    def get_results(self):
        return self._results.copy()
    
    def get_explored_params(self):  
        return self._exploredparameters.copy()
             
    def get(self, name, evaluate=False):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>evaluate<<.

        :param name: The Name of the Parameter,Result or TreeNode that is requested.
        :param evaluate: If the default evaluation of a parameter should be returned.
        :return: The requested object or it's default evaluation. Returns None if object could not be found.
        '''
        return self._nninterface.get(name, evaluate)


    def prepare_paramspacepoint(self,n):
        ''' Notifies the explored parameters what the current point in the parameter space it is,
        i.e. which is the current run.
        '''

        # extract only one particular paramspacepoint
        for key,val in self._exploredparameters.items():
            val.set_parameter_access(n)


     
    def make_single_run(self,n):
        ''' Creates a SingleRun object for parameter exploration.
        
        The SingleRun object can used as the parent trajectory. The object contains a shallow
        copy of the parent trajectory but wihtout parameter arrays. From every array only the 
        nth parameter is used.
        '''
        return SingleRun(self, n)

    def __getattr__(self,name):
        
        if not '_nninterface' in self.__dict__:
            raise AttributeError('This is to avoid pickling issues!')
   
        return getattr(self._nninterface, name)


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
    
    def __init__(self, parent_trajectory,  n):
        
        assert isinstance(parent_trajectory, Trajectory)



        self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%Hh%Mm%Ss')

        self._n = n
        
        name = 'Run_No_%08d' % n
        self._parent_trajectory = parent_trajectory
        self._parent_trajectory.prepare_paramspacepoint(n)

        self._storageservice = self._parent_trajectory._storageservice

        self._single_run = Trajectory(name, parent_trajectory._dynamic_imports)
        self._single_run.set_storage_service(self._storageservice)
        
        self._nninterface = self._parent_trajectory._nninterface
        self.last = self._parent_trajectory.last

        del self._single_run._nninterface
        self._single_run._nninterface = self._nninterface
        self._single_run._standard_param_type = self._parent_trajectory._standard_param_type
        
        self._nninterface._parent_trajectory_name = self._parent_trajectory.get_name()
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
        return self.add_derived_parameter( *args, **kwargs)
        
    def add_derived_parameter(self, *args, **kwargs):
        self.last= self._single_run.add_derived_parameter(*args, **kwargs)
        return self.last

    
    def ap(self, *args, **kwargs):
        ''' Short for add_parameter.
        '''
        return self.add_parameter(*args, **kwargs)
    
    
    def add_parameter(self, *args, **kwargs):
        ''' Adds a DERIVED Parameter to the trajectory and emits a warning.
        ''' 
        self._logger.warn('Cannot add Parameters anymore, yet I will add a derived Parameter.')
        return self.add_derived_parameter( *args, **kwargs)

    def get(self, name):
        return self._nninterface.get(name)

    def __getattr__(self,name):
        
        if not '_nninterface' in self.__dict__:
            raise AttributeError('This is to avoid pickling issues!')
        
        return getattr(self._nninterface, name)
        
    def get(self, name):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Even if fast access is True,
        get will return a parameter object and not the parameter's default evaluation.

        :param name: The Name of the Parameter,Result or TreeNode that is requested.
        :return: The requested object. Returns None if object could not be found.
        '''
        return self._nninterface.get(name)

    def get_parent_name(self):
        return self._parent_trajectory.get_name()
    
    def get_name(self):
        return self._single_run.get_name()

    def ar(self,*args,**kwargs):
        return self.add_result(*args,**kwargs)

    def add_result(self,  *args,**kwargs):
        return self._single_run.add_result( *args,**kwargs)
    
    def set_fast_access(self,val):
        assert isinstance(val, bool)
        self._nninterface._fast_access=val
        
#     def set_double_checking(self,val):
#         assert isinstance(val, bool)
#         self._nninterface._double_checking=val
        
    def store(self, lock=None):
        ''' Stores all obtained results a new derived parameters to the hdf5file.
        
        In case of multiprocessing a lock needs to be provided to prevent hdf5file corruption!!!
        '''
        self._add_explored_params()
        self._storageservice.store(self, lock=lock)
        

    def to_dict(self, evaluate = False, short_names=False):
        ''' This method returns all parameters reachable from this node as a dict.
        The keys are the full names of the parameters and the values of the dict are the parameters
        themselves or the default evaluation of the parameters.
        :param evaluate: Boolean to determine whether the dictionary entries are parameter objects or the default
         evaluation of the parameter.
        :param short_names: Determines the keys of the result dictionary, if short_names is True, the keys are only
        the names of the Prameters (i.e. traj.group.param becomes only param). If there are dublicate entries, an Error
         is thrown.
        :return: A dictionary
        '''
        return self._nninterface.to_dict(evaluate, short_names)

    def _add_explored_params(self):
        ''' Stores the explored parameters as a Node in the HDF5File under the results nodes for easier comprehension of the hdf5file.
        '''
        for fullname,param in self._parent_trajectory._exploredparameters.items():
            splitname = fullname.split('.')
            
            #remove the Parameters tag
            splitname = ['ExploredParameters']+splitname[1:]
            newfullname = '.'.join(splitname)


            param_dict = {}
            keys = param.get_entry_names()
            for key in keys:
                param_dict[key] = param.get(key)

            self.add_result(full_result_name=newfullname, result_type=SimpleResult, **param_dict)
            
