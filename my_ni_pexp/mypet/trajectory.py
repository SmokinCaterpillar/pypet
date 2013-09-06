'''
Created on 17.05.2013

@author: robert
'''

import logging
import datetime
import time
from mypet.parameter import Parameter, BaseParameter, Result, BaseResult, ArrayParameter, PickleResult
import importlib as imp
import itertools as it
import inspect
import numpy as np

import mypet.petexceptions as pex
from mypet.utils.helpful_functions import flatten_dictionary
from mypet import globally
from mypet.annotations import WithAnnotations
import copy


BFS = 'BFS'
DFS = 'DFS'

class TrajOrRun(object):
    ''' Abstract class for methods that are used by single runs as well as full trajectories.

    '''
    #Constants for fetching items
    STORETRAJECTORYITEM = 'STORETRAJECTORYITEM' #We want to store an item of the trajectory
    STORESINGLERUNITEM = 'STORESINGLERUNITEM' #We want to store an item of the single run
    LOAD = 'LOAD' #We want to load stuff with the storage service
    REMOVE = 'REMOVE' #We want to remove stuff

    #For fetching all items
    ALL = 'ALL'

    @property
    def name_(self):
        '''Name of the trajectory'''
        return self.get_name()

    @property
    def timestamp_(self):
        '''Float timestamp of creation time'''
        return self.get_timestamp()

    @property
    def time_(self):
        '''Formatted time string of the time the trajectory was created.
        '''
        return self.get_time()

    @property
    def standard_parameter(self):
        ''' The standard parameter used for parameter creation'''
        return self.get_standard_parameter()

    @standard_parameter.setter
    def standard_parameter(self, parameter):
        self.set_standard_parameter(parameter)

    @property
    def standard_result(self):
        ''' The standard result class used for result creation '''
        return self.get_standard_result()

    @standard_result.setter
    def standard_result(self,result):
        self.set_standard_result(result)

    @property
    def fast_access(self):
        '''Whether parameter instances (False) or their values (True) are returned via natural naming

        Default is True.
        '''
        return self.get_fast_access

    @fast_access.setter
    def fast_acces_(self,value):
        self.set_fast_access(value)

    @property
    def check_uniqueness(self):
        '''Whether natural naming should check if naming is unambigous'''
        return self.get_uniqueness()

    @check_uniqueness.setter
    def check_uniqueness(self,value):
        return self.set_check_uniqueness(value)



    def get_config(self,fast_access=False):
        ''' Returns a dictionary containing the full config names as keys and the config parameters
         or the config parameter values.
        :param fast_access: Determines whether the parameter objects or their values are returned
         in the dictionary.
        :return: Dictionary containing the config data
        '''
        if isinstance(self,Trajectory):
            return self._config.copy()
        elif isinstance(self,SingleRun):
            return self._parent_trajectory.get_config()
        else:
            raise RuntimeError('You shall not pass!')

    def get_parameters(self,fast_access=False):
        ''' Returns a dictionary containing the full parameter names as keys and the parameters
         or the parameter values.
        :param fast_access: Determines whether the parameter objects or their values are returned
         in the dictionary.
        :return: Dictionary containing the parameters.
        '''
        if isinstance(self,Trajectory):
            return self._config.copy()
        elif isinstance(self,SingleRun):
            return self._parent_trajectory.get_config()
        else:
            raise RuntimeError('You shall not pass!')


    def get_explored_parameters(self, fast_access=False):
        ''' Returns a dictionary containing the full names as keys and the explored parameters
         or the exlored parameter values.
        :param fast_access: Determines whether the parameter objects or their values are returned
         in the dictionary.
        :return: Dictionary containing the parameters.
        '''
        if isinstance(self,Trajectory):
            if not fast_access:
                return self._exploredparameters.copy()
            else:
                explored_parameters={}
                for key,param in self._exploredparameters.iteritems():
                    val=param.get()
                    explored_parameters[key]=val

                return explored_parameters
        elif isinstance(self,SingleRun):
            return self._parent_trajectory.get_explored_parameters(fast_access)
        else:
            raise RuntimeError('You shall not pass!')

    def get_derived_parameters(self,fast_access=False):
        ''' Returns a dictionary containing the full names as keys and the derived parameters
         or the derived parameter values.
        :param fast_access: Determines whether the parameter objects or their values are returned
         in the dictionary.
        :return: Dictionary containing the parameters.
        '''
        self.get('derived_parameters', fast_access=fast_access,check_uniqueness=False).to_dict()

    def get_results(self):
        ''' Returns a dictionary containing the full result names as keys and the corresponding
        result objects.
        :return: Dictionary containing the results.
        '''
        self.get('results', fast_access=False,check_uniqueness=False).to_dict()

    def __contains__(self, item):
        ''' See :func:`contains`
        '''
        return self.contains(item)

    def get_search_strategy(self):
        return self._nninterface._search_strategy

    def set_search_strategy(self, string):
        assert string == BFS or string == DFS
        self._nninterface._search_strategy = string

    def get_uniqueness(self):
        return self._nninterface._check_uniqueness

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

    def get(self, name, fast_access=False, check_uniqueness = False, search_strategy = BFS):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>fast_access<<.

        :param name: The Name of the Parameter,Result or NNTreeNode that is requested.
        :param fast_access: If the default evaluation of a parameter should be returned.
        :param check_uniqueness: If search through the Parameter tree should be stopped after finding an entry or
        whether it should be chekced if the path through the tree is not unique.
        :param: search_strategy: The strategy to search the tree, either breadth first search (BFS) or depth first
        seach (DFS).
        :return: The requested object or it's default evaluation. Raises an error if the object cannot be found.
        '''
        return self._nninterface._get(name, fast_access, check_uniqueness, search_strategy)


    def contains(self,item):
        ''' Checks if the trajectory contains a specific parameter or result.

        It is checked if the item can be found via the trajectories "get" method.

        :param item: Name of the parameter or result or an object which name is then taken.
        :return: True or False
        '''
        if isinstance(item, (BaseParameter, BaseResult)):
            search_string = item.get_fullname()
        elif isinstance(item,str):
            search_string = item
        else:
            return False
        try:
            self.get(search_string)
            return True
        except AttributeError:
            return False

    def get_storage_service(self):
        ''' Returns the storage service of the trajectory
        '''
        return self._storageservice

    def to_dict(self, fast_access = False, short_names=False):
        ''' Returns all parameters and results in a dict.
        Keys are the names of the parameters/results (either full names or the short names depending
        on the setting of short_names) and the corresponding objects or directly the parameter
        values (if fast_access = True)
        :param fast_access: Boolean to determine whether the dictionary entries are parameter
        objects or the values accessible via param.get().
        :param short_names: Parameter that deterimines how the keys look like. If short_names is True
        all names must be unique, otherwise a ValueError is thrown.
        :return: A dictionary containing the parameters or results
        '''
        return self._nninterface._to_dict(fast_access, short_names)

    # def __getitem__(self, item):
    #     return getattr(self,item)

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
        else:
            self._nninterface._set(key, value)




    def _fetch_items(self,store_load, iterable, *args, **kwargs):
        only_empties = kwargs.pop('only_empties',False)

        non_empties = kwargs.pop('non_empties',False)


        if isinstance(iterable,str):
            iterable = [iterable]

        try:
            iterable = iter(iterable)
        except TypeError:
            iterable = [iterable]

        item_list = []
        for iteritem in iterable:


            if isinstance(iteritem,tuple):
                param_or_result = iteritem[1]
                msg = iteritem[0]
                if len(iteritem)>2:
                    args = iteritem[2]
                if len(iteritem)>3:
                    kwargs=iteritem[3]
                if len(iteritem)>4:
                    raise TypeError('Your argument tuple has to many entries, please call stuff '
                                    'to store with [(msg,item,args,kwargs),]')
            else:
                param_or_result = iteritem
                msg = None



            if isinstance(param_or_result, str):
                item = self.get(param_or_result)
            elif isinstance(param_or_result,(BaseParameter,BaseResult)):
                item =param_or_result
            else:
                raise RuntimeError('You shall not pass!')



            if isinstance(item,NNTreeNode):
                raise ValueError('One of the items you want to store or loead is a Tree Node, but '
                                 'Tree Nodes cannot be stored or loaded!')

            if msg == None:
                if isinstance(item, BaseResult):
                    if store_load in [TrajOrRun.STORESINGLERUNITEM,TrajOrRun.STORETRAJECTORYITEM]:
                        msg = globally.UPDATE_RESULT
                    elif store_load == TrajOrRun.LOAD:
                        msg = globally.RESULT
                    elif store_load == TrajOrRun.REMOVE:
                        msg = globally.REMOVE_RESULT
                    else:
                        raise RuntimeError('You shall not pass!')
                elif isinstance(item, BaseParameter):
                    if store_load in [TrajOrRun.STORESINGLERUNITEM,TrajOrRun.STORETRAJECTORYITEM]:
                        msg = globally.UPDATE_PARAMETER
                    elif store_load == TrajOrRun.LOAD:
                        msg = globally.PARAMETER
                    elif store_load == TrajOrRun.REMOVE:
                        msg = globally.REMOVE_PARAMETER
                else:
                    raise RuntimeError('You shall not pass!')

            if only_empties and not item.is_empty():
                continue
            if non_empties and item.is_empty():
                continue

            if store_load == TrajOrRun.STORESINGLERUNITEM:
                fullname = item.get_fullname()
                if not (fullname in self._single_run._derived_parameters or
                                fullname in self._single_run._results):
                    self._logger.warning('You want to store >>%s<< but this belongs to the parent '
                                         'trajectory not to the current single run. I will skip '
                                         'its storage.' % fullname)

            item_list.append((msg,item,args,kwargs))
        return item_list




    def store_stuff(self, iterator, *args,**kwargs):
        ''' Loads parameters specified in >>to_load_list<<. You can directly list the Parameter objects or their
        names.
        If names are given the >>get<< method is applied to find the parameter or result in the trajectory.
        If kwargs contains the keyword >>only_empties=True<<, only _empty parameters or results are passed to the
        storage service to get loaded.
        :param to_load_list: A list with parameters or results to store.
        :param args: Additional arguments directly passed to the storage service
        :param kwargs: Additional keyword arguments directly passed to the storage service (except the kwarg
        non_empties)
        :return:
        '''
        if isinstance(self,Trajectory):
                if not self._stored:
                    raise TypeError('Cannot store stuff for a trajectory that has never been '
                                    'stored to disk. Please call traj.store() first, which will '
                                    'actually cause the storage of all items in the trajectory.')

                trajname = self.get_name()
                msg = TrajOrRun.STORETRAJECTORYITEM
        elif isinstance(self, SingleRun):
                trajname = self._parent_trajectory.get_name()
                msg = TrajOrRun.STORESINGLERUNITEM
        else:
                raise RuntimeError('You shall not pass')

        non_empties = kwargs.pop('non_empties',False)

        if iterator == TrajOrRun.ALL:
            iterator = self.to_dict().itervalues()





        fetched_items = self._fetch_items(msg,iterator,*args,non_empties=non_empties,**kwargs)

        if fetched_items:
            self._storageservice.store(globally.LIST, fetched_items, trajectoryname = trajname)
        else:
            self._logger.warning('Your storage was not successfull, could not find a single item '
                                 'to store.')

    def get_full_param_name(self, param_name):
        param = self.get(param_name)
        return param.gfn()

    def gfpn(self, param_name):
        return self.get_full_param_name(param_name)



class NaturalNamingInterface(object):

    
    def __init__(self, working_trajectory_name, fast_access = True,
                 check_uniqueness=False,search_strategy = BFS, storage_dict = None,
                 flat_storage_dict=None,nodes_and_leaves = None):
        self._fast_access = fast_access
        self._check_uniqueness = check_uniqueness
        self._search_strategy = search_strategy
        self._working_trajectory_name=working_trajectory_name
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' +
                                         self._working_trajectory_name)

        self._storage_dict = storage_dict
        if self._storage_dict == None:
            self._storage_dict={}

        self._flat_storage_dict = flat_storage_dict
        if self._flat_storage_dict == None:
            self._flat_storage_dict = {}

        self._nodes_and_leaves = nodes_and_leaves
        if self._nodes_and_leaves == None:
            self._nodes_and_leaves = {}

        self._root = NNTreeNode(self)



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

        if isinstance(new_item,dict) and len(new_item) > 0:
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





    def _get(self, name, fast_access = False, check_uniqueness = False, search_strategy = BFS):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>fast_access<<.

        :param name: The Name of the Parameter,Result or NNTreeNode that is requested.
        :param fast_access: If the default evaluation of a parameter should be returned.
        :return: The requested object or it's default evaluation. Returns None if object could not be found.
        '''
        return self._root.get(name, fast_access, check_uniqueness, search_strategy)


    def _shortcut(self, name):
        
        expanded = None

        if name.startswith('run_') or name.startswith('r_'):
            split_name = name.split('_')
            if len(split_name) == 2:
                index = split_name[1]
                if index.isdigit():
                    if len(index) < SingleRun.TRAILINGZEROS:
                        expanded = SingleRun.FROMATTEDRUNNAME % int(index)

        if name in ['cr','currentrun', 'current_run']:
            expanded= self._working_trajectory_name

        if name in ['par','param']:
            expanded = 'parameters'

        if name in ['dpar', 'dparam']:
            expanded = 'derived_parameters'

        if name in ['res']:
            expanded='results'

        if name in ['conf']:
            expanded = 'config'
        
        if name in ['traj','tr']:
            expanded = 'trajectory'
        
        return expanded
         
        
    
    def _add_to_nninterface(self, fullname, data):
        
        split_name = fullname.split('.')
        
        for name in split_name:
            
            if not self._shortcut(name) == None:
                raise AttributeError('%s is already an important shortcut, cannot add it.' % name)
        
            

        replace = fullname in self._flat_storage_dict

        leaf = split_name.pop()
        
        self._add_to_storage_dict(split_name, leaf, data)
        self._flat_storage_dict[fullname] = data

        split_name.append(leaf) 

        if not replace:
            for name in split_name:
                if name in self._nodes_and_leaves:
                    self._nodes_and_leaves[name] = self._nodes_and_leaves[name] +1
                else:
                    self._nodes_and_leaves[name] =1
                #self._nodes_and_leaves.add(name)
        
    
    def _add_to_storage_dict(self, where_list, leaf, data):
        try:
            act_dict = self._storage_dict
            for idx,name in enumerate(where_list):
                if not name in act_dict:
                    act_dict[name] ={}

                act_dict = act_dict[name]

            if leaf in act_dict and isinstance(act_dict[leaf], dict):

                raise AttributeError('Your addition does not work, you would have a tree node '
                                     'called %s as well as a leaf containing data, both hanging '
                                     'below %s.' % (leaf,name))

            act_dict[leaf] = data

        except AttributeError:
            self._remove_recursive(where_list[0:idx+1],self._storage_dict)
            raise
            

    def _shallow_copy(self):
        newNNinterface = NaturalNamingInterface(working_trajectory_name=self._working_trajectory_name,
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
        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' +
                                         self._working_trajectory_name)
        self._root = NNTreeNode(nninterface=self)



    def _get_result(self, data, fast_access):

        if fast_access and isinstance(data, BaseParameter) and not isinstance(data, BaseResult):
            return data.get()
        else:
            return data

    def _search(self,fullname,key,dictionary, check_uniqueness, search_strategy):

        assert (search_strategy == BFS or search_strategy == DFS)
        check_list = [dictionary]
        result = None

        while len(check_list) > 0:

            if search_strategy == BFS:
                new_dict = check_list.pop(0)
            elif search_strategy == DFS:
                new_dict = check_list.pop()
            else:
                raise RuntimeError('You should never come here!')

            if key in new_dict:
                if not result == None:
                    raise AttributeError('The node or parameter/result %s is not uniqe.' %
                                         fullname)
                else:
                    result = new_dict[key]
                    if not check_uniqueness :
                        return result
            else:
                for val in new_dict.itervalues():
                    if isinstance(val,dict):
                        check_list.append(val)

        return result

            

class NNTreeNode(object):
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

    # def __getitem__(self, item):
    #     return getattr(self,item)
    #
    # def __iter__(self):
    #     return self.to_dict(fast_access=self._nninterface._fast_access,
    #                         short_names=False).iterkeys()

    def __getattr__(self,name):

        if (not  '_nninterface' in self.__dict__ or
            not  '_fullname' in self.__dict__ or
            not '_dict' in self.__dict__ or
            not 'get' in self.__class__.__dict__ or
            name[0]=='_'):
            raise AttributeError('Wrong attribute %s. (And you this statement prevents pickling '
                                 'problems)' % name)

        return self.get(name,self._nninterface._fast_access, self._nninterface._check_uniqueness,
                        self._nninterface._search_strategy)

    def __contains__(self,item):
        return self.contains(item)

    def contains(self,item):
        ''' Checks if the node contains a specific parameter or result.

        It is checked if the item can be found via the trajectories "get" method.

        :param item: Name of the parameter or result or an object which name is then taken.
        :return: True or False
        '''
        if isinstance(item, (BaseParameter, BaseResult)):
            search_string = item.get_fullname()
        elif isinstance(item,str):
            search_string = item
        else:
            return False


        if not search_string.startswith(self._fullname) and self._fullname != '':
            _,_,search_string = search_string.partition(self._fullname)


        try:
            self.get(search_string)
            return True
        except AttributeError:
            return False

    def __setattr__(self, key, value):
        if key[0]=='_':
            self.__dict__[key] = value
        else:
            instance = self.get(key)

            if not isinstance(instance, BaseParameter ):
                raise AttributeError('You cannot assign values to a tree node or a list of nodes '
                                     'and results, it only works for parameters ')


            instance.set(value)


    def to_dict(self, fast_access = False, short_names=False):

        ## Root node has no name, i.e. fullname == ''
        if len(self._fullname)>0:
            temp_dict = flatten_dictionary(self._dict,'.')

        ## If we are at the root node, we can simply return the flat dictionary and do not need to search
        else:
            temp_dict = self._nninterface._flat_storage_dict

            if not fast_access and not short_names:
                return  temp_dict.copy()

        result_dict={}

        for key,val in temp_dict.iteritems():


            if short_names:

                newkey = key.split('.')[-1]

                if newkey in result_dict:
                    raise ValueError('Cannot make short names, the names are not unique!')

            else:
                newkey = val.get_fullname()

            newval = self._nninterface._get_result(val,fast_access=fast_access)
            result_dict[newkey]=newval


        return result_dict



    def get(self, name, fast_access=False, check_uniqueness = False, search_strategy = BFS):
        ''' Same as traj.>>name<<
        Requesting parameters via get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>fast_access<<.

        :param name: The Name of the Parameter,Result or NNTreeNode that is requested.
        :param fast_access: If the default evaluation of a parameter should be returned.
        :param check_uniqueness: If search through the Parameter tree should be stopped after finding an entry or
        whether it should be chekced if the path through the tree is not unique.
        :param: search_strategy: The strategy to search the tree, either breadth first search (BFS) or depth first
        seach (DFS).
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
                raise AttributeError('Leading underscores are not allowed for group or parameter '
                                     'names. Cannot return %s.' %key)

            if not key in self._nninterface._nodes_and_leaves:
                raise AttributeError('%s is not part of your trajectory or it\'s tree.' % name)


        ## Check in O(1) first if a full parameter/result name is given
        fullname = '.'.join(split_name)

        if fullname.startswith(self._fullname):
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
            result =  self._nninterface._search(new_name,key, result, check_uniqueness,
                                                search_strategy)

        if isinstance(result,dict):
            return NNTreeNode(self._nninterface,new_name,result)
        elif not result == None:
            return self._nninterface._get_result(result,fast_access)
        else:
            raise AttributeError('The node or param/result >>%s<<, cannot be found.' % new_name)


        @property
        def children_names_(self):
            '''Names of immediate successor nodes in trajectory tree'''
            return self.get_children_names()

        def get_children_names(self,sort=False):
            if sort:
                return sorted(self._dict.keys())
            else:
                return self._dict.keys()

        @property
        def nchildren_(self):
            '''Number of immediate successor node in trajectory tree'''
            return self.get_nchildren()

        def get_nchildren(self):
            return len(self._dict)




class Trajectory(TrajOrRun):
    '''The trajectory manages results and parameters.


    The trajectory is the common object to interact with before and during a simulation.
    You can add four types of data to the trajectory:

    * Config:   These are special parameters specifying modalities of how to run your simulations.
                Changing a confing parameter should NOT have any influence on the results you
                obtain from your simulations.

                They specify runtime environment parameters like how many CPUs you use for
                multiprocessing, where the storage file into on disk can be found, etc.

                In fact, if you use the default runtime environment of this project, the environment
                will add some config parameters to your trajectory.

                The method to add these is :func:`add_config`

    * Parameters:   These are your primary ammunition in numerical simulations. They specify
                    how your simulation works. They can only be added before the actual
                    running of the simulation exploring the parameter space. They can be
                    added via :func:`add_parameter` and be explored using :func:`explore`.

                    Your parameters should encompass all values that completly define your simulation,
                    I recommend also storing random number generator seeds as parameters to
                    guarantee that a simulation can be exactly repeated.


    * Derived Parameters:   They are not much different from parameters except that they can be
                            added anytime.

                            Conceptually this encompasses stuff that is intermediately
                            computed from the original parameters. For instance, as your original
                            parameters you have a random number seed and some other parameters.
                            From these you compute a connection matrix for a neural network.
                            This connection matrix could be stored as a derived parameter.

                            Derived parameters are added via :func:`add_derived_parameter`

    * Results:  Result are added via the :func:`add_result`

    There are several ways to access the parameters, to learn about these, fast access, and natural
    naming see :ref:`more-on-access`


    
    :param name: Name of the trajectory, if `add_time=True` the current time is added as a string
                to the parameter name.

                    
    :param dynamicly_imported_classes: If the user has a custom parameter that needs to be loaded
                                      dynamically during runtime, the module containing the class 
                                      needs to be specified here as a list of classes or strings
                                      naming classes and there module paths.
                                      For example:
                                      `dynamically_imported_classes =
                                      ['mypet.parameter.PickleParameter',MyCustomParameter]`

                                      If you only have a single class to import, you do not need
                                      the list brackets:
                                      `dynamically_imported_classes
                                      = 'mypet.parameter.PickleParameter'`


                                      
    :param add_time: Boolean whether to add the current time to the parameter name.

    :param comment: A useful comment describing the trajectory.

    :param storage_service: A service to handle storage of the trajectory, parameters, and results.
                            If you use the Trajectory in combination with an environment the
                            environment will take care about this!

    :raises: AttributeError: If the name of the trajectory contains invalid characters.

             TypeError: If the dynamically imported classes are not classes or strings.
    
                                      
    Example usage:

    >>> traj = Trajectory('ExampleTrajectory',dynamically_imported_classes=['Some.custom.class'],\
    comment = 'I am a neat example!')

    '''


    def __init__(self, name='Traj',  dynamically_imported_classes=None,
                 add_time = True, storage_service=None, comment=''):
    
        #if init_time is None:
        init_time = time.time()

        
        formatted_time = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        
        self._timestamp = init_time
        self._time = formatted_time

        if add_time:
            self._name = name+'_'+str(formatted_time)
        else:
            self._name = name

        self._parameters={}
        self._derivedparameters={}
        self._results={}
        self._exploredparameters={}

        self._config={}

        self._changed_default_params = {}
        
        self._single_run_ids ={}
        self._run_information = {}
        
        # Per Definition the lenght is set to be 1, even with an _empty trajectory in principle you could make a single run
        self._add_run_info(0)
        
        self._nninterface = NaturalNamingInterface(working_trajectory_name=self._name)
        
        
        self._storageservice = storage_service

        self.set_comment(comment)

        self._idx = -1

        self._standard_parameter = Parameter
        self._standard_result = Result

        self._stored = False
        
        self._fullcopy=False

        self._dynamic_imports=['mypet.parameter.PickleParameter']

        if not dynamically_imported_classes is None:
            self.add_to_dynamic_imports(dynamically_imported_classes)

        
        # self._loadedfrom = 'None'

        self._not_admissable_names = set(dir(self) + dir(self._nninterface) +
                                         dir(self._nninterface._root)) | set(['ALL'])


        faulty_names = self._check_name(name)

        if '.' in name:
            faulty_names+=' colons >>.<< are  not allowed in trajectory names,'

        if faulty_names:
            raise AttributeError('Your Trajectory %s contains the following not admissible names: '
                                 '%s please choose other names.'
                                 % (name, faulty_names))

        self._logger = logging.getLogger('mypet.trajectory.Trajectory=' + self._name)


    def set_fullcopy(self,val):
        assert isinstance(val,bool)
        self._fullcopy=val

    def get_fullcopy(self,val):
        return self._fullcopy

    @property
    def full_copy_(self):
        '''Whether trajectory is copied fully or only the current parameter space point'''
        return self.get_fullcopy()

    @full_copy_.setter
    def full_copy_(self,val):
        self.set_fullcopy(val)


    def add_to_dynamic_imports(self,dynamically_imported_classes):
        ''' Adds classes or paths to classes to the trajectory to create custom parameters.

        :param dynamically_imported_classes: If the user has a custom parameter that needs to be
                                      loaded
                                      dynamically during runtime, the module containing the class
                                      needs to be specified here as a list of classes or strings
                                      naming classes and there module paths.
                                      For example:
                                      `dynamically_imported_classes =
                                      ['mypet.parameter.PickleParameter',MyCustomParameter]`

                                      If you only have a single class to import, you do not need
                                      the list brackets:
                                      `dynamically_imported_classes
                                      = 'mypet.parameter.PickleParameter'`

        '''

        if not isinstance(dynamically_imported_classes,(list,tuple)):
            dynamically_imported_classes=[dynamically_imported_classes]

        for item in dynamically_imported_classes:
            if not (isinstance(item,str) or inspect.isclass(item)):
                raise TypeError('Your dynamic import >>%s<< is neither a class nor a string.' %
                                str(item))

        self._dynamic_imports.extend(dynamically_imported_classes)


    def __iter__(self):
        ''' Iterator over all single runs.

        equivalent to calling :func:`iterruns`
        :
            :code-block:: python

            traj.iterruns(non_completed=False)

        '''
        return self.iterruns(non_completed=False)

    def iterruns(self, non_completed=False):
        ''' Returns an Iterator over all singe runs.

        :param non_completed: Whether completed runs should be discarded or not.
        '''
        if non_completed:
            return (self.make_single_run(idx) for idx in xrange(len(self))
                    if self.get_run_information(idx)['completed'])
        else:
            return (self.make_single_run(idx) for idx in xrange(len(self)))

    def idx2run(self,name_or_id):
        ''' Converts an integer idx to the corresponding single run name and vice versa.

        :param name_or_id: Name of a single run of an integer index
        '''
        return self._single_run_ids[name_or_id]

    def get_run_names(self):
        '''Returns a sorted list of the names of the single runs'''
        return  sorted(self._run_information.keys())

    @property
    def run_names_(self):
        '''Sorted list of names of runs'''
        return self.get_run_names()


    def get_run_information(self, name_or_idx=None):
        ''' Returns a dictionary containing information about a single run.

        If no name or idx is given than a list of all dictionaries is returned. Note
        that this requires a deepcopy of all the run information!

        :param name_or_idx:
        :return:
        '''
        if name_or_idx is None:
            return copy.deepcopy(self._run_information)
        if isinstance(name_or_idx,int):
            name_or_idx = self.idx2run(name_or_idx)
        return self._run_information[name_or_idx].copy()



    def get_time(self):
        return self._time



    def get_timestamp(self):
        return self._timestamp

    def remove_stuff(self, iterable, *args, **kwargs):

        kwargs['trajectory'] = self

        fetched_items = self._fetch_items(TrajOrRun.REMOVE,iterable, *args, **kwargs)

        if fetched_items:
            if self._stored:
                try:
                    self._storageservice.store(globally.LIST,fetched_items,
                                               trajectoryname = self.get_name())
                except:
                    self._logger.error('Could not remove >>%s<< from the trajectory. Maybe the'
                                       ' item(s) was/were never stored to disk. To remove it only '
                                       'from the trajectory call'
                                       ' >>traj._remove_only_from_trajectory(itemname)<<'
                                       ' if you are sure that this is the case.')
                    raise
            else:
                for msg,item,dummy1,dummy2 in fetched_items:
                    self._remove_only_from_trajectory(item.get_fullname())
        else:
            self._logger.warning('Your removal was not successful, could not find a single '
                                 'item to remove.')



    def remove_incomplete_runs(self,*args,**kwargs):
        self._storageservice.store(globally.REMOVE_INCOMPLETE_RUNS, self,
                                    *args,trajectoryname=self.get_name(), **kwargs)



    def _remove_only_from_trajectory(self,itemname):

        split_name = itemname.split('.')
        category = split_name[0]
        if category == 'results':
            del self._results[itemname]
        elif category == 'parameters':
            del self._parameters[itemname]
        elif category == 'derived_parameters':
            del self._derivedparameters[itemname]
        elif category == 'config':
            del self._config[itemname]
        else:
            raise RuntimeError('You should never come here :eeek:')

        if itemname in self._exploredparameters:
            del self._exploredparameters[itemname]


        if len(self._exploredparameters)== 0:
            self.shrink()


        self._nninterface._remove(itemname)
        self._logger.debug('Removed %s from trajectory.' %itemname)


    def shrink(self):
        if self._stored:
            raise TypeError('Your trajectory is already stored to disk of database, shrinking is '
                            'not allowed.')

        for key, param in self._exploredparameters:
            param._shrink()

        self._run_information={}
        self._single_run_ids={}
        self._add_run_info(0)




    def preset_config(self, config_name,*args,**kwargs):
        ''' Similar to preset_parameter.
        '''
        config_name = 'config'+'.'+config_name
        if config_name in self._config:
            self._config[config_name].set(*args,**kwargs)
        else:
            self._changed_default_params[config_name] = (args,kwargs)

    def preset_parameter(self, param_name,*args,**kwargs ):
        ''' Can be called before parameters are added to the Trajectory in order to change the values that are stored
        into the parameter.

        After creation of a Parameter, the instance of the parameter is called with param.set(*args,**kwargs).
        The prefix 'parameters.' is also automatically added to 'param_name'. If the parameter already exists,
        when preset_parameter is called, the parameter is changed directly.

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
            raise pex.DefaultReplacementError('The following parameters were supposed to replace a '
                                              'default value, but it was never tried to '
                                              'add default values with these names: %s' %
                                              str(self._changed_default_params))

        self.lock_parameters()
        self.lock_derived_parameters()
        for param in self._exploredparameters.itervalues():
            param.set_fullcopy=self._fullcopy

        self.store()



    def find(self,name_list,predicate):
        if not isinstance(name_list,list):
            name_list=[name_list]

        iter_list = []
        for name in name_list:
            param = self.get(name)
            if not isinstance(param,BaseParameter):
                raise TypeError('>>%s<< is not a parameter it is a %s, find is not applicable' %
                                (name,str(type(param))))

            if param.is_array():
                iter_list.append(iter(param.get_array()))
            else:
                iter_list.append((param.get() for dummy in xrange(len(self))))

        logic_iter = it.imap(predicate,*iter_list)

        for idx,item in enumerate(logic_iter):
            if item:
                yield idx




    def __len__(self):
        return len(self._run_information)



    
    def __getstate__(self):
        result = self.__dict__.copy()

        if not self._fullcopy:
            run_info = self.get_run_information(self._idx)
            result['_run_information'] = {run_info['name']: run_info}
            result['_single_run_ids'] = {run_info['name']:self._idx,self._idx:run_info['name']}

        del result['_logger']
        return result
    
    def __setstate__(self, statedict):
        self.__dict__.update(statedict)

        #self._tree= NNTreeNode(parent_trajectory=self, predecessors=[], depth=0, name='root')
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

       
    def set_comment(self,comment):
        if len(comment) >= globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
            self._logger.warning('Comment is too long. It has %d characters. '
                                 'I truncated it to %d characters.'
                                 % (len(comment),globally.HDF5_STRCOL_MAX_COMMENT_LENGTH))
            comment=comment[0:globally.HDF5_STRCOL_MAX_COMMENT_LENGTH-3]+'...'
        self._comment=comment


    @property
    def comment_(self):
        '''A useful comment about the trajectory'''
        return self.get_comment()

    @comment_.setter
    def comment(self, comment):
        self.set_comment()

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
        if self._name.startswith(SingleRun.RUNNAME):
            prefix = 'results.'+self._name+'.'
        else:
            prefix = 'results.trajectory.'
        args = list(args)


        if isinstance(args[0], BaseResult):

            instance = args.pop(0)
            if not instance.get_fullname().startswith('results.'):
                instance._rename(prefix+instance.get_fullname())
            full_result_name = instance.get_fullname()

        elif isinstance(args[0],str):

            full_result_name = args.pop(0)

            if not full_result_name.startswith('results.'):
                full_result_name = prefix+full_result_name

            if not 'result' in kwargs:
                if args and inspect.isclass(args[0]) and issubclass(args[0] , BaseResult):
                        args = list(args)
                        result_type = args.pop(0)
                else:
                    result_type = self._standard_result
            else:
                result_type = kwargs.pop('result')

            if isinstance(result_type,str):
                result_type = self._create_class(result_type)

            instance = result_type(full_result_name,*args, **kwargs)
        else:
            raise RuntimeError('You did not supply a new Result or a name for a new result')

        faulty_names = self._check_name(full_result_name)

        if faulty_names:
            raise AttributeError('Your Result >>%s<< contains the following not admissible names: '
                                 '%s please choose other names' %
                                 (full_result_name,str(faulty_names)))


        if full_result_name in self._results:
            self._logger.warn(full_result_name +
                              ' is already part of trajectory, I will replace it.')

        self._results[full_result_name] = instance
        
        self._nninterface._add_to_nninterface(full_result_name, instance)

        
        return instance

    def add_config(self, *args, **kwargs):
        return self._add_any_param('config.',self._config,*args,**kwargs)

    def ac(self, *args, **kwargs):
        return self.add_config(*args,**kwargs)


    def is_completed(self,name_or_id):
        return self.get_run_information(name_or_id)['completed']


    def get_standard_parameter(self):
        return self._standard_parameter

    def get_standard_result(self):
        return self._standard_result

    def set_standard_parameter(self,param_type):
        ''' Sets the standard parameter type.

        If param_type is not specified for add_parameter, than the standard parameter is used.
        '''
        assert issubclass(param_type,BaseParameter)
        self._standard_parameter = param_type


    def set_standard_result(self, result_type):
        ''' Sets the standard parameter type.

        If result_type is not specified for add_result, than the standard result is used.
        '''
        assert issubclass(result_type,BaseResult)
        self._standard_result=result_type

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
        if self._name.startswith(SingleRun.RUNNAME):
            prefix = 'derived_parameters.'+self._name+'.'
        else:
            prefix = 'derived_parameters.trajectory.'
        return self._add_any_param(prefix,self._derivedparameters,
                                   *args,**kwargs)

    def _add_any_param(self, prefix, where_dict, *args,**kwargs):

        args = list(args)
        preprefix = prefix.split('.')[0]+'.'

        if isinstance( args[0],BaseParameter):

            instance = args.pop(0)
            if not instance.get_fullname().startswith(preprefix):
                instance._rename(prefix+instance.get_fullname())
            full_parameter_name = instance.get_fullname()

        elif isinstance(args[0],str):

            full_parameter_name = args.pop(0)

            if not full_parameter_name.startswith(preprefix):
                full_parameter_name = prefix+full_parameter_name

            if not 'parameter' in kwargs:
                if args and inspect.isclass(args[0]) and issubclass(args[0] , BaseParameter):
                        args = list(args)
                        param_type = args.pop(0)
                else:
                    param_type = self._standard_parameter
            else:
                param_type = kwargs.pop('parameter')

            if isinstance(param_type,str):
                param_type = self._create_class(param_type)

            instance = param_type(full_parameter_name,*args, **kwargs)
        else:
            raise RuntimeError('You did not supply a new Parameter or a name for a new Parameter.')

        faulty_names = self._check_name(full_parameter_name)

        if faulty_names:
            raise AttributeError('Your Parameter %s contains the following not admittable names: '
                                 '%s please choose other names.'
                                 % (full_parameter_name, faulty_names))

        if full_parameter_name in where_dict:
            self._logger.warn(full_parameter_name + ' is already part of trajectory, I will '
                                                    'replace the old one.')

        if full_parameter_name in self._changed_default_params:
            self._logger.info('You have marked parameter %s for change before, so here you go!' %
                              full_parameter_name)

            change_args, change_kwargs = self._changed_default_params.pop(full_parameter_name)
            instance.set(*change_args,**change_kwargs)

        where_dict[full_parameter_name] = instance

        self._nninterface._add_to_nninterface(full_parameter_name, instance)


        # self.last = instance
        # self.Last = instance

        self._logger.debug('Added >>%s<< to trajectory.' %full_parameter_name)

        # # If a parameter is added for the first time, the length is set to 1
        # if len(self) == 0 and where_dict==self._parameters:
        #     self._length = 1
        #     #If we add a parameter we could have a single run without exploration
        #     self._add_run_info(0)


        return instance


    
    def _check_name(self, name):
        split_names = name.split('.')
        faulty_names = ''

        for split_name in split_names:
            if split_name in self._not_admissable_names:
                faulty_names = '%s %s is a method/attribute of the trajectory/treenode/naminginterface,' %\
                               (faulty_names, split_name)

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

    def expand(self,build_function,*args,**kwargs):
        build_dict = build_function(*args,**kwargs)

        # if the builder function returns tuples, the first element must be the build dictionary
        if isinstance(build_dict, tuple):
            build_dict, dummy = build_dict

        #split_dict = self._split_dictionary(build_dict)

        count = 0#Don't like it but ok
        for key, builditerable in build_dict.items():
            act_param = self.get(key,check_uniqueness=True)
            if isinstance(act_param,NNTreeNode):
                raise ValueError('%s is not an appropriate search string for a parameter.' % key)

            act_param._expand(builditerable)

            name = act_param.gfn()

            self._exploredparameters[name] = act_param



            if count == 0:
                length = len(act_param)#Not so nice, but this should always be the same numbert
            else:
                if not length == len(act_param):
                    raise ValueError('The parameters to _explore have not the same size!')

            for irun in range(length):

                self._add_run_info(irun)


    def explore(self,build_dict):
        ''' Creates Parameter Arrays for exploration.
        '''
            
        count = 0#Don't like it but ok
        for key, builditerable in build_dict.items():
            act_param = self.get(key,check_uniqueness=True)
            if isinstance(act_param,NNTreeNode):
                raise ValueError('%s is not an appropriate search string for a parameter.' % key)

            act_param._explore(builditerable)

            name = act_param.gfn()

            self._exploredparameters[name] = act_param


            
            if count == 0:
                length = len(act_param)#Not so nice, but this should always be the same numbert
            else:
                if not length == len(act_param):
                    raise ValueError('The parameters to _explore have not the same size!')
       
            for irun in range(length):

                self._add_run_info(irun)



    def _add_run_info(self,runid):

        runname = SingleRun.FROMATTEDRUNNAME % runid
        self._single_run_ids[runname] = runid
        self._single_run_ids[runid] = runname
        info_dict = {}

        info_dict['idx'] = runid
        info_dict['timestamp'] = 42.0
        info_dict['time'] = '~waste ur t1me with a phd'
        info_dict['completed'] = 0
        info_dict['name'] = runname
        info_dict['parameter_summary'] = 'Not yet my friend!'

        self._run_information[runname] = info_dict
        
            
    def lock_parameters(self):
        for key, par in self._parameters.items():
            par.lock()
    
    def lock_derived_parameters(self):
        for key, par in self._derivedparameters.items():
            par.lock()

    def finalize_experiment(self):
        self.restore_default()
            
    def update_skeleton(self):
        self.load(self.get_name(),False,globally.UPDATE_SKELETON,globally.UPDATE_SKELETON,
                  globally.UPDATE_SKELETON)

    def load_stuff(self, iterator, *args,**kwargs):
        ''' Loads parameters specified in >>to_load_list<<. You can directly list the Parameter objects or their
        names.
        If names are given the >>get<< method is applied to find the parameter or result in the trajectory.
        If kwargs contains the keyword >>only_empties=True<<, only _empty parameters or results are passed to the
        storage service to get loaded.
        :param to_load_list: A list with parameters or results to store.
        :param args: Additional arguments directly passed to the storage service
        :param kwargs: Additional keyword arguments directly passed to the storage service (except the kwarg
        non_empties)
        :return:
        '''

        if not self._stored:
            raise TypeError('Cannot load stuff from disk for a trajectory that has never been stored.')

        only_empties = kwargs.pop('only_empties',False)

        if iterator == TrajOrRun.ALL:
            iterator = self.to_dict().itervalues()


        fetched_items = self._fetch_items(TrajOrRun.LOAD,iterator,*args,only_empties=only_empties,
                                          **kwargs)
        if fetched_items:
            self._storageservice.load(globally.LIST, fetched_items,
                                      trajectoryname = self.get_name())
        else:
            self._logger.warning('Your loading was not successful, could not find a single item '
                                 'to load.')




    def load(self,
             trajectoryname=None,
             as_new=False,
             load_params = globally.LOAD_DATA,
             load_derived_params = globally.LOAD_SKELETON,
             load_results = globally.LOAD_SKELETON,
             *args, **kwargs):

        if not trajectoryname:
            trajectoryname = self.get_name()

        self._storageservice.load(globally.TRAJECTORY,self,*args,trajectoryname=trajectoryname,
                                  as_new=as_new, load_params=load_params,
                                  load_derived_params=load_derived_params,
                                  load_results=load_results,
                                  **kwargs)


    def _check_if_both_have_same_parameters(self,other_trajectory,
                                            ignore_trajectory_derived_parameters):

        assert isinstance(other_trajectory,Trajectory)
        self.update_skeleton()
        other_trajectory.update_skeleton()

        ## Load all parameters of the current and the given Trajectory
        if self._stored:
            self.load_stuff(self._parameters.values(),only_empties=True)
        if other_trajectory._stored:
            other_trajectory.load_stuff(other_trajectory._parameters.values(),only_empties=True)

        self.restore_default()
        other_trajectory.restore_default()


        allmyparams = self._parameters.copy()
        allotherparams = other_trajectory._parameters.copy()


        if not ignore_trajectory_derived_parameters:
            my_traj_dpars =self.get('derived_parameters.trajectory').to_dict()
            allmyparams.update(my_traj_dpars)
            other_traj_dpars = other_trajectory.get('derived_parameters.trajectory').to_dict()
            allotherparams.update(other_traj_dpars)


        ## Check if the trajectories have the same parameters:
        my_keyset = set(allmyparams.keys())
        other_keyset = set(allotherparams.keys())

        if not my_keyset== other_keyset:
            diff1 = my_keyset - other_keyset
            diff2 = other_keyset-my_keyset
            raise TypeError( 'Cannot merge trajectories, they do not live in the same space,the '
                             'set of parameters >>%s<< is only found in the current trajectory '
                             'and >>%s<< only in the other trajectory.' % (str(diff1),str(diff2)))

        for key,other_param in allotherparams.items():
            my_param = self.get(key)
            if not my_param._values_of_same_type(my_param.get(),other_param.get()):
                raise TypeError('Cannot merge trajectories, values of parameters >>%s<< are not '
                                'of the same type. Types are %s (current) and %s (other).'%
                                (key,str(type(my_param.get())),str(type(other_param.get()))))


    def backup(self,*args,**kwargs):
        self._storageservice.store(globally.BACKUP,self,*args, trajectoryname=self.get_name(),
                                   **kwargs)


    def merge(self, other_trajectory, *args,**kwargs):

        trial_parameter = kwargs.pop('trial_parameter',None)
        remove_duplicates = kwargs.pop('remove_duplicates', False)
        ignore_trajectory_derived_parameters = kwargs.pop('ignore_trajectory_derived_parameters',
                                                          False)

        ignore_trajectory_results = kwargs.pop('ignore_trajectory_results', False)
        backup=kwargs.pop('backup_filename',None)
        other_backup = kwargs.pop('other_backup_filename', None)

        ## Check if trajectories can be merged
        self._check_if_both_have_same_parameters(other_trajectory,
                                                 ignore_trajectory_derived_parameters)

        ## BACKUP if merge is possible
        if (not other_backup is None) and other_backup != 0 and other_backup != False :
            if isinstance(other_backup,str):
                backup_filename = other_backup
                kwargs['backup_filename']=backup_filename


            other_trajectory.backup(globally.BACKUP,*args,**kwargs)

        if (not backup is None) and backup != 0 and backup != False:
            kwargs.pop('backup_filename',None) # Otherwise the filename from previous backup might be kept
            if isinstance(backup,str):
                backup_filename = backup
                kwargs['backup_filename']=backup_filename


            self.backup(globally.BACKUP,self,*args,**kwargs)




        self._logger.info('Merging the parameters.')
        used_runs, changed_parameters = self._merge_parameters(other_trajectory,remove_duplicates,trial_parameter,ignore_trajectory_derived_parameters)

        if np.all(used_runs==0):
            self._logger.warning('Your merge discards all runs of the other trajectory, maybe you '
                                 'try to merge a trajectory with itself?')
            return
        # if not ignore_trajectory_derived_parameters and 'derived_parameters.trajectory' in other_trajectory:
        #     self._logger.info('Merging derived trajectory parameters')
        #     changed_derived_parameters = self._merge_trajectory_derived_parameters(other_trajectory,used_runs)
        # else:
        #     changed_derived_parameters = []

        rename_dict={}

        if not ignore_trajectory_results and 'results.trajectory' in other_trajectory:
            self._logger.info('Merging trajectory results skeletons.')
            self._merge_trajectory_results(other_trajectory,rename_dict)

        self._logger.info('Merging single run skeletons.')
        self._merge_single_runs(other_trajectory,used_runs,rename_dict)


        adding_length = sum(used_runs)


        self._logger.info('Updating Trajectory information and changed parameters in storage.')


        #update_iterator = it.repaet(globally.UPDATE_PARAMETER)
        #self.store_stuff(it.izp(update_iterator,param_iterator),*args,**kwargs)

        self._storageservice.store(globally.UPDATE_TRAJECTORY, self,  *args,
                                   trajectoryname=self.get_name(),
                                   changed_parameters=changed_parameters,
                                   new_results=sorted(rename_dict.values()), **kwargs)

        self._logger.info('Start copying results and single run derived parameters.')
        try:
            self._storageservice.store(globally.MERGE, None, *args, trajectoryname=self.get_name(),
                                       other_trajectory_name=other_trajectory.get_name(),
                                       rename_dict=rename_dict, **kwargs)
        except pex.NoSuchServiceError:
            self._logger.warning('My storage service does not support merging of trajectories, '
                                 'I will use the load mechanism of the other trajectory and copy '
                                 'the results manually and slowly. Note that thereby the other '
                                 'trajectory will be altered.')

            self._merge_slowly(other_trajectory,rename_dict,*args,**kwargs)
        except ValueError,e:
            self._logger.warning(str(e))

            self._merge_slowly(other_trajectory,rename_dict,*args,**kwargs)

        self._logger.info('Finished Merging!')


    def _merge_slowly(self,other_trajectory, rename_dict,*args,**kwargs):

        for other_key, new_key in rename_dict.iteritems():

            other_instance = other_trajectory.get(other_key)
            was_empty = False
            if other_instance.is_empty():
                was_empty = True
                other_trajectory.load_stuff(other_instance,*args,**kwargs)


            my_instance = self.get(new_key)
            if not my_instance.is_empty():
                raise RuntimeError('You want to slowly merge results, but your target result '
                                   '>>%s<< is not _empty, this should not happen.' %
                                   my_instance.get_fullname())

            load_dict = other_instance._store()
            my_instance._load(load_dict)


            self.store_stuff(my_instance,*args,**kwargs)


            if was_empty:
                other_instance._empty()
                my_instance._empty()




    def _merge_trajectory_results(self, other_trajectory, rename_dict):

        other_results = other_trajectory.get('results.trajectory').to_dict()

        for key, result in other_results.iteritems():


            if key in self._results:
                self._logger.warning('You already have a trajectory result called >>%s<< in your '
                                     'trajectory. I will not copy it.' %key)
                continue

            rename_dict[key] = key
            comment = result.get_comment()
            result_type = result.get_classname()
            self.add_result(key,comment=comment,result_type=result_type)



    def _merge_single_runs(self, other_trajectory, used_runs, rename_dict):

        count = len(self)
        runnames = other_trajectory.get_run_names()
        for  runname in runnames:
            idx = other_trajectory.get_run_information(runname)['idx']
            if used_runs[idx]:
                try:
                    results = other_trajectory.get('results.' + runname).to_dict()
                except AttributeError:
                    results = {}

                try :
                    derived_params = other_trajectory.get('derived_parameters.'+runname).to_dict()
                except AttributeError:
                    derived_params={}

                time = other_trajectory.get_run_information(runname)['time']
                timestamp = other_trajectory.get_run_information(runname)['timestamp']
                completed = other_trajectory.get_run_information(runname)['completed']


                new_runname = SingleRun.FROMATTEDRUNNAME % count



                self._run_information[new_runname] = dict(idx = count,
                                                          time = time, timestamp=timestamp,
                                                          completed = completed)

                self._single_run_ids[count] = new_runname
                self._single_run_ids[new_runname] = count


                count +=1

                for result_name, result in results.iteritems():
                    new_result_name = self._rename_key(result_name,1,new_runname)
                    rename_dict[result_name] = new_result_name
                    comment = result.get_comment()
                    result_type = result.get_classname()
                    self.add_result(new_result_name,comment=comment,result=result_type)



                for dpar_name, dpar in derived_params.iteritems():
                    new_dpar_name = self._rename_key(dpar_name,1,new_runname)
                    rename_dict[dpar_name] = new_dpar_name
                    comment = dpar.get_comment()
                    param_type = dpar.get_classname()
                    self.add_derived_parameter(new_dpar_name,comment=comment,parameter=param_type)


            else:
                continue


    def _rename_key(self,key,pos,newname):
        split_key = key.split('.')
        split_key[pos]=newname
        renamed_key = '.'.join(split_key)
        return renamed_key

    def _merge_parameters(self,other_trajectory, remove_duplicates=False, trial_parameter = None,
                          ignore_trajectory_derived_parameters=False):



        if trial_parameter:
            if remove_duplicates:
                self._logger.warning('You have given a trial parameter and you want to '
                                     'remove_stuff duplicates. There cannot be any duplicates '
                                     'when adding trials, I will not look for duplicates.')
                remove_duplicates=False

        if trial_parameter:
            my_trial_parameter = self.get(trial_parameter)
            other_trial_parameter = other_trajectory.get(trial_parameter)
            if not isinstance(my_trial_parameter,BaseParameter):
                raise TypeError('Your trial_parameter >>%s<< does not evaluate to a real parameter'
                                ' in the trajectory' % trial_parameter)

            if my_trial_parameter.is_array():
                my_trial_list = my_trial_parameter.get_array()
            else:
                my_trial_list = [my_trial_parameter.get()]

            if other_trial_parameter.is_array():
                other_trial_list = other_trial_parameter.get_array()
            else:
                other_trial_list = [other_trial_parameter.get()]
            mytrialset = set(my_trial_list)
            mymaxtrial = max(mytrialset)

            if  mytrialset != set(range(mymaxtrial+1)):
                raise TypeError('In order to specify a trial parameter, this parameter must '
                                'contain integers from 0 to %d, but it infact it '
                                'contains >>%s<<.' %(mymaxtrial,str(mytrialset)))

            othertrialset = set(other_trial_list)
            othermaxtrial = max(othertrialset)
            if  othertrialset != set(range(othermaxtrial+1)):
                raise TypeError('In order to specify a trial parameter, this parameter must '
                                'contain integers from 0 to %d, but it infact it contains >>%s<< in the other trajectory.' %(othermaxtrial,str(othertrialset)))

            trial_parameter = my_trial_parameter.get_fullname()

            if not trial_parameter in self._exploredparameters:
                self._exploredparameters[trial_parameter] = my_trial_parameter


        ## Check which parameters differ:
        params_to_change ={}

        params_to_merge = other_trajectory._parameters.copy()

        if not ignore_trajectory_derived_parameters:
            trajectory_derived_parameters = other_trajectory.get('derived_parameters.trajectory').to_dict()
            params_to_merge.update(trajectory_derived_parameters)


        for key, other_param in params_to_merge.iteritems():

            my_param = self.get(key)
            if not my_param._values_of_same_type(my_param.get(),other_param.get()):
                raise TypeError('The parameters with name >>%s<< are not of the same type, cannot '
                                'merge trajectory.' %key)

            if my_param.get_fullname() == trial_parameter:
                params_to_change[key] = (my_param,other_param)
                continue

            if (my_param.is_array()
                or other_param.is_array()
                or not my_param._equal_values(my_param.get(), other_param.get())):

                params_to_change[key]=(my_param,other_param)
                if not my_param.is_array() and not other_param.is_array():
                    remove_duplicates=False

        ## Now first check if we use all runs ore remove_stuff duplicates:
        use_runs = np.ones(len(other_trajectory))
        if remove_duplicates:

            for irun in xrange(len(other_trajectory)):
                for jrun in xrange(len(self)):
                    change = True
                    for my_param, other_param in params_to_change.itervalues():
                        if other_param.is_array():
                            other_param.set_parameter_access(irun)

                        if my_param.is_array():
                            my_param.set_parameter_access(jrun)

                        val1 = my_param.get()
                        val2 = other_param.get()

                        if not my_param._equal_values(val1,val2):
                            change = False
                            break
                    if change:
                        use_runs[irun] = 0.0
                        break

            ## Restore changed default values
            for my_param, other_param in params_to_change.itervalues():
                other_param.restore_default()
                my_param.restore_default()


        ## Now merge into the new trajectory
        adding_length = int(sum(use_runs))
        if adding_length == 0:
            return 0, []

        for my_param, other_param in params_to_change.itervalues():
            fullname =  my_param.get_fullname()



            if fullname == trial_parameter:
                other_array = [x+mymaxtrial+1 for x in other_trial_list]
            else:
                if other_param.is_array():
                    other_array = (x for run,x in it.izip(use_runs,other_param.get_array()) if run)
                else:
                    other_array = (other_param.get() for dummy in xrange(adding_length))


            if not my_param.is_array():
                    my_param.unlock()
                    my_param._explore((my_param.get() for dummy in xrange(len(self))))

                    #self._exploredparameters[my_param.get_fullname()]=my_param

            my_param.unlock()

            my_param._expand(other_array)

            if not fullname in self._exploredparameters:
                self._exploredparameters[fullname] = my_param



        return use_runs, params_to_change.keys()




    def store(self, *args, **kwargs):
        ''' Stores all obtained results a new derived parameters to the hdf5file.
        '''
        #self._srn_add_explored_params()
        self._storageservice.store(globally.TRAJECTORY,self,trajectoryname=self.get_name(),
                                   *args, **kwargs)
        self._stored=True

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









    def restore_default(self):
        for param in self._exploredparameters.itervalues():
            param.restore_default()


    def prepare_paramspacepoint(self,n):
        ''' Notifies the explored parameters what the current point in the parameter space it is,
        i.e. which is the current run.
        '''

        # extract only one particular paramspacepoint
        for key,val in self._exploredparameters.items():
            val.set_parameter_access(n)


     
    def make_single_run(self,idx):
        ''' Creates a SingleRun object for parameter exploration.
        
        The SingleRun object can used as the parent trajectory. The object contains a shallow
        copy of the parent trajectory but wihtout parameter arrays. From every array only the 
        nth parameter is used.
        '''
        name = self.idx2run(idx)
        self._idx=idx
        return SingleRun( name, idx, self)





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
    TRAILINGZEROS = 8
    RUNNAME = 'run_'
    FROMATTEDRUNNAME= RUNNAME+'%'+'0%dd' % TRAILINGZEROS
    
    def __init__(self, name,  id, parent_trajectory):
        
        assert isinstance(parent_trajectory, Trajectory)



        #self._time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%Hh%Mm%Ss')

        self._idx = id

        self._parent_trajectory = parent_trajectory
        self._parent_trajectory.prepare_paramspacepoint(id)

        self._storageservice = self._parent_trajectory._storageservice

        self._single_run = Trajectory(name, parent_trajectory._dynamic_imports, add_time=False)
        self._single_run.set_storage_service(self._storageservice)
        
        self._nninterface = self._parent_trajectory._nninterface._shallow_copy()
        # self.last = self._parent_trajectory.last
        # self.Last = self._parent_trajectory.Last

        #del self._single_run._nninterface
        self._single_run._nninterface = self._nninterface
        self._single_run._standard_parameter = self._parent_trajectory._standard_parameter
        self._single_run._standard_result = self._parent_trajectory._standard_result
        
        self._nninterface._parent_trajectory_name = self._parent_trajectory.get_name()
        self._nninterface._working_trajectory_name = self._single_run.get_name()

        self._logger = logging.getLogger('mypet.trajectory.SingleRun=' + self._single_run.get_name())


    def __len__(self):
        ''' Length of a single run can only be 1 and nothing else!
        :return:
        '''
        return 1


    @property
    def parent_name_(self):
        '''Name of the parent trajectory'''
        return self.get_parent_name()

    def get_idx(self):
        return self._idx

    @property
    def idx_(self):
        '''Index of the single run'''
        return self.get_idx()

    def get_timestamp(self):
        return self._single_run.get_timestamp()

    def get_time(self):
        return self._single_run.get_time()

        
    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        return result
    
    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.trajectory.SingleRun=' + self._single_run.get_name())

        
    def add_derived_parameter(self, *args, **kwargs):
        # self.last= self._single_run.add_derived_parameter(*args, **kwargs)
        # self.Last = self.last
        # return self.last
        return self._single_run.add_derived_parameter(*args, **kwargs)


    
    
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

    def get_time(self):
        return self._single_run.get_time()

    def get_timestamp(self):
        return self._single_run.get_timestamp()




    def set_standard_parameter(self,param_type):
        ''' Sets the standard parameter type.

        If param_type is not specified for add_parameter, than the standard parameter is used.
        '''
        assert issubclass(param_type,BaseParameter)
        self._single_run._standard_parameter = param_type


    def set_standard_result(self, result_type):
        ''' Sets the standard parameter type.

        If result_type is not specified for add_result, than the standard result is used.
        '''
        assert issubclass(result_type,BaseResult)
        self._single_run._standard_result=result_type

    def get_standard_parameter(self):
        return self._single_run._standard_parameter

    def get_standard_result(self):
        return self._single_run._standard_result


    def store(self, *args, **kwargs):
        ''' Stores all obtained results a new derived parameters to the hdf5file.
        '''
        #self._srn_add_explored_params()
        self._storageservice.store(globally.SINGLERUN,self,trajectoryname=self.get_parent_name(),
                                   *args, **kwargs)
