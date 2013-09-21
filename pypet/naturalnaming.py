__author__ = 'robert'




import importlib as imp
import itertools as it
import inspect
import numpy as np


import pypet.petexceptions as pex
from pypet.utils.helpful_functions import flatten_dictionary
from pypet import globally
from pypet.annotations import WithAnnotations
import logging


#For fetching:
STORE = 'STORE'
LOAD = 'LOAD' #We want to f_load stuff with the storage service
REMOVE = 'REMOVE' #We want to remove stuff


#Group Constants
RESULT = 'RESULT'
RESULT_GROUP = 'RESULTGROUP'
PARAMETER = 'PARAMETER'
PARAMETER_GROUP = 'PARAMETER_GROUP'
DERIVED_PARAMETER = 'DERIVED_PARAMETER'
DERIVED_PARAMETER_GROUP = 'DERIVED_PARAMETER_GROUP'
CONFIG = 'CONFIG'
CONFIG_GROUP = 'CONFIG_GROUP'

## For fast searching
FAST_UPPER_BOUND = 2


#### Naming
FORMAT_ZEROS=8
RUN_NAME = 'run_'
FORMATTED_RUN_NAME=RUN_NAME+'%0'+str(FORMAT_ZEROS)+'d'

class NNTreeNode(WithAnnotations):
    def __init__(self,full_name,root,leaf):
        #self.v_full_name = full_name

        super(NNTreeNode,self).__init__()

        split_name = full_name.split('.')

        if root:
            self._depth=0
        else:
            self._depth = len(split_name)

        self._name=split_name.pop()
        self._location='.'.join(split_name)
        self._leaf=leaf

    @property
    def v_depth(self):
        ''' Depth of the node in the trajectory tree.
        '''
        return self._depth

    @property
    def v_leaf(self):
        '''Whether node is a leaf or not (i.e. it is a group node)'''
        return self._leaf



    def f_is_root(self):
        '''Returns whether the group is root (True for the trajectory and a single run object)'''
        return self._depth==0

    @property
    def v_full_name(self):
        ''' The full name, relative to the root node.

        The full name of a trajectory or single run is the empty string since it is root.
        '''
        if self.f_is_root():
            return ''
        else:
            if self._location=='':
                return self._name
            else:
                return '.'.join([self._location,self._name])

    @property
    def v_name(self):
        ''' Name of the node
        '''
        return self._name

    @property
    def v_location(self):
        ''' Location relative to the root node.

        The location of a trajectory or single run is the empty string since it is root.
        '''
        return self._location

    def _rename(self, fullname):
        ''' Renames the parameter or result.
        '''
        #self.v_full_name = fullname
        split_name = fullname.split('.')

        self._depth = len(split_name)

        self._name=split_name.pop()
        self._location='.'.join(split_name)


    def f_get_class_name(self):
        ''' Returns the class name of the parameter or result or group,
        equivalent to `return self.__class__.__name__`
        '''
        return self.__class__.__name__



class NNLeafNode(NNTreeNode):
    ''' Abstract class interface of result or parameter
    '''

    def __init__(self,full_name,comment,parameter):
        super(NNLeafNode,self).__init__(full_name=full_name,root=False,leaf=True)
        self._parameter=parameter
        self._fast_accessible = parameter

        self._comment=''
        self.v_comment=comment


    @property
    def v_comment(self):
        ''' Should be a nice descriptive comment'''
        return self._comment

    @v_comment.setter
    def v_comment(self, comment):

        comment = str(comment)
        if len(comment)>=globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
            raise AttributeError('Your comment is too long ( %d characters), only comments up to'
                                 '%d characters are allowed.' %
                                 (len(comment),globally.HDF5_STRCOL_MAX_COMMENT_LENGTH))

        self._comment=comment


    @property
    def v_fast_accessible(self):
        '''Whether or not fast access can be supported by the Parameter or Result'''
        return self._fast_accessible

    @property
    def v_parameter(self):
        '''Whether the node is a parameter or not (i.e. a result)'''
        return self._parameter

    def f_val_to_str(self):
        ''' Returns a string summarizing the data handled by the parameter or result
        '''
        return ''


    def __str__(self):
        ''' String representation of the parameter or result, If not other specified this is
        simply the full name.
        '''
        return self.v_full_name





    def _store_flags(self):
        return {}

    def _store(self):
        ''' Method called by the storage service for serialization.

        The method converts the parameter's or result's value into  simple
        data structures that can be stored to disk.
        Returns a dictionary containing these simple structures.
        Understood basic strucutres are

        * python natives (int,str,bool,float,complex)

        * python lists and tuples

        * numpy natives and arrays of type np.int8-64, np.uint8-64, np.float32-64,
                                            np.complex, np.str

        * python dictionaries of the previous types (flat not nested!)

        * pandas data frames

        * object tables

        :return: A dictionary containing basic data structures.

        '''
        raise NotImplementedError('Implement this!')

    def _load(self, load_dict):
        ''' Method called by the storage service to reconstruct the original result.

        Data contained in the load_dict is equal to the data provided by the result
        when previously called with _store()

        :param load_dict: The dictionary containing basic data structures

        '''
        raise  NotImplementedError('Implement this!')


    def f_is_empty(self):
        ''' Returns true if no data is handled by a result or parameter
        '''
        raise NotImplementedError('You should implement this!')

    def f_empty(self):
        ''' Removes all data from the result.

        If the result has already been stored to disk via a trajectory and a storage service,
        the data on disk is not affected by `f_emptyty`.

        Yet, this function is particularly useful if you have stored very large data to disk
        and you want to free some memory on RAM but still keep the skeleton of the result.

        '''
        raise NotImplementedError('You should implement this!')

class NaturalNamingInterface(object):


    # TYPE_NODE_MAPPING = {
    #     'result_group' : ResultGroup,
    #     'config_group' : ConfigGroup,
    #     'derived_parameter_group' : DerivedParameterGroup
    #     'parameter_group' : ParameterGroup
    # }




    def __init__(self, root_instance):

        self._root_instance = root_instance

        self._run_or_traj_name= root_instance.v_name

        self._logger = logging.getLogger('pypet.trajectory.NNTree=' +
                                         self._root_instance.v_name)

        self._flat_storage_dict = {}

        self._nodes_and_leaves = {}

        self._not_admissible_names = set(dir(self) + dir(self._root_instance) ) | set([globally.ALL])


    def _map_type_to_dict(self,type_name):

        root = self._root_instance

        if type_name == RESULT:
            return root._results
        elif type_name == PARAMETER:
            return root._parameters
        elif type_name == DERIVED_PARAMETER:
            return root._derived_parameters
        elif type_name == CONFIG:
            return root._config
        else:
            raise RuntimeError('You shall not pass!')


    def _change_root(self, new_root):
        new_root._children = self._root_instance._children
        self._root_instance = new_root

    def _get_fast_access(self):
        return self._root_instance.v_fast_access

    def _get_search_strategy(self):
        return self._root_instance.v_search_strategy

    def _get_check_uniqueness(self):
        return self._root_instance.v_check_uniqueness


    def _fetch_from_string(self,store_load, name, args, kwargs):

        node = self._root_instance.f_get(name)

        return self._fetch_from_node(store_load,node,args,kwargs)

    def _fetch_from_node(self,store_load, node,args,kwargs):
        msg = self._node_to_msg(store_load,node)

        return (msg,node,args,kwargs)

    def _fetch_from_tuple(self,store_load,store_tuple,args,kwargs):

        node = store_tuple[1]
        msg = store_tuple[0]
        if len(store_tuple) > 2:
            args = store_tuple[2]
        if len(store_tuple) > 3:
            kwargs = store_tuple[3]
        if len(store_tuple) > 4:
            print store_tuple
            raise TypeError('Your argument tuple has to many entries, please call stuff '
                            'to f_store with [(msg,item,args,kwargs),]')

        ##dummy test
        _ = self._fetch_from_node(store_load,node)

        return (msg,node,args,kwargs)


    @staticmethod
    def _node_to_msg(store_load,node):

        if node.v_leaf:
            if store_load ==STORE:
                return globally.LEAF
            elif store_load == LOAD:
                return globally.LEAF
            elif store_load == REMOVE:
                 return globally.REMOVE
        else:
            if store_load ==STORE:
                return globally.GROUP
            elif store_load == LOAD:
                return globally.GROUP
            elif store_load == REMOVE:
                 return globally.REMOVE
        #raise ValueError('I do not know how to f_store >>%s<<' % str(node))


    def _fetch_items(self, store_load, iterable, args, kwargs):
        only_empties = kwargs.pop('only_empties', False)

        non_empties = kwargs.pop('non_empties', False)


        item_list = []
        for iter_item in iterable:

            try:
                item_tuple = self._fetch_from_string(store_load,iter_item,args,kwargs)
            except AttributeError:
                try:
                    item_tuple = self._fetch_from_node(store_load,iter_item,args,kwargs)
                except AttributeError:
                    item_tuple = self._fetch_from_tuple(store_load,iter_item,args,kwargs)

            item = item_tuple[1]

            if only_empties and not item.f_is_empty():
                continue
            if non_empties and item.f_is_empty():
                continue

            if self._root_instance._is_run:
                fullname = item.v_full_name
                if not self.v_name in fullname:
                    raise TypeError('You want to store/load/remove >>%s<< but this belongs to the '
                                    'parent trajectory not to the current single run.' % fullname)



            item_list.append(item_tuple)
        return item_list


    def _remove_subtree(self,start_node,name):

        def _remove_subtree_inner(node):
            if not node.v_leaf:

                for name in node._children.keys():
                    child = node._children[name]
                    _remove_subtree_inner(child)
                    del node._children[name]
                    del child

            self._delete_node(node)



        child = start_node._children[name]

        _remove_subtree_inner(child)
        del start_node._children[name]






    def _delete_node(self,node):

        full_name = node.v_full_name
        name = node.v_name

        root = self._root_instance


        if full_name in ['parameters','results','derived_parameters','config','']:
            ## You cannot delete root or nodes in first layer
            return

        if node.v_leaf:
            if full_name in root._parameters:
                del root._parameters[full_name]

            elif full_name in root._config:
                del root._config[full_name]

            elif full_name in root._derived_parameters:
                del root._derived_parameters[full_name]

            elif full_name in root._results:
                del root._results[full_name]

            if full_name in root._explored_parameters:
                del root._explored_parameters[full_name]

                if len(root._explored_parameters)==0:
                    if root._stored:
                       self._logger.warning('You removed an explored parameter, but your '
                                            'trajectory was already stored to disk. So it is '
                                            'not shrunk!')
                    else:
                        root.f_shrink()

            del self._flat_storage_dict[full_name]



        else:
            del root._groups[full_name]

        del self._nodes_and_leaves[name][full_name]
        if len(self._nodes_and_leaves[name]) == 0:
            del self._nodes_and_leaves[name]


    def _remove_node_or_leaf(self, instance,remove_empty_groups):
        full_name = instance.v_full_name
        split_name = full_name.split('.')
        self._remove_recursive(self._root_instance,split_name,remove_empty_groups)



    def _remove_recursive(self,actual_node,split_name,remove_empty_groups):

        if len(split_name)== 0:
            self._delete_node(actual_node)
            return True

        name = split_name.pop(0)


        child = actual_node._children[name]

        if self._remove_recursive(child, split_name, remove_empty_groups):
            del actual_node._children[name]
            del child

            if remove_empty_groups and len(actual_node._children) == 0:
                self._delete_node(actual_node)
                return True

        return False





    def _shortcut(self, name):

        expanded = None

        if name.startswith('run_') or name.startswith('r_'):
            split_name = name.split('_')
            if len(split_name) == 2:
                index = split_name[1]
                if index.isdigit():
                    if len(index) < FORMAT_ZEROS:
                        expanded = FORMATTED_RUN_NAME % int(index)

        if name in ['cr', 'currentrun', 'current_run']:
            expanded = self._root_instance.v_name

        if name in ['par', 'param']:
            expanded = 'parameters'

        if name in ['dpar', 'dparam']:
            expanded = 'derived_parameters'

        if name in ['res']:
            expanded = 'results'

        if name in ['conf']:
            expanded = 'config'

        if name in ['traj', 'tr']:
            expanded = 'trajectory'

        return expanded


    def _add_prefix( self,name, start_node, group_type_name):

        ## If we add an instance with a full name at root, we do not need to add the prefix
        if start_node.f_is_root():
            for prefix in ('results','parameters','derived_parameters','config'):
                if name.startswith(prefix):
                    return name

        root=self._root_instance

        if start_node.v_depth<2:
            if group_type_name == DERIVED_PARAMETER_GROUP:

                add=''

                if not ((name.startswith('run_') and len(name) ==len(RUN_NAME)+FORMAT_ZEROS) or
                    name.startswith('trajectory')):

                    if root._is_run:
                        add= start_node.v_name + '.'
                    else:
                        add= 'trajectory.'

                if start_node.v_depth== 0:
                    add = 'derived_parameters.' + add

                return add+name


            elif group_type_name == RESULT_GROUP:

                add = ''

                if not ((name.startswith('run_') and len(name) ==len(RUN_NAME)+FORMAT_ZEROS) or
                    name == 'trajectory'):

                    if root._is_run:
                        add= start_node.v_name + '.'
                    else:
                        add= 'trajectory.'

                if start_node.v_depth== 0:
                    add = 'results.' + add

                return add+name

        if start_node.f_is_root():

            if group_type_name == PARAMETER_GROUP:
                return 'parameters.'+name

            if group_type_name == CONFIG_GROUP:
                return 'config.'+name

        return name


    def _add_from_leaf_instance(self,start_node,instance):

        full_name = start_node.v_full_name

        if full_name.startswith('results'):
            group_type_name = RESULT_GROUP
            type_name = RESULT


        elif full_name.startswith('parameters'):
            group_type_name = PARAMETER_GROUP
            type_name = PARAMETER

        elif full_name.startswith('derived_parameters'):
            group_type_name = DERIVED_PARAMETER_GROUP
            type_name = DERIVED_PARAMETER

        elif full_name.startswith('config'):
            group_type_name = CONFIG_GROUP
            type_name = CONFIG

        else:
            raise RuntimeError('You shall not pass!')

        return self._add_generic(start_node,type_name,group_type_name,[instance],{})


    def _add_from_group_name(self,start_node,name):

        full_name = start_node.v_full_name

        if full_name.startswith('results'):
            group_type_name = RESULT_GROUP


        elif full_name.startswith('parameters'):
            group_type_name = PARAMETER_GROUP


        elif full_name.startswith('derived_parameters'):
            group_type_name = DERIVED_PARAMETER_GROUP


        elif full_name.startswith('config'):
            group_type_name = CONFIG_GROUP


        else:
            raise RuntimeError('You shall not pass!')

        return self._add_generic(start_node,group_type_name,group_type_name,[name],{})



    def _add_generic(self,start_node,type_name,group_type_name,args,kwargs):

        if type_name == group_type_name:
            # Wee add a group node, this can be only done by name:
            name = args[0]
            instance = None
            constructor = None

        else:
            ## We add a leaf node in the end:
            args = list(args)

            create_new = True

            if len(args) == 1 and len(kwargs)==0:
                item = args[0]
                try:
                    name = item.v_full_name
                    instance = item
                    constructor = None

                    create_new = False
                except AttributeError:
                    pass




            if create_new:
                if inspect.isclass(args[0]):
                    constructor = args.pop(0)
                else:
                    constructor = None

                instance = None

                name = args.pop(0)

        name = self._add_prefix(name,start_node,group_type_name)


        return self._add_to_nninterface(start_node,name,type_name,group_type_name,instance,
                                            constructor,args,kwargs)








    def _add_to_nninterface(self, start_node, name, type_name, group_type_name,
                            instance, constructor, args, kwargs ):


        split_name = name.split('.')

        faulty_names= self._check_names(split_name)

        if faulty_names:
            raise AttributeError(
                'Your Parameter/Result/Node >>%s<< f_contains the following not admissible names: '
                '%s please choose other names.'
                % (name, faulty_names))


        return self._add_to_tree(start_node, split_name, type_name, group_type_name, instance, constructor,
                     args, kwargs )


    def _add_to_tree(self, start_node, split_name, type_name, group_type_name, instance, constructor,
                     args, kwargs ):
        try:
            act_node = start_node
            last_idx = len(split_name)-1
            for idx, name in enumerate(split_name):

                if not name in act_node._children:


                    if idx == last_idx and group_type_name != type_name:
                        # If we are at the end of the chain and we add a leave node

                        new_node = self._create_any_param_or_result(act_node.v_full_name,name,
                                                                    type_name,instance,constructor,
                                                                    args,kwargs)

                        self._flat_storage_dict[new_node.v_full_name] = new_node


                    else:
                        # We add a group node
                        new_node = self._create_any_group(act_node.v_full_name,name,
                                                          group_type_name)

                    act_node._children[name] = new_node


                    if not name in self._nodes_and_leaves:
                        self._nodes_and_leaves[name]={new_node.v_full_name:new_node}
                    else:
                        self._nodes_and_leaves[name][new_node.v_full_name]=new_node

                else:
                    if idx == last_idx:
                        raise AttributeError('You already have a group/instance >>%s<< under '
                                             '>>%s<<' % (name,start_node.v_full_name))


                act_node = act_node._children[name]

            return act_node
        except:
            self._logger.error('Failed storing >>%s<< under >>%s<<.' %
                               (name, start_node.v_full_name))
            raise



    def _check_names(self, split_names):

        faulty_names = ''

        for split_name in split_names:
            if split_name in self._not_admissible_names:
                faulty_names = '%s %s is a method/attribute of the trajectory/treenode/naminginterface,' % \
                               (faulty_names, split_name)

            if split_name[0] == '_':
                faulty_names = '%s %s starts with a leading underscore,' % (
                    faulty_names, split_name)

            if ' ' in split_name:
                faulty_names = '%s %s f_contains white space(s),' % (faulty_names, split_name)

            if not self._shortcut(split_name) is None:
                faulty_names = '%s %s is already an important shortcut,' %( faulty_names, split_name)


        return faulty_names


    def _create_any_group(self, location, name, type_name):

        instance = self._create_node_instance(location,name, type_name)

        self._root_instance._groups[instance.v_full_name]=instance


        return instance



    def _create_node_instance(self,location,name,type_name):

        if location:
            full_name = '%s.%s' % (location, name)
        else:
            full_name = name


        if type_name == RESULT_GROUP:
            return ResultGroup(self,full_name=full_name, root=False)

        elif type_name == PARAMETER_GROUP:
            return ParameterGroup(self,full_name=full_name, root=False)

        elif type_name == CONFIG_GROUP:
            return ConfigGroup(self,full_name=full_name, root=False)

        elif type_name == DERIVED_PARAMETER_GROUP:
            return DerivedParameterGroup(self,full_name=full_name, root=False)
        else:
            raise RuntimeError('You shall not pass!')


    def _create_any_param_or_result(self, location, name, type_name, instance, constructor,
                                    args, kwargs):


        root = self._root_instance

        if location:
            full_name = '%s.%s' % (location, name)
        else:
            full_name = name

        if instance is None:

            if constructor is None:
                if type_name == RESULT:
                    constructor=root._standard_result
                else:
                    constructor=root._standard_parameter



            instance = constructor(full_name, *args, **kwargs)
        else:
            instance._rename(full_name)

        
        where_dict = self._map_type_to_dict(type_name)

        if full_name in where_dict:
            raise AttributeError(full_name + ' is already part of trajectory,')

        if type_name != RESULT:
            if full_name in root._changed_default_parameters:
                self._logger.info('You have marked parameter %s for change before, so here you go!' %
                                  full_name)

                change_args, change_kwargs = root._changed_default_parameters.pop(full_name)
                instance.f_set(*change_args, **change_kwargs)

        where_dict[full_name] = instance




        self._logger.debug('Added >>%s<< to trajectory.' % full_name)

        return instance







    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        return result


    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('pypet.trajectory.NNTree=' +
                                         self._run_or_traj_name)


    @staticmethod
    def _get_result(data, fast_access):

        if fast_access and data.v_fast_accessible:
            return data.f_get()
        else:
            return data

    @staticmethod
    def _iter_nodes( node, recursive=False, search_strategy=globally.BFS):

        if recursive:
            if search_strategy == globally.BFS:
                return NaturalNamingInterface._recursive_traversal_bfs(node)
            elif search_strategy == globally.DFS:
                return NaturalNamingInterface._recursive_traversal_dfs(node)
            else:
                raise ValueError('Your search method is not understood!')
        else:
            return node._children.itervalues()


    @staticmethod
    def _iter_leaves(node):
        for node in node.f_iter_nodes(recursive=True):
            if node.v_leaf:
                yield node
            else:
                continue

    def _to_dict(self,node,fast_access = True, short_names=False, copy=True):

        if (fast_access or short_names)  and not copy:
            raise ValueError('You can not request the original data with >>fast_access=True<< or'
                             ' >>short_names=True<<.')

        if node.f_is_root():
            temp_dict = self._flat_storage_dict

            if not fast_access and not short_names:
                if copy:
                    return temp_dict.copy()
                else:
                    return temp_dict

            else:
                iterator = temp_dict.itervalues()
        else:
            iterator=self._iter_leaves(node)

        result_dict={}
        for val in iterator:
            if short_names:
                new_key = val.v_name
            else:
                new_key = val.v_full_name

            if new_key in result_dict:
                raise ValueError('Your short names are not unique!')

            new_val = self._get_result(val,fast_access)
            result_dict[new_key]=new_val

        return result_dict

    @staticmethod
    def _recursive_traversal_bfs(node):
        if not node._leaf:
            for child in node._children.itervalues():
                yield child

            for child in node._children.itervalues():
                for new_node in NaturalNamingInterface._recursive_traversal_bfs(child):
                    yield new_node


    @staticmethod
    def _recursive_traversal_dfs(node):
        if not node._leaf:
            for child in node._children.itervalues():
                yield child
                for new_node in NaturalNamingInterface._recursive_traversal_dfs(child):
                    yield new_node


    def _very_fast_search(self, node, key, check_uniqueness):
        ''' Will always test if nodes are not unique'''

        parent_full_name = node.v_full_name

        candidate_dict = self._nodes_and_leaves[key]

        if len(candidate_dict) > FAST_UPPER_BOUND:
            raise pex.TooManyGroupsError('Too many nodes')

        result_node = None
        for goal_name in candidate_dict.iterkeys():

            if goal_name.startswith(parent_full_name):

                if not result_node is None:
                    raise pex.NotUniqueNodeError('Node >>%s<< has been found more than once,'
                                                 'full name of first found is >>%s<< and of'
                                                 'second >>%s<<'
                                                 % (key,goal_name,result_node.v_full_name))

                result_node=candidate_dict[goal_name]

        return result_node


    def _search(self,node,  key, check_uniqueness, search_strategy):

        try:
            return self._very_fast_search(node, key, check_uniqueness)
        except pex.TooManyGroupsError:
            pass
        except pex.NotUniqueNodeError:
            if check_uniqueness:
                raise
            else:
                pass

        nodes_iterator = NaturalNamingInterface._iter_nodes(node, recursive=True,
                                                            search_strategy=search_strategy)

        result_node = None
        for child in nodes_iterator:
            if key == child.v_name:

                if not result_node is None:
                    raise pex.NotUniqueNodeError('Node >>%s<< has been found more than once,'
                                                 'full name of first found is >>%s<< and of '
                                                 'second >>%s<<'
                                                 % (key,child.v_full_name,result_node.v_full_name))

                result_node =  child
                if not check_uniqueness:
                    return result_node

        return result_node



    def _get(self,node, name, fast_access, check_uniqueness, search_strategy):
        ''' Same as traj.>>name<<
        Requesting parameters via f_get does not pay attention to fast access. Whether the parameter object or it's
        default evaluation is returned depends on the value of >>fast_access<<.

        :param name: The Name of the Parameter,Result or NNGroupNode that is requested.
        :param fast_access: If the default evaluation of a parameter should be returned.
        :param check_uniqueness: If search through the Parameter tree should be stopped after finding an entry or
        whether it should be chekced if the path through the tree is not unique.
        :param: search_strategy: The strategy to search the tree, either breadth first search (globally.BFS) or depth first
        seach (globally.DFS).
        :return: The requested object or it's default evaluation. Raises an error if the object cannot be found.
        '''


        split_name = name.split('.')


        ## Rename shortcuts and check keys:
        for idx, key in enumerate(split_name):
            shortcut = self._shortcut(key)
            if shortcut:
                key = shortcut
                split_name[idx] = key

            if key[0] == '_':
                raise AttributeError('Leading underscores are not allowed for group or parameter '
                                     'names. Cannot return %s.' % key)

            if not key in self._nodes_and_leaves:
                raise AttributeError('%s is not part of your trajectory or it\'s tree.' % name)

        ## Check in O(1) if len(split_name)==1
        if len(split_name)==1 and not check_uniqueness:
            result = node._children.get(key,None)
        else:
            result = None

        if result is None:
            ## Check in O(d) first if a full parameter/result name is given
            fullname = '.'.join(split_name)

            if fullname.startswith(node.v_full_name):
                new_name = fullname
            else:
                new_name = node.v_full_name + '.' + fullname

            if new_name in self._flat_storage_dict:
                return self._get_result(self._flat_storage_dict[new_name],
                                                     fast_access=fast_access)

            if new_name in self._root_instance._groups:
                return self._root_instance._groups[new_name]

        # Check in O(N)
        # [Worst Case, Average Case is better since looking into a single dict costs O(1)]
        # globally.BFS or globally.DFS
        # If check Uniqueness == True, search is slower since the full dictionary
        # is always searched

        result = node
        for key in split_name:
            result = self._search(result,key, check_uniqueness, search_strategy)

        if result is None:
            raise AttributeError('The node or param/result >>%s<<, cannot be found.' % name)
        if result.v_leaf:
            return self._get_result(result, fast_access)
        else:
            return result






class NNGroupNode(NNTreeNode):
    ''' A group node hanging somewhere under the trajectory or single run root node.
    You can add other groups or parameters/results to it.
    '''

    def __init__(self, nn_interface=None, full_name='', root=False):
        super(NNGroupNode,self).__init__(full_name,root=root,leaf=False)
        self._children={}
        self._nn_interface=nn_interface

    def __str__(self):

        if not self.f_is_root():
            name = self.v_full_name
        else:
            name = self.v_name

        return '<%s>: %s: %s' % (self.f_get_class_name(),name,
                                 str([(key,str(type(val)))
                                      for key,val in self._children.iteritems()]))

    def f_children(self):
        '''Returns the number of children of the group.'''
        return len(self._children)

    def f_has_children(self):
        '''Checks if node has children or not'''
        return len(self._children)==0

    def __getattr__(self, name):

        if (not '_nn_interface' in self.__dict__ or
                not '_full_name' in self.__dict__ or
                not '_children' in self.__dict__ or
                not 'f_get' in self.__class__.__dict__ or
                    name[0] == '_'):
            raise AttributeError('Wrong attribute %s. (And you this statement prevents pickling '
                                 'problems)' % name)

        return self.f_get(name, self._nn_interface._get_fast_access(),
                        self._nn_interface._get_check_uniqueness(),
                        self._nn_interface._get_search_strategy())

    def __contains__(self, item):
        return self.f_contains(item)

    def f_remove_child(self, name, recursive = False):
        ''' Removes a child of the group.

        Note that groups and leaves are only removed from the current trajectory in RAM.
        If the trajectory is stored to disk, this data is not affected. Thus, remove can be used
        only to free RAM memory!

        If you want to free memory on disk via your storage service,
        use :func:`~pypet.trajectory.Trajectory.f_remove_item(s)` of your trajectory.

        :param name: Name of child

        :param recursive: Must be true if child is a group that has children. Will remove
                            the whole subtree in this case. Otherwise a Type Error is thrown.

        :raises: TypeError

        '''
        if not name in self._children:
                raise TypeError('Your group >>%s<< does not contain the child >>%s<<.' %
                                (self.v_full_name,name))

        else:
            child = self._children[name]

            if not child.v_leaf and child.f_has_children and not recursive:
                raise TypeError('Cannot remove child. It is a group with children. Use'
                                ' f_remove with >>recursive = True')
            else:
                self._nn_interface._remove_subtree(self,name)


    def f_contains(self, item, recursive = True):
        ''' Checks if the node contains a specific parameter or result.

        It is checked if the item can be found via the "~pypet.naturalnaming.NNGroupNode.f_get" method.

        :param item: Parameter/Result name or instance.

        :param: recursive: Whether the whole sub tree under the group should be checked or only
                          its immediate children. Default is the whole sub tree.
                          If `recursive=False` you must only specify the name not the full name.

        :return: True or False
        '''

        try:
            search_string = item.v_full_name
            name = item.v_name
        except AttributeError:
            search_string = item
            name = item

        try:
            if search_string.startswith(self.v_full_name) and self.v_full_name != '':
                _, _, search_string = search_string.partition(self.v_full_name)
        except AttributeError:
            return False

        if recursive:
            try:
                self.f_get(search_string)

                return True
            except AttributeError:

                return False
        else:
            return name in self._children

    def __setattr__(self, key, value):
        if key.startswith('_'):
            self.__dict__[key] = value
        elif hasattr(self.__class__,key):
            property = getattr(self.__class__,key)
            if property.fset is None:
                raise AttributeError('%s is read only!' % key)
            else:
                property.fset(self,value)
        else:
            instance = self.f_get(key)

            if not instance.v_parameter:
                raise AttributeError('You cannot assign values to a tree node or a list of nodes '
                                     'and results, it only works for parameters ')

            instance.f_set(value)

    def __getattr__(self, key):
        if key.startswith('_'):
            raise AttributeError('Trajectory node does not contain >>%s<<' % key)

        if not '_nn_interface' in self.__dict__:
            raise AttributeError('This is to avoid pickling issues')

        return self._nn_interface._get(self,key,fast_access=self._nn_interface._get_fast_access(),
                                       check_uniqueness=self._nn_interface._get_check_uniqueness(),
                                       search_strategy=self._nn_interface._get_search_strategy())

    def f_iter_nodes(self, recursive=False, search_strategy=globally.BFS):
        ''' Iterates over nodes hanging below this group.

        :param recursive: Whether to iterate the whole sub tree or only immediate children.

        :param search_strategy: Either BFS or DFS (BFS recommended)

        :return: Iterator over nodes

        '''
        return self._nn_interface._iter_nodes(self,recursive=recursive,
                                             search_strategy=search_strategy)


    def f_iter_leaves(self):
        ''' Iterates (recursively) over all leaves hanging below the current group.
        '''
        return self._nn_interface._iter_leaves(self)


    def f_get(self, name, fast_access=False, check_uniqueness=False, search_strategy=globally.BFS):
        ''' Searches for an item (parameter/result/group node) with the given `name`-

        :param name: Name of the item (full name or parts of the full name)

        :param fast_access: If the result is a parameter, whether fast access should be applied.

        :param check_uniqueness: Whether it should be checked if the name unambiguously yields
                                 a single result.

        :param search_strategy: The search strategy (default and recommended is BFS)

        :return: The found instance (result/parameter/group node) or if fast access is True and you
                 found
                 a parameter, the parameter's value is returned.
        '''
        return self._nn_interface._get(self, name, fast_access=fast_access,
                                       check_uniqueness=check_uniqueness,
                                       search_strategy=search_strategy)

    def f_get_children(self, copy=True):
        '''Returns a children dictionary.

        :param copy: Whether the group's original dicitionary or a shallow copy is returned.
                     If you want the real dictionary please do not modify it at all!

        :returns: Dictionary of nodes
        '''
        if copy:
            return self._children.copy()
        else:
            return self._children

    def f_to_dict(self,fast_access = False, short_names=False):
        ''' Returns a dictionary with pairings of (full) names as keys and instances/values.

        :param fast_access: If True, parameter values are returned instead of the instances-

        :param short_names: If true, keys are not full names but only the names. Raises a Value
                            Error if the names are not unique.

        :return: dictionary

        :raises: ValueError

        '''
        return self._nn_interface._to_dict(self, fast_access=fast_access,short_names=short_names)


    def f_store_child(self,name,recursive=False):
        '''Stores a child or recursively a subtree to disk'''
        if not name in self._children:
                raise TypeError('Your group >>%s<< does not contain the child >>%s<<.' %
                                (self.v_full_name,name))

        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.store(globally.TREE, self._children[name], trajectory_name=traj.v_name,
                              recursive=recursive)



    def f_load_child(self,name,recursive=False,load_data=globally.UPDATE_DATA):
        '''Loads a child or recursively a subtree from disk'''
        if not name in self._children:
                raise TypeError('Your group >>%s<< does not contain the child >>%s<<.' %
                                (self.v_full_name,name))

        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.load(globally.TREE, self,child_name=name, trajectory_name=traj.v_name,
                             recursive=recursive, load_data=load_data, trajectory=traj)





class ParameterGroup(NNGroupNode):
    ''' Group node in your trajectory, hanging below `traj.parameters` (or the `parameters` group itself).

    You can add other groups or parameters to it.
    '''
    def f_add_parameter_group(self,name):
        '''Adds an empty parameter group under the current node.

        Adds the full name of the current node
        as prefix to the name of the group.
        If current node is the trajectory or single run (root), the prefix `'parameters'`
        is added to the full name.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        '''
        return self._nn_interface._add_generic(self,type_name = PARAMETER_GROUP,
                                               group_type_name = PARAMETER_GROUP,
                                               args = (name,), kwargs={})

    def f_add_parameter(self,*args,**kwargs):
        ''' Adds a parameter under the current node.

        There are two ways to add a new parameter either by adding a parameter instance,
        directly:

        >>> new_parameter = Parameter('group1.group2.myparam', data=42, comment='Example!')
        >>> traj.f_add_parameter(new_parameter)

        Or by passing the values directly to the function, with the name being the first
        (non-keyword!) argument:

        >>> traj.f_add_parameter('group1.group2.myparam', data=42, comment='Example!')

        If you want to create a different parameter than the standard parameter, you can
        give the constructor as the first (non-keyword!) argument followed by the name (non-keyword!):

        >>> traj.f_add_parameter(PickleParameter,'group1.group2.myparam', data=42, comment='Example!')

        The full name of the current node is added as a prefix to the given parameter name.
        If the current node is the trajectory the prefix `'parameters'` is added to the name.

        '''
        return self._nn_interface._add_generic(self,type_name = PARAMETER,
                                               group_type_name = PARAMETER_GROUP,
                                               args=args,kwargs=kwargs)

class ResultGroup(NNGroupNode):
    ''' Group node in your trajectory, hanging below `traj.results`.

    You can add other groups or results to it.
    '''
    def f_add_result_group(self,name):
        '''Adds an empty result group under the current node.

        Adds the full name of the current node
        as prefix to the name of the group.
        If current node is the trajectory (root) adds the prefix `'results.trajectory'` to the full name.
        If current node is a single run (root) adds the prefix `'results.run_08%d%'` to the full name
        where `'08%d'` is replaced by the index of the current run.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        '''


        return self._nn_interface._add_generic(self,type_name = RESULT_GROUP,
                                               group_type_name = RESULT_GROUP,
                                               args = (name,), kwargs={})

    def f_add_result(self,*args,**kwargs):
        ''' Adds a result under the current node.

        There are two ways to add a new result either by adding a result instance,
        directly:

        >>> new_result = Result('group1.group2.myresult', 1666, x=3, y=4, comment='Example!')
        >>> traj.f_add_result(new_result)

        Or by passing the values directly to the function, with the name being the first
        (non-keyword!) argument:

        >>> traj.f_add_result('group1.group2.myresult', 1666, x=3, y=3,comment='Example!')


        If you want to create a different result than the standard result, you can
        give the constructor as the first (non-keyword!) argument followed by the name (non-keyword!):

        >>> traj.f_add_result(PickleResult,'group1.group2.myresult', 1666, x=3, y=3, comment='Example!')

        Additional arguments (here `1666`) or keyword arguments (here `x=3, y=3`) are passed
        onto the constructor of the result.


        Adds the full name of the current node
        as prefix to the name of the result.
        If current node is the trajectory (root) adds the prefix `'results.trajectory'` to the full name.
        If current node is a single run (root) adds the prefix `'results.run_08%d%'` to the full name
        where `'08%d'` is replaced by the index of the current run.

        '''
        return self._nn_interface._add_generic(self,type_name = RESULT,
                                               group_type_name = RESULT_GROUP,
                                               args=args,kwargs=kwargs)


class DerivedParameterGroup(NNGroupNode):
    ''' Group node in your trajectory, hanging below `traj.derived_parameters`.

    You can add other groups or parameters to it.
    '''
    def f_add_derived_parameter_group(self,name):
        '''Adds an empty derived parameter group under the current node.

        Adds the full name of the current node
        as prefix to the name of the group.
        If current node is the trajectory (root) adds the prefix `'derived_parameters.trajectory'`
        to the full name.
        If current node is a single run (root) adds the prefix `'derived_parameters.run_08%d%'`
        to the full name
        where `'08%d'` is replaced by the index of the current run.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        '''

        return self._nn_interface._add_generic(self,type_name = DERIVED_PARAMETER_GROUP,
                                               group_type_name = DERIVED_PARAMETER_GROUP,
                                               args = (name,), kwargs={})

    def f_add_derived_parameter(self,*args,**kwargs):
        ''' Adds a derived parameter under the current group.

        Similar to
        :func:`~pypet.naturalnaming.ParameterGroup.f_add_parameter`.

        Naming prefixes are added as in
        :func:`~pypet.naturalnaming.DerivedParameterGroup.f_add_derived_parameter_group`
        '''
        return self._nn_interface._add_generic(self,type_name = DERIVED_PARAMETER,
                                               group_type_name = DERIVED_PARAMETER_GROUP,
                                               args=args,kwargs=kwargs)



class ConfigGroup(NNGroupNode):
    ''' Group node in your trajectory, hanging below `traj.config`.

    You can add other groups or parameters to it.
    '''
    def f_add_config_group(self,name):
        '''Adds an empty config group under the current node.

        Adds the full name of the current node
        as prefix to the name of the group.
        If current node is the trajectory or single run (root), the prefix `'config'`
        is added to the full name.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        '''
        return self._nn_interface._add_generic(self,type_name = CONFIG_GROUP,
                                               group_type_name = CONFIG_GROUP,
                                               args = (name,), kwargs={})

    def f_add_config(self,*args,**kwargs):
        ''' Adds config under the current group.

        Similar to
        :func:`~pypet.naturalnaming.ParameterGroup.f_add_parameter`.

        If current group is the trajectory the prefix `'config'` is added to the name.

        '''
        return self._nn_interface._add_generic(self,type_name = CONFIG,
                                               group_type_name = CONFIG_GROUP,
                                               args=args,kwargs=kwargs)




