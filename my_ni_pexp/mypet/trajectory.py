'''
Created on 17.05.2013

@author: robert
'''

import logging
import datetime
import time
from lxml.etree import _Validator
from mypet.parameter import Parameter, BaseParameter, SimpleResult, BaseResult, ArrayParameter, PickleResult
import importlib as imp

import mypet.petexceptions as pex
from mypet.utils.helpful_functions import flatten_dictionary
from mypet import globally

class TrajOrRun(object):



    def set_search_strategy(self, string):
        assert string == 'bfs' or string == 'dfs'
        self._nninterface._search_strategy = string

    def set_check_uniqueness(self, val):
        assert isinstance(val,bool)
        self._nninterface._check_uniqueness = val

    def set_storage_service(self, service):
        self._storageservice = service

    def set_fast_access(self, val):
        assert isinstance(val,bool)
        self._nninterface._fast_access = val

    def add_parameter(self,   *args, **kwargs):
        pass

    def adp(self,  *args,**kwargs):
        ''' Short for add_derived_parameter
        '''
        return self.add_derived_parameter( *args, **kwargs)

    def ar(self,*args,**kwargs):
        ''' Short for add_result.
        '''
        return self.add_result(*args, **kwargs)

    def ap(self, *args, **kwargs):
        ''' Short for add_parameter.
        '''
        return self.add_parameter( *args, **kwargs)

    def get(self, name, fast_access=False, check_uniqueness = False, search_strategy = 'bfs'):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>fast_access<<.

        :param name: The Name of the Parameter,Result or TreeNode that is requested.
        :param fast_access: If the default evaluation of a parameter should be returned.
        :param check_uniqueness: If search through the Parameter tree should be stopped after finding an entry or
        whether it should be chekced if the path through the tree is not unique.
        :param: search_strategy: The strategy to search the tree, either breadth first search ('bfs') or depth first
        seach ('dfs').
        :return: The requested object or it's default evaluation. Raises an error if the object cannot be found.
        '''
        return self._nninterface._get(name, fast_access, check_uniqueness, search_strategy)

    def get_storage_service(self):
        return self._storageservice

    def to_dict(self, fast_access = False, short_names=False):
        ''' This method returns all parameters reachable from this node as a dict.
        The keys are the full names of the parameters and the values of the dict are the parameters
        themselves or the default evaluation of the parameters.
        :param fast_access: Boolean to determine whether the dictionary entries are parameter objects or the default
         evaluation of the parameter.
        :return: A dictionary
        '''
        return self._nninterface._to_dict(fast_access, short_names)


    def __getattr__(self,name):

        #if not '_nninterface' in self.__dict__:
        if not '_logger' in self.__dict__ or not '_nninterface' in self.__dict__:
            raise AttributeError('This is to avoid pickling issues.')

        return self.get(name, fast_access = self._nninterface._fast_access,
                        check_uniqueness=self._nninterface._check_uniqueness,
                        search_strategy=self._nninterface._search_strategy)

    def __setattr__(self, key, value):
        if key[0]=='_':
            self.__dict__[key] = value
        elif key == 'last' or key == 'Last':
            self.__dict__[key]=value
        else:
            self._nninterface._set(key, value)


    def _fetch_items(self, stuff_list, kwargs):


        only_empties = kwargs.pop('only_empties',False)

        non_empties = kwargs.pop('non_empties',False)


        if not isinstance(stuff_list,list):
            stuff_list=[stuff_list]

        item_list = []
        for arg in stuff_list:
            if isinstance(arg, str):
                item = self.get(arg)
            else:
                item = arg

            if isinstance(item,TreeNode):
                raise ValueError('One of the items you want to store or loead is a Tree Node, but Tree Nodes cannot be stored or loaded!')

            if only_empties and not item.is_empty():
                continue
            if non_empties and item.is_empty():
                continue

            item_list.append(item)
        return item_list

    def get_full_param_name(self, param_name):
        param = self.get(param_name)
        return param.gfn()

    def gfpn(self, param_name):
        return self.get_full_param_name(param_name)

    def remove(self, removal_list):

        if not isinstance(removal_list,list):
            removal_list = [removal_list]

        for item in removal_list:
            if isinstance(item, (BaseParameter,BaseResult)):
                instance = item
            elif isinstance(item, str):
                instance = self.get(item,fast_access=False)
            else:
                raise ValueError('This aint working bro, I do not know what %s is.' % str(item))

            fullname = instance.get_fullname()
            self._remove(fullname)
            self._nninterface._remove(fullname)

class NaturalNamingInterface(object):

    
    def __init__(self, working_trajectory_name, parent_trajectory_name, fast_access = True,
                 check_uniqueness=False,search_strategy = 'bfs', storage_dict = None,
                 flat_storage_dict=None,nodes_and_leaves = None):
        self._fast_access = fast_access
        self._check_uniqueness = check_uniqueness
        self._search_strategy = search_strategy
        self._working_trajectory_name=working_trajectory_name
        self._parent_trajectory_name=parent_trajectory_name
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._working_trajectory_name)

        self._storage_dict = storage_dict
        if self._storage_dict == None:
            self._storage_dict={}

        self._flat_storage_dict = flat_storage_dict
        if self._flat_storage_dict == None:
            self._flat_storage_dict = {}

        self._nodes_and_leaves = nodes_and_leaves
        if self._nodes_and_leaves == None:
            self._nodes_and_leaves = {}

        self._root = TreeNode(self)



    def _to_dict(self, fast_access = False, short_names=False):
        return self._root.to_dict(fast_access, short_names)



    def _remove(self, fullname):
        split_name = fullname.split('.')
        self._remove_recursive(split_name,self._storage_dict)
        del self._flat_storage_dict[fullname]

    def _remove_recursive(self,split_name, dictionary):

        key = split_name.pop(0)
        new_item = dictionary[key]
        delete = False

        if isinstance(new_item,dict):
            self._remove_recursive(split_name,new_item)
            if len(new_item)==0:
                delete = True
        else:
            delete = True

        if delete:
            del new_item
            del dictionary[key]

            self._nodes_and_leaves[key] = self._nodes_and_leaves[key]-1
            if self._nodes_and_leaves[key] == 0:
                del self._nodes_and_leaves[key]





    def _get(self, name, fast_access = False, check_uniqueness = False, search_strategy = 'bfs'):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>fast_access<<.

        :param name: The Name of the Parameter,Result or TreeNode that is requested.
        :param fast_access: If the default evaluation of a parameter should be returned.
        :return: The requested object or it's default evaluation. Returns None if object could not be found.
        '''
        return self._root.get(name, fast_access, check_uniqueness, search_strategy)


    def _shortcut(self, name):
        
        expanded = None
        
        if name in ['cr', 'CurrentRun', 'currentrun', 'Current_Run', 'current_run']:
            expanded= self._working_trajectory_name

        if name in ['par', 'Par']:
            expanded = 'parameters'

        if name in ['dpar', 'DPar']:
            expanded = 'derived_parameters'

        if name in ['Res', 'res']:
            expanded='results'

        if name in ['conf', 'Conf']:
            expanded = 'config'
        
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
        self._flat_storage_dict[fullname] = data

        split_name.append(leaf) 
        
        for name in split_name:
            if name in self._nodes_and_leaves:
                self._nodes_and_leaves[name] = self._nodes_and_leaves[name] +1
            else:
                self._nodes_and_leaves[name] =1
            #self._nodes_and_leaves.add(name)
        
    
    def _add_to_storage_dict(self, where_list, leaf, data):
        act_dict = self._storage_dict
        for name in where_list:
            if not name in act_dict:
                act_dict[name] ={}

            act_dict = act_dict[name]
        
        if leaf in act_dict and isinstance(act_dict[leaf], dict):
            raise AttributeError('Your addition does not work, you would have a tree node called %s as well as a leaf containing data, both hanging below %s.' % (leaf,name))
                
        act_dict[leaf] = data
            

    def _shallow_copy(self):
        newNNinterface = NaturalNamingInterface(working_trajectory_name=self._working_trajectory_name,
                                                parent_trajectory_name=self._parent_trajectory_name,
                                                fast_access=self._fast_access,
                                                check_uniqueness= self._check_uniqueness,
                                                search_strategy= self._search_strategy,
                                                storage_dict= self._recursive_shallow_copy(self._storage_dict),
                                                flat_storage_dict=self._flat_storage_dict.copy(),
                                                nodes_and_leaves= self._nodes_and_leaves.copy())
        return newNNinterface

        
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        del result['_root'] 
        #result['_storage_dict'] = self._recursive_shallow_copy(self._storage_dict)
        #result['_nodes_and_leaves'] = self._nodes_and_leaves.copy()
        return result

    def _set(self,key,val):

        setattr(self._root,key,val)
    
    def _recursive_shallow_copy(self, dictionary):
        
        new_dict = dictionary.copy()
        for key, val in dictionary.items():
            if isinstance(val, dict):
                new_dict[key] = self._recursive_shallow_copy(val)
        
        return new_dict
    
    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' +  self._working_trajectory_name)
        self._root = TreeNode(nninterface=self)



    def _get_result(self, data, fast_access):

        if fast_access and isinstance(data, BaseParameter) and not isinstance(data, BaseResult):
            return data.get()
        else:
            return data

    def _search(self,fullname,key,dictionary, check_uniqueness, search_strategy):

        assert (search_strategy == 'bfs' or search_strategy == 'dfs')
        check_list = [dictionary]
        result = None

        while len(check_list) > 0:

            if search_strategy == 'bfs':
                new_dict = check_list.pop(0)
            elif search_strategy == 'dfs':
                new_dict = check_list.pop()
            else:
                raise RuntimeError('You should never come here!')

            if key in new_dict:
                if not result == None:
                    raise AttributeError('The node or parameter/result %s is not uniqe.' % fullname)
                else:
                    result = new_dict[key]
                    if not check_uniqueness :
                        return result
            else:
                for val in new_dict.itervalues():
                    if isinstance(val,dict):
                        check_list.append(val)

        return result

            

class TreeNode(object):
    '''Object to construct the file tree.

    The recursive structure allows access to parameters via natural naming.
    '''
    def __init__(self, nninterface, fullname='', dictionary = None):

        self._fullname = fullname
        self._nninterface = nninterface

        if fullname == '':
            self._dict =self._nninterface._storage_dict
        else:
            self._dict=dictionary


    def __getattr__(self,name):

        if (not  '_nninterface' in self.__dict__ or
            not  '_fullname' in self.__dict__ or
            not '_dict' in self.__dict__ or
            not 'get' in self.__class__.__dict__ or
            name[0]=='_'):
            raise AttributeError('Wrong attribute %s. (And you this statement prevents pickling problems)' % name)

        return self.get(name,self._nninterface._fast_access, self._nninterface._check_uniqueness,
                        self._nninterface._search_strategy)


    def __setattr__(self, key, value):
        if key[0]=='_':
            self.__dict__[key] = value
        else:
            instance = self.get(key)

            if not isinstance(instance, BaseParameter ):
                raise AttributeError('You cannot assign values to a tree node or a list of nodes and leaves, it only works for parameters (excluding results).')


            instance.set(value)


    def to_dict(self, fast_access = False, short_names=False):

        temp_dict = flatten_dictionary(self._dict,'.')

        result_dict={}
        if short_names or fast_access:
            for key in temp_dict:
                val = temp_dict[key]

                if short_names:

                    newkey = key.split('.')[-1]

                    if newkey in result_dict:
                        raise ValueError('Cannot make short names, the names are not unique!')

                else:
                    newkey = key

                newval = self._nninterface._get_result(val,fast_access=fast_access)
                result_dict[newkey]=newval
        else:
            result_dict = temp_dict

        return result_dict



    def get(self, name, fast_access=False, check_uniqueness = False, search_strategy = 'bfs'):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>fast_access<<.

        :param name: The Name of the Parameter,Result or TreeNode that is requested.
        :param fast_access: If the default evaluation of a parameter should be returned.
        :param check_uniqueness: If search through the Parameter tree should be stopped after finding an entry or
        whether it should be chekced if the path through the tree is not unique.
        :param: search_strategy: The strategy to search the tree, either breadth first search ('bfs') or depth first
        seach ('dfs').
        :return: The requested object or it's default evaluation. Raises an error if the object cannot be found.
        '''


        split_name = name.split('.')


        ## Rename shortcuts and check keys:
        for idx,key in enumerate(split_name):
            shortcut = self._nninterface._shortcut(key)
            if shortcut:
                key = shortcut
                split_name[idx] = key

            if key[0] == '_':
                raise AttributeError('Leading underscores are not allowed for group or parameter names. Cannot return %s.' %key)

            if not key in self._nninterface._nodes_and_leaves:
                raise AttributeError('%s is not part of your trajectory or it\'s tree.' % name)


        ## Check in O(1) first if a full parameter/result name is given
        fullname = '.'.join(split_name)
        if self._fullname=='':
            new_name = fullname
        else:
            new_name = self._fullname+'.'+fullname

        if new_name in self._nninterface._flat_storage_dict:
            return self._nninterface._get_result(self._nninterface._flat_storage_dict[new_name],
                                                 fast_access=fast_access)

        ## Check in O(N) [Worst Case, Average Case is better since looking into a single dict costs O(1)] BFS or DFS
        ## If check Uniqueness == True, search is slower since the full dictionary is always searched
        result = self._dict
        for key in split_name:
            result =  self._nninterface._search(new_name,key, result, check_uniqueness, search_strategy)

        if isinstance(result,dict):
            return TreeNode(self._nninterface,new_name,result)
        elif not result == None:
            return self._nninterface._get_result(result,fast_access)
        else:
            raise AttributeError('The node or param/result >>%s<<, cannot be found.' % new_name)







class Trajectory(TrajOrRun):
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
                                      dynamicly_imported_classes=['mypet.parameter.PickleParameter']
                                      (Note that in __init__ the PickleParameter is actually added
                                      to the potentially dynamically loaded classes.)
                                      
    :param init_time: The time exploration was started, float, in seconds from linux start, e.g. 
                     from time.time()
    
                                      
    As soon as a parameter is added to the trajectory it can be accessed via natural naming:
    >>> traj.add_parameter('paramgroup.param1')
    
    >>> traj.parameters.paramgroup.param1.entry1 = 42
    
    >>> print traj.parameters.paramgroup.param1.entry1
    >>> 42
    
    Derived parameters are stored under the group derived_parameters.Name_of_trajectory_or_run.
    
    There are several shortcuts implemented. The expression traj.derived_parameters.pwt
    maps to derived_parameters.Name_of_current_trajectory_or_run.
    
    If no main group like 'results','parameters','derived_parameters' is specified, 
    like accessing traj.paramgroup.param1
    It is first checked if paramgroup.param1 can be found in the derived_parameters, if not is looked 
    for in the parameters. 
    For example, traj.paramgroup.param1 would map to print traj.parameters.paramgroup.param1                     
    '''
    

    
    standard_comment = 'Dude, do you not want to tell us your amazing story about this trajectory?'

    def __init__(self, name='Traj',  dynamicly_imported_classes=None, init_time=None):
    
        if init_time is None:
            init_time = time.time()


        
        formatted_time = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        
        self._time = init_time
        self._formatted_time = formatted_time


        self._name = name+'_'+str(formatted_time)

        self._parameters={}
        self._derivedparameters={}
        self._results={}
        self._exploredparameters={}
        self._config={}

        self._changed_default_params = {}
        
        self._id_to_dpar={} #the numbering of the results, only important if results have been
        self._dpar_to_id={}
        self._id_to_res={}
        self._res_to_id={}
        
        #if there are no parameters in the trajectory the length is 0 otherwise the lenght of the trajectory
        # is the size of the explored parameters
        self._length = 0
        
        self._nninterface = NaturalNamingInterface(working_trajectory_name=self._name, parent_trajectory_name = self._name)
        
        
        self._storageservice = None

        self._comment= Trajectory.standard_comment

        
        self.last = None
        self.Last = None


        self._standard_param_type = Parameter
        self._standard_result_type = SimpleResult
        
        
        self._dynamic_imports=set(['mypet.parameter.PickleParameter'])
        if not dynamicly_imported_classes == None:
            self._dynamic_imports.update(dynamicly_imported_classes)
        
        self._loadedfrom = 'None'

        self._not_admissable_names = set(dir(self) + dir(self._nninterface) + dir(self._nninterface._root))
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)





    def _remove(self,fullname):

        split_name = fullname.split('.')
        category = split_name[0]
        if category == 'results':
            del self._results[fullname]
        elif category == 'parameters':
            del self._parameters[fullname]
        elif category == 'derived_parameters':
            del self._derivedparameters[fullname]
        elif category == 'config':
            del self._config[fullname]
        else:
            raise RuntimeError('You should nover come here :eeek:')

        if fullname in self._exploredparameters:
            del self._exploredparameters[fullname]

        if len(self._parameters) == 0 and len(self._derivedparameters) == 0:
            self._length = 0
        else:
            if len(self._exploredparameters)== 0:
                self._length = 1

        self._logger.debug('Removed %s from trajectory.' %fullname)



    def change_config(self, config_name,*args,**kwargs):
        ''' Similar to change_parameter.
        '''
        config_name = 'config'+'.'+config_name
        if config_name in self._config:
            self._config[config_name].set(*args,**kwargs)
        else:
            self._changed_default_params[config_name] = (args,kwargs)

    def change_parameter(self, param_name,*args,**kwargs ):
        ''' Can be called before parameters are added to the Trajectory in order to change the values that are stored
        into the parameter.

        After creation of a Parameter, the instance of the parameter is called with param.set(*args,**kwargs).
        The prefix 'parameters.' is also automatically added to 'param_name'. If the parameter already exists,
        when change_parameter is called, the parameter is changed directly.

        Before experiment is carried out it is checked if all changes are actually carried out.

        :param param_name: The name of the parameter that is to be changed after it's creation, the prefix 'parameters.'
                            is automatically added, i.e. param_name = 'parameters.'+param_name
        :param args:
        :param kwargs:
        :return:
        '''
        param_name = 'parameters'+'.'+param_name
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





    def __len__(self):
        return self._length



    
#     def set_double_checking(self, val):
#         assert isinstance(val,bool)
#         self._nninterface._double_checking=val
    

    
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
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


    def get_comment(self):
        return self._comment

    def add_result(self, *args,**kwargs):
        ''' Adds a result to the trajectory, 
        
        This is a rather open implementation the user can provide *args as well as **kwargs
        which will be fed to the init function of your result.
        
        If result_type is already the instance of a Result a new instance will not be created.
        Adding of naming is similar to derived_parameters.
        
        Does not update the 'last' shortcut of the trajectory.
        '''
        prefix = 'results.'+self._name+'.'
        args = list(args)


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

            if not 'result_type' in kwargs:
                if args and isinstance(args[0], type) and issubclass(args[0] , BaseResult):
                        args = list(args)
                        result_type = args.pop(0)
                else:
                    result_type = self._standard_result_type
            else:
                result_type = kwargs.pop('result_type')

            instance = result_type(full_result_name,*args, **kwargs)
        else:
            raise RuntimeError('You did not supply a new Result or a name for a new result')

        faulty_names = self._check_name(full_result_name)

        if faulty_names:
            raise AttributeError('Your Parameter %s contains the following not admittable names: %s please choose other names')


        if full_result_name in self._results:
            self._logger.warn(full_result_name + ' is already part of trajectory, I will replace it.')

        self._results[full_result_name] = instance
        
        self._nninterface._add_to_nninterface(full_result_name, instance)

        
        return instance

    def add_config(self, *args, **kwargs):
        return self._add_any_param('config.',self._config,*args,**kwargs)

    def ac(self, *args, **kwargs):
        return self.add_config(*args,**kwargs)
        



    def set_standard_param_type(self,param_type):
        ''' Sets the standard parameter type.

        If param_type is not specified for add_parameter, than the standard parameter is used.
        '''
        assert issubclass(param_type,BaseParameter)
        self._standard_param_type = param_type


    def set_standard_result_type(self, result_type):
        ''' Sets the standard parameter type.

        If result_type is not specified for add_result, than the standard result is used.
        '''
        assert issubclass(result_type,BaseResult)
        self._standard_result_type=result_type

    def add_derived_parameter(self, *args,**kwargs):
        ''' Adds a new derived parameter. Returns the added parameter.
        
        :param full_parameter_name: The full name of the derived parameter. Grouping is achieved by colons'.'. The
        trajectory will add 'derived_parameters' and the  name  of the current trajectory or run to the name. For
        example, the parameter named paramgroup.param1 which is  added in the current run
        run_No_00000001_2013_06_03_17h40m24s becomes:
                            derived_parameters.run_No_00000001_2013_06_03_17h40m24s.paramgroup.param1
                                    
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

        return self._add_any_param('derived_parameters.'+self._name+'.',self._derivedparameters,
                                   *args,**kwargs)

    def _add_any_param(self, prefix, where_dict, *args,**kwargs):

        args = list(args)

        if 'param' in kwargs or (args and isinstance( args[0],BaseParameter)):
            if 'param' in kwargs:
                instance = kwargs.pop('param')
            else:
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
            raise RuntimeError('You did not supply a new Parameter or a name for a new Parameter.')

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
        self.Last = instance

        self._logger.debug('Added >>%s<< to trajectory.' %full_parameter_name)

        # If a parameter is added for the first time, the length is set to 1
        if len(self) == 0:
            self._length = 1

        return instance
    
    def _check_name(self, name):
        split_names = name.split('.')
        faulty_names = ''

        for split_name in split_names:
            if split_name in self._not_admissable_names:
                faulty_names = '%s %s is a method/attribute of the trajectory/treenode/naminginterface,' \
                                %(faulty_names, split_name)

            if split_name[0] == '_':
                faulty_names = '%s %s starts with a leading underscore,' %(faulty_names,split_name)

            if ' ' in split_name:
                faulty_names = '%s %s contains white space(s),' %(faulty_names,split_name)


        return faulty_names


    
    def add_parameter(self,   *args, **kwargs):
        ''' Adds a new parameter. Returns the added parameter.

        :param full_parameter_name: The full name of the parameter. Grouping is achieved by colons'.'. The
        trajectory will add 'parameters' to the name. For example, the parameter named paramgroup.param1 which is becomes:
                            parameters.paramgroup.param1

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

        
        return self._add_any_param('parameters.',self._parameters, *args,**kwargs)
        

        
        
    def _split_dictionary(self, tosplit_dict):
        ''' Converts a dictionary containing full parameter entry names into a nested dictionary.
        
        The input dictionary {'parameters.paramgroup1.param1.entry1':42 , 
                              'parameters.paramgroup1.param1.entry2':43,
                              'parameters.paramgroup1.param2.entry1':44} will produce the return of
        
        {'parameters.paramgroup1':{'entry1':42,'entry2':43}, 
         'parameters.paramgroup1.param2' : {'entry1':44}}
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
        {'parameters.paramgroup1.param1.entry1':[21,21,21,42,42,42],
         'parameters.paramgroup1.param2.entry1' : [1.0, 2.0, 3.0, 1.0, 2.0, 3.0]}
         
         which would be the Cartesian product of [21,42] and [1.0,2.0,3.0].

        These values are added to the stored parameters and param1 and param2 would become arrays.
        '''
        build_dict = build_function(*args,**kwargs) 
        
        # if the builder function returns tuples, the first element must be the build dictionary
        if isinstance(build_dict, tuple):
            build_dict, dummy = build_dict
        
        #split_dict = self._split_dictionary(build_dict)
            
        count = 0#Don't like it but ok
        for key, buildlist in build_dict.items():
            act_param = self.get(key,check_uniqueness=True)
            if isinstance(act_param,TreeNode):
                raise ValueError('%s is not an appropriate search string for a parameter.' % key)

            act_param.explore(buildlist)

            name = act_param.gfn()
            self._exploredparameters[name] = self._parameters[name]

            
            if count == 0:
                self._length = len(self._parameters[name])#Not so nice, but this should always be the same numbert
            else:
                if not self._length == len(self._parameters[name]):
                    raise ValueError('The parameters to explore have not the same size!')
       
            
        
            
    def lock_parameters(self):
        for key, par in self._parameters.items():
            par.lock()
    
    def lock_derived_parameters(self):
        for key, par in self._derivedparameters.items():
            par.lock()

    def finalize_experiment(self):
        for key, param in self._exploredparameters.items():
            param.restore_default()
            
    def update_skeleton(self):
        self.load(self.get_name(),False,globally.UPDATE_SKELETON,globally.UPDATE_SKELETON,
                  globally.UPDATE_SKELETON)

    def load_stuff(self, to_load_list, *args,**kwargs):
        ''' Loads parameters specified in >>to_load_list<<. You can directly list the Parameter objects or their
        names.
        If names are given the >>get<< method is applied to find the parameter or result in the trajectory.
        If kwargs contains the keyword >>only_empties=True<<, only empty parameters or results are passed to the
        storage service to get loaded.
        :param to_load_list: A list with parameters or results to store.
        :param args: Additional arguments directly passed to the storage service
        :param kwargs: Additional keyword arguments directly passed to the storage service (except the kwarg
        non_empties)
        :return:
        '''
        item_list = self._fetch_items(to_load_list, kwargs)

        self._storageservice.load(item_list,trajectoryname=self.get_name(),*args,**kwargs)

    def store_stuff(self, to_store_list, *args, **kwargs):
        ''' Stores parameters specified in >>to_load_list<<. You can directly list the Parameter objects or their
        names.
        If names are given the >>get<< method is applied to find the parameter or result in the trajectory.
        If kwargs contains the keyword >>non_empties=True<<, only non-empty parameters or results are passed to the
        storage service to get stored.
        :param to_load_list: A list with parameters or results to store.
        :param args: Additional arguments directly passed to the storage service
        :param kwargs: Additional keyword arguments directly passed to the storage service (except the kwarg
        non_empties)
        :return:
        '''
        item_list = self._fetch_items(to_store_list, kwargs)

        self._storageservice.store(item_list,trajectoryname=self.get_name(),*args,**kwargs)

    def load(self,
             trajectoryname=None,
             replace=False,
             load_params = globally.LOAD_DATA,
             load_derived_params = globally.LOAD_SKELETON,
             load_results = globally.LOAD_SKELETON,
             *args, **kwargs):

        if not trajectoryname:
            trajectoryname = self.get_name()

        self._storageservice.load(self,trajectoryname=trajectoryname, replace=replace, load_params=load_params,
                                  load_derived_params=load_derived_params,
                                  load_results=load_results,
                                  *args,**kwargs)

    def store(self, *args, **kwargs):
        ''' Stores all obtained results a new derived parameters to the hdf5file.
        '''
        #self._add_explored_params()
        self._storageservice.store(self,trajectoryname=self.get_name(), *args, **kwargs)

    def is_empty(self):
        return (len(self._parameters) == 0 and
                len(self._derivedparameters) == 0 and
                len(self._results) == 0)


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

    
    def get_id_dicts(self):

        id_to_res = {}
        for key, val in self._id_to_res.items():
            self._id_to_res[key] = val.copy()

        id_to_dpar = {}

        for key, val in self._id_to_dpar.items():
            self._id_to_dpar[key] = val.copy()

        return id_to_dpar, self._dpar_to_id.copy(), id_to_res, self._res_to_id.copy()
    
    def get_results(self):
        return self._results.copy()
    
    def get_explored_params(self):  
        return self._exploredparameters.copy()
             



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





class SingleRun(TrajOrRun):
    ''' Constitutes one specific parameter combination in the whole trajectory.
    
    A SingleRun instance is accessed during the actual run phase of a trajectory. 
    There exists a SignleRun object for each point in the parameter space.
    The object contains a shallow and reduced copy of the trajectory. From each parameter array
    only the nth parameter can be accesses.
    
    parameters can no longer be added, the parameter set is supposed to be complete before
    a the actual running of the experiment. However, derived parameters can still be added.
    This might be useful, for example, to store a connectivity matrix of neural network,
    that is built new for point in the trajectory.
    
    Natural Naming applies as before. For convenience a SingleRun object is still named traj:
    >>> print traj.parameters.paramgroup1.param1.entry1
    >>> 42
    
    There are several shortcuts through the parameter tree.
    >>> pint traj.paramgroup1.param1.entry
    
    Would first look for a parameter paramgroup1.param1 in the derived parameters of the current
    run, next the derived parameters of the trajectory would be checked, if that was not 
    successful either, the parameters of the trajectory are searched.
    
    The instance of a SingleRun is never instantiated by the user but by the parent trajectory.
    From the trajectory it gets assigned the current hdf5filename, a link to the parent trajectory,
    and the corresponding index n within the trajectory, i.e. the index of the parameter space point.
    '''
    
    def __init__(self, parent_trajectory,  n):
        
        assert isinstance(parent_trajectory, Trajectory)



        self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%Hh%Mm%Ss')

        self._n = n
        
        name = 'run_No_%08d' % n
        self._parent_trajectory = parent_trajectory
        self._parent_trajectory.prepare_paramspacepoint(n)

        self._storageservice = self._parent_trajectory._storageservice

        self._single_run = Trajectory(name, parent_trajectory._dynamic_imports)
        self._single_run.set_storage_service(self._storageservice)
        
        self._nninterface = self._parent_trajectory._nninterface._shallow_copy()
        self.last = self._parent_trajectory.last
        self.Last = self._parent_trajectory.Last

        #del self._single_run._nninterface
        self._single_run._nninterface = self._nninterface
        self._single_run._standard_param_type = self._parent_trajectory._standard_param_type
        self._single_run._standard_result_type = self._parent_trajectory._standard_result_type
        
        self._nninterface._parent_trajectory_name = self._parent_trajectory.get_name()
        self._nninterface._working_trajectory_name = self._single_run.get_name()

        self._logger = logging.getLogger('mypet.trajectory.SingleRun=' + self._single_run.get_name())


    def __len__(self):
        ''' Length of a single run can only be 1 and nothing else!
        :return:
        '''
        return 1

    def get_parent_name(self):
        return self._parent_trajectory.get_name()

    def get_n(self): 
        return self._n   
           
        
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        return result
    
    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.trajectory.SingleRun=' + self._single_run.get_name())

        
    def add_derived_parameter(self, *args, **kwargs):
        self.last= self._single_run.add_derived_parameter(*args, **kwargs)
        self.Last = self.last
        return self.last


    
    
    def add_parameter(self, *args, **kwargs):
        ''' Adds a DERIVED Parameter to the trajectory and emits a warning.
        ''' 
        self._logger.warn('Cannot add parameters anymore, yet I will add a derived Parameter.')
        return self.add_derived_parameter( *args, **kwargs)


    def __getattr__(self,name):

        #if not '_nninterface' in self.__dict__:
        if not '_logger' in self.__dict__ or not '_nninterface' in self.__dict__:
            raise AttributeError('This is to avoid pickling issues.')


        return self.get(name, fast_access=self._nninterface._fast_access)

    def get_parent_name(self):
        return self._parent_trajectory.get_name()
    
    def get_name(self):
        return self._single_run.get_name()

    def add_result(self,  *args,**kwargs):
        return self._single_run.add_result( *args,**kwargs)





    def _remove(self,fullname):

        split_name = fullname.split('.')
        category = split_name[0]
        traj_name = split_name[1]
        if category == 'results':
            if traj_name == self.get_name():
                del self._single_run._results[fullname]
            else:
                raise ValueError('You cannot remove >>%s<<. Only derived parameters and results of the current run can be removed.')
        elif category == 'parameters':
            raise ValueError('You cannot remove >>%s<<. Only derived parameters and results of the current run can be removed.')
        elif category == 'derived_parameters':
            if traj_name == self.get_name():
                del self._single_run._derivedparameters[fullname]
            else:
                raise ValueError('You cannot remove >>%s<<. Only derived parameters and results of the current run can be removed.')
        elif category == 'config':
            raise ValueError('You cannot remove >>%s<<. Only derived parameters and results of the current run can be removed.')
        else:
            raise RuntimeError('You should nover come here :eeek:')


        self._logger.debug('Removed %s from trajectory.' %fullname)


    def set_standard_param_type(self,param_type):
        ''' Sets the standard parameter type.

        If param_type is not specified for add_parameter, than the standard parameter is used.
        '''
        assert issubclass(param_type,BaseParameter)
        self._single_run._standard_param_type = param_type


    def set_standard_result_type(self, result_type):
        ''' Sets the standard parameter type.

        If result_type is not specified for add_result, than the standard result is used.
        '''
        assert issubclass(result_type,BaseResult)
        self._single_run._standard_result_type=result_type


    def store(self, *args, **kwargs):
        ''' Stores all obtained results a new derived parameters to the hdf5file.
        '''
        #self._add_explored_params()
        self._storageservice.store(self,trajectoryname=self.get_parent_name(), *args, **kwargs)

    def store_stuff(self, to_store_list, *args, **kwargs):
        ''' Stores parameters specified in >>to_load_list<<. You can directly list the Parameter objects or their
        names.
        If names are given the >>get<< method is applied to find the parameter or result in the trajectory.
        If kwargs contains the keyword >>non_empties=True<<, only non-empty parameters or results are passed to the
        storage service to get stored.
        :param to_load_list: A list with parameters or results to store.
        :param args: Additional arguments directly passed to the storage service
        :param kwargs: Additional keyword arguments directly passed to the storage service (except the kwarg
        non_empties)
        :return:
        '''
        item_list = self._fetch_items(to_store_list, kwargs)


        self._storageservice.store(item_list,trajectoryname=self.get_parent_name(),*args,**kwargs)