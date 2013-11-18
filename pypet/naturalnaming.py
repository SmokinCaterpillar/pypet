""" Module to handle a trajectory's tree containing groups and leaves (aka parameters and results).

Contains the following classes:

    * :class:`~pypet.naturalnaming.NaturalNamingInterface`

        Class that handles interaction with the tree.

        Usually functions of tree nodes allowing the manipulation of their child nodes or
        themselves are more or less empty skeletons that pass a request over to the NNInterface.
        The advantage is that the actual nodes are rather slim objects and the computations
        are hidden in the NNInterface.

        The NNInterface handles requests like the addition or removal of groups and leaves or
        search for particular nodes in the tree.

    * :class:`~pypet.naturalnaming.NNTreeNode`

        Abstract definition of a general node in the tree, subclasses
        :class:`~pypet.annotations.WithAnnotations`.

    * :class:`~pypet.naturalnaming.NNGroupNode`

        Abstract definition of a group node, subclasses the `NNTreeNode`.

    * :class:`~pypet.naturalnaming.NNLeafNode`

        Abstract definition of a leaf node, subclasses the `NNTreeNode`.

    * :class:`~pypet.naturalnaming.ConfigGroup`

        A group node for config parameters. Provides functionality to add more config groups
        or parameters, subclasses the `GroupNode`.

    * :class:`~pypet.naturalnaming.ParameterGroup`,
      :class:`~pypet.naturalnaming.DerivedParameterGroup` ,
      :class:`~pypet.naturalnaming.ResultGroup`

        Analogous to the above

"""

__author__ = 'Robert Meyer'

import inspect
import itertools as itools
import logging

from pypet.utils.decorators import deprecated
import pypet.pypetexceptions as pex
from pypet import pypetconstants
from pypet.annotations import WithAnnotations
from pypet.utils.helpful_classes import ChainMap



#For fetching:
STORE = 'STORE' #We want to store stuff with the storage service
LOAD = 'LOAD' #We want to load stuff with the storage service
REMOVE = 'REMOVE' #We want to remove stuff, potentially from disk


#Group Constants
RESULT = 'RESULT'
RESULT_GROUP = 'RESULTGROUP'
PARAMETER = 'PARAMETER'
PARAMETER_GROUP = 'PARAMETER_GROUP'
DERIVED_PARAMETER = 'DERIVED_PARAMETER'
DERIVED_PARAMETER_GROUP = 'DERIVED_PARAMETER_GROUP'
CONFIG = 'CONFIG'
CONFIG_GROUP = 'CONFIG_GROUP'

# For fast searching of nodes in the tree:
# If there are more candidate solutions found by the fast search
# (that need to be checked sequentially) than this number
# a slow search with a full tree traversal is initiated.
FAST_UPPER_BOUND = 2




class NNTreeNode(WithAnnotations):
    """ Abstract class to define the general node in the trajectory tree."""
    def __init__(self,full_name,leaf):
        super(NNTreeNode,self).__init__()

        self._rename(full_name)

        self._leaf=leaf # Whether or not a node is a leaf, aka terminal node.

    @property
    def v_depth(self):
        """ Depth of the node in the trajectory tree."""
        return self._depth

    @property
    @deprecated( msg='Please use `v_is_leaf` instead.')
    def v_leaf(self):
        """Whether node is a leaf or not (i.e. it is a group node)

        DEPRECATED: Please use v_is_leaf!

        """
        return self.v_is_leaf

    @property
    def v_is_leaf(self):
        """Whether node is a leaf or not (i.e. it is a group node)"""
        return self._leaf

    @deprecated( msg='Please use property `v_is_root` instead.')
    def f_is_root(self):
        """Whether the group is root (True for the trajectory and a single run object)

        DEPRECATED: Please use property v_is_root!

        """
        return self.v_is_root

    @property
    def v_is_root(self):
        """Whether the group is root (True for the trajectory and a single run object)"""
        return self._depth==0

    @property
    def v_full_name(self):
        """ The full name, relative to the root node.

        The full name of a trajectory or single run is the empty string since it is root.

        """
        return self._full_name

    @property
    def v_name(self):
        """ Name of the node"""
        return self._name

    @property
    def v_location(self):
        """ Location relative to the root node.

        The location of a trajectory or single run is the empty string since it is root.

        """
        return self._full_name[:-len(self._name)-1]

    @property
    def v_creator_name(self):
        """ The name of the creator of the node.

        The creator name is either the name of a single run
        (e.g. 'run_00000009') or 'trajectory'.

        """
        return self._creator_name

    def _rename(self, full_name):
        """ Renames the parameter or result."""
        split_name = full_name.split('.')

        # The full name of root is '' (the empty string)
        if full_name != '':
            self._depth = len(split_name)
        else:
            self._depth=0

        self._full_name=full_name
        self._name=split_name[-1]

        # In case of results and derived parameters the creator can be a single run
        # parameters and configs are always created by the original trajectory
        if self._depth>1 and split_name[0] in ['results', 'derived_parameters']:
            self._creator_name = split_name[1]
        else:
            self._creator_name = 'trajectory'


    def f_get_class_name(self):
        """ Returns the class name of the parameter or result or group.

        Equivalent to `obj.__class__.__name__`

        """
        return self.__class__.__name__



class NNLeafNode(NNTreeNode):
    """ Abstract class interface of result or parameter (see :mod:`pypet.parameter`)"""

    def __init__(self,full_name,comment,parameter):
        super(NNLeafNode,self).__init__(full_name=full_name,leaf=True)
        self._parameter=parameter

        self._comment=''
        self.v_comment=comment


    @property
    def v_comment(self):
        """Should be a nice descriptive comment"""
        return self._comment

    @v_comment.setter
    def v_comment(self, comment):
        """Changes the comment"""
        comment = str(comment)
        self._comment=comment


    def f_supports_fast_access(self):
        """Whether or not fast access can be supported by the parameter or result.

        ABSTRACT: Needs to be implemented by subclass.

        """
        raise NotImplementedError('You should implement this!')


    @property
    @deprecated(msg='Please use function `f_supports_fast_access()` instead.')
    def v_fast_accessible(self):
        """Whether or not fast access can be supported by the Parameter or Result

        DEPRECATED: Please use function `f_supports_fast_access` instead!

        """
        return self.f_supports_fast_access()

    @property
    @deprecated(msg='Please use `v_is_parameter` instead.')
    def v_parameter(self):
        """Whether the node is a parameter or not (i.e. a result)

        DEPRECATED: Please use `v_is_parameter` instead!

        """
        return self.v_is_parameter

    @property
    def v_is_parameter(self):
        """Whether the node is a parameter or not (i.e. a result)"""
        return self._parameter

    def f_val_to_str(self):
        """ Returns a string summarizing the data handled by the parameter or result

        ABSTRACT: Needs to be implemented by subclass, otherwise the empty string is returned.

        """
        return ''


    def __str__(self):
        """ String representation of the parameter or result.

        If not specified in subclass this is simply the full name.

        """
        return self.v_full_name



    def _store_flags(self):
        """ Currently not used because I let the storage service infer how to store
        stuff from the data itself.

        If you write your own parameter or result you can implement this function
        to make specifications on how to store data,
        see also :func:`pypet.storageservice.HDF5StorageService.store`.

        :returns: {} (Empty dictionary)

        """
        return {}

    def _store(self):
        """Method called by the storage service for serialization.

        The method converts the parameter's or result's value(s) into  simple
        data structures that can be stored to disk.
        Returns a dictionary containing these simple structures.

        Understood basic structures are

        * python natives (int, long, str,bool,float,complex)

        * python lists and tuples

        * numpy natives arrays, and matrices of type
          np.int8-64, np.uint8-64, np.float32-64, np.complex, np.str

        * python dictionaries of the previous types (flat not nested!)

        * pandas data frames

        * object tables (see :class:`~pypet.parameter.ObjectTable`)

        :return: A dictionary containing basic data structures.

        ABSTRACT: Needs to be implemented by subclass

        """
        raise NotImplementedError('Implement this!')

    def _load(self, load_dict):
        """Method called by the storage service to reconstruct the original result.

        Data contained in the load_dict is equal to the data provided by the result or parameter
        when previously called with _store().

        :param load_dict:

            The dictionary containing basic data structures, see also
            :func:`~pypet.naturalnaming.NNLeafNode._store`.


        ABSTRACT: Needs to be implemented by subclass

        """
        raise  NotImplementedError('Implement this!')


    def f_is_empty(self):
        """Returns true if no data is handled by a result or parameter.

        ABSTRACT: Needs to be implemented by subclass

        """
        raise NotImplementedError('You should implement this!')

    def f_empty(self):
        """Removes all data from the result or parameter.

        If the result has already been stored to disk via a trajectory and a storage service,
        the data on disk is not affected by `f_empty`.

        Yet, this function is particularly useful if you have stored very large data to disk
        and you want to free some memory on RAM but still keep the skeleton of your result or
        parameter.

        Note that freeing RAM requires that all references to the data are deleted. If you
        reference the data somewhere else in your code, the data is not erased from RAM.

        ABSTRACT: Needs to be implemented by subclass

        """
        raise NotImplementedError('You should implement this!')

class NaturalNamingInterface(object):
    """Class to manage the tree structure of a trajectory.

    Handles search, insertion, etc.

    """
    def __init__(self, root_instance):

        # The root instance is a reference to the top node of the tree. This is either
        # a single run or the parent trajectory. This can change during runtime!
        self._root_instance = root_instance

        self._run_or_traj_name= root_instance.v_name

        self._logger = logging.getLogger('pypet.trajectory.NNTree=' +
                                         self._root_instance.v_name)

        # Dictionary containing ALL leaves. Keys are the full names and values the parameter
        # and result instances.
        self._flat_leaf_storage_dict = {}

        # Nested dictionary containing names (not full names) as keys. Values are dictionaries
        # containing the full names as keys and the parameters and results as values.
        self._nodes_and_leaves = {}

        # Twofold nested dictionary: Outer dictionary has the creator name
        # (e.g. trajectory or run_00000000) as keys.
        # Values are dictionaries containing names (not full names) as keys and dictionaries
        # of parameter and result instances as values and their full names as keys (as above).
        # This dictionary is used for fast search in case a trajectory is told to behave like
        # a particular run (by setting the v_as_run property).
        self._nodes_and_leaves_runs_sorted={}

        # List of names that are taboo. The user cannot create parameters or results that
        # contain these names.
        self._not_admissible_names = set(dir(self)) | set( dir(self._root_instance) )


    def _map_type_to_dict(self,type_name):
        """ Maps a an instance type representation string (e.g. 'RESULT')
        to the corresponding dictionary in root.

        """
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
        """ Changes the root of the whole tree.

        This is called on creation of single runs to take over the tree from its parent
        trajectory and vice versa.

        """
        new_root._children = self._root_instance._children
        self._root_instance = new_root
        self._run_or_traj_name= self._root_instance.v_name

        self._logger = logging.getLogger('pypet.trajectory.NNTree=' +
                                         self._root_instance.v_name)

    def _get_fast_access(self):
        return self._root_instance.v_fast_access

    def _get_search_strategy(self):
        return self._root_instance.v_search_strategy

    def _get_check_uniqueness(self):
        return self._root_instance.v_check_uniqueness


    def _fetch_from_string(self,store_load, name, args, kwargs):
        """Method used by f_store/load/remove_items to find a corresponding item in the tree.

        :param store_load:

            String constant specifying if we want to store, load or remove.
            The corresponding constants are defined at the top of this module.

        :param name: String name of item to store, load or remove.

        :param args: Additional arguments passed to the storage service

        :param kwargs: Additional keyword arguments passed to the storage service

        :return:

            A formatted request that can be handled by the storage service, aka
            a tuple: (msg, item_to_store_load_or_remove, args, kwargs)

        """
        if not isinstance(name, basestring):
            raise TypeError('No string!')

        node = self._root_instance.f_get(name)

        return self._fetch_from_node(store_load,node,args,kwargs)

    def _fetch_from_node(self,store_load, node,args,kwargs):
        """Method used by f_store/load/remove_items to find a corresponding item in the tree.

        :param store_load: String constant specifying if we want to store, load or remove
        :param node: A group, parameter or result instance.
        :param args: Additional arguments passed to the storage service
        :param kwargs: Additional keyword arguments passed to the storage service

        :return:

            A formatted request that can be handled by the storage service, aka
            a tuple: (msg, item_to_store_load_or_remove, args, kwargs)

        """
        msg = self._node_to_msg(store_load,node)

        return msg,node,args,kwargs

    def _fetch_from_tuple(self,store_load,store_tuple,args,kwargs):
        """ Method used by f_store/load/remove_items to find a corresponding item in the tree.

        The input to the method should already be in the correct format, this method only
        checks for sanity.

        :param store_load: String constant specifying if we want to store, load or remove

        :param store_tuple:

            Tuple already in correct format (msg, item, args, kwargs). If args and kwargs
            are not given, they are taken from the supplied parameters

        :param args: Additional arguments passed to the storage service if len(store_tuple)<3

        :param kwargs: Additional keyword arguments passed to the storage service if len(store_tuple)<4


        :return:

            A formatted request that can be handled by the storage service, aka
            a tuple: (msg, item_to_store_load_or_remove, args, kwargs)

        """

        node = store_tuple[1]
        msg = store_tuple[0]
        if len(store_tuple) > 2:
            args = store_tuple[2]
        if len(store_tuple) > 3:
            kwargs = store_tuple[3]
        if len(store_tuple) > 4:
            print store_tuple
            raise ValueError('Your argument tuple has to many entries, please call '
                            'store with [(msg,item,args,kwargs),...]')

        ##dummy test
        _ = self._fetch_from_node(store_load,node, args, kwargs)

        return msg,node,args,kwargs


    @staticmethod
    def _node_to_msg(store_load,node):
        """Maps a given node and a store_load constant to the message that is understood by
        the storage service.

        """
        if node.v_is_leaf:
            if store_load ==STORE:
                return pypetconstants.LEAF
            elif store_load == LOAD:
                return pypetconstants.LEAF
            elif store_load == REMOVE:
                 return pypetconstants.REMOVE
        else:
            if store_load ==STORE:
                return pypetconstants.GROUP
            elif store_load == LOAD:
                return pypetconstants.GROUP
            elif store_load == REMOVE:
                 return pypetconstants.REMOVE


    def _fetch_items(self, store_load, iterable, args, kwargs):
        """ Method used by f_store/load/remove_items to find corresponding items in the tree.


        :param store_load:

            String constant specifying if we want to store, load or remove.
            The corresponding constants are defined at the top of this module.

        :param iterable:

            Iterable over items to look for in the tree. Can be strings specifying names,
            can be the item instances themselves or already correctly formatted tuples.

        :param args: Additional arguments passed to the storage service

        :param kwargs:

            Additional keyword arguments passed to the storage service.
            Two optional keyword arguments are popped and used by this method.

            only_empties:

                Can be in kwargs if only empty parameters and results should be considered.

            non_empties:

                Can be in kwargs if only non-empty parameters and results should be considered.


        :return:

            A list containing formatted tuples.
            These tuples can be handled by the storage service, they have
            the following format: (msg, item_to_store_load_or_remove, args, kwargs)

        """
        only_empties = kwargs.pop('only_empties', False)

        non_empties = kwargs.pop('non_empties', False)


        item_list = []
        # Iterate through the iterable and apply the appropriate fetching method via try and error.
        for iter_item in iterable:

            try:
                item_tuple = self._fetch_from_string(store_load,iter_item,args,kwargs)
            except TypeError:
                try:
                    item_tuple = self._fetch_from_node(store_load,iter_item,args,kwargs)
                except AttributeError:
                    item_tuple = self._fetch_from_tuple(store_load,iter_item,args,kwargs)

            item = item_tuple[1]
            msg = item_tuple[0]

            if item.v_is_leaf:
                if only_empties and not item.f_is_empty():
                    continue
                if non_empties and item.f_is_empty():
                    continue

            # Explored Parameters cannot be removed, this would break the underlying hdf5 file
            # structure
            if (msg == pypetconstants.REMOVE and
                        item.v_full_name in self._root_instance._explored_parameters):
                raise TypeError('You cannot remove an explored parameter of a trajectory stored '
                                'into an hdf5 file.')


            item_list.append(item_tuple)

        return item_list

    def _remove_subtree(self,start_node,name):
        """Removes a subtree from the trajectory tree.

        Does not delete stuff from disk only from RAM.

        :param start_node: The parent node from where to start
        :param name: Name of child which will be deleted and recursively all nodes below the child

        """
        def _remove_subtree_inner(node):

            if not node.v_is_leaf:
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
        """Deletes a single node from the tree.

        Removes all references to the node.

        Note that the 'parameters', 'results', 'derived_parameters', and 'config' groups
        hanging directly below root cannot be deleted. Also the root node itself cannot be
        deleted. (This would cause a tremendous wave of uncontrollable self destruction, which
        would finally lead to the Apocalypse!)

        """
        full_name = node.v_full_name
        name = node.v_name
        run_name = node.v_creator_name

        root = self._root_instance


        if full_name in ['parameters','results','derived_parameters','config','']:
            # You cannot delete root or nodes in first layer
            return

        if node.v_is_leaf:
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

                # If we remove an explored parameter and the trajectory was not stored to disk
                # before we need to check if there are no explored parameters left. If so
                # the length of the trajectory is shrunk to 1.
                if len(root._explored_parameters)==0:
                    if root._stored:
                       self._logger.warning('You removed an explored parameter, but your '
                                            'trajectory was already stored to disk. So it is '
                                            'not shrunk!')
                    else:
                        root.f_shrink()

            del self._flat_leaf_storage_dict[full_name]

        else:
            del root._groups[full_name]

        # Finally remove all references in the dictionaries for fast search
        del self._nodes_and_leaves[name][full_name]
        if len(self._nodes_and_leaves[name]) == 0:
            del self._nodes_and_leaves[name]

        del self._nodes_and_leaves_runs_sorted[name][run_name][full_name]
        if len(self._nodes_and_leaves_runs_sorted[name][run_name]) == 0:
            del self._nodes_and_leaves_runs_sorted[name][run_name]
            if len(self._nodes_and_leaves_runs_sorted[name]) == 0:
                del self._nodes_and_leaves_runs_sorted[name]


    def _remove_node_or_leaf(self, instance, remove_empty_groups):
        """Removes a single node from the tree.

        Only from RAM not from hdf5 file!

        :param instance: The node to be deleted

        :param remove_empty_groups:

            Whether groups that become empty due to deletion of the node should be erased as well.

        """
        full_name = instance.v_full_name
        split_name = full_name.split('.')
        self._remove_recursive(self._root_instance, split_name, remove_empty_groups)

    def _remove_recursive(self,actual_node,split_name,remove_empty_groups):
        """Removes a given node from the tree.

        Starts from a given node and walks recursively down the tree to the location of the node
        we want to remove.

        We need to walk from a start node in case we want to check on the way back whether we got
        empty group nodes due to deletion.

        :param actual_node: Current node

        :param split_name: List of names to get the next nodes.

        :param remove_empty_groups:

             Whether groups that become empty due to deletion of the node should be erased as well.

        :return: True if node was deleted, otherwise False

        """

        # If the names list is empty, we have reached the node we want to delete.
        if len(split_name)== 0:
            self._delete_node(actual_node)
            return True

        # Otherwise get the next node by using the first name in the list
        name = split_name.pop(0)
        child = actual_node._children[name]

        # Recursively walk down the tree
        if self._remove_recursive(child, split_name, remove_empty_groups):
            del actual_node._children[name]
            del child

            # Remove empty groups on the way back if desired
            if remove_empty_groups and len(actual_node._children) == 0:
                self._delete_node(actual_node)
                return True

        return False

    def _shortcut(self, name):
        """Maps a given shortcut to corresponding name

        * 'run_X' or 'r_X' to 'run_XXXXXXXXX'

        * 'cr' or 'currentrun' or 'current_run' to the current run name in case of a
          single run instance

        * 'par' or 'param' to 'parameters'

        * 'dpar' or 'dparam' to 'derived_parameters'

        * 'res' to 'results'

        * 'conf' to 'config'

        * 'tr' or 'traj' to 'trajectory'

        :return: The mapped name or None if no shortcut is matched.

        """
        expanded = None

        if name.startswith('run_') or name.startswith('r_'):
            split_name = name.split('_')
            if len(split_name) == 2:
                index = split_name[1]
                if index.isdigit():
                    if len(index) < pypetconstants.FORMAT_ZEROS:
                        expanded = pypetconstants.FORMATTED_RUN_NAME % int(index)

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
        """Adds the correct sub branch prefix to a given name.

        Usually the prefix is the full name of the parent node. In case items are added
        directly to the trajectory the prefixes are chosen according to the matching subbranch.

        For example, this could be 'parameters' for parameters or 'results.run_00000004' for
        results added to the fifth single run.

        :param name:

            Name of new node. Colon notation is possible to generate group nodes on the
            fly (e.g. 'mynewgroupA.mynewgroupB.myresult').

        :param start_node:

            Parent node under which the new node should be added.

        :param group_type_name:

            Type name of subbranch the item belongs to (e.g. 'PARAMETER_GROUP', 'RESULT_GROUP' etc).


        :return: The name with the added prefix.

        """

        ## If we add an instance with a correct full name at root, we do not need to add the prefix
        if start_node.v_is_root:
            for prefix in ('results','parameters','derived_parameters','config'):
                if name.startswith(prefix):
                    return name

        root=self._root_instance

        # If the start node of our insertion is root or one below root we might need to add prefixes.
        if start_node.v_depth<2:
            # In case of derived parameters and results we also need to add prefixes containing the
            # subbranch and the current run or trajectory.
            # For instance, a prefix could be 'results.run_00000007'.
            if group_type_name == DERIVED_PARAMETER_GROUP:

                add=''

                if (not ((name.startswith(pypetconstants.RUN_NAME) and
                                  len(name) ==len(pypetconstants.RUN_NAME)+pypetconstants.FORMAT_ZEROS) or
                                  name == 'trajectory') ):

                    if root._is_run:
                        add= start_node.v_name + '.'
                    else:
                        add= 'trajectory.'

                if start_node.v_depth== 0:
                    add = 'derived_parameters.' + add

                return add+name


            elif group_type_name == RESULT_GROUP:

                add = ''

                if (not ((name.startswith(pypetconstants.RUN_NAME) and
                                  len(name) ==len(pypetconstants.RUN_NAME)+pypetconstants.FORMAT_ZEROS) or
                                  name == 'trajectory') ):

                    if root._is_run:
                        add= start_node.v_name + '.'
                    else:
                        add= 'trajectory.'

                if start_node.v_depth== 0:
                    add = 'results.' + add

                return add+name

        # If the start node is root and we have a config or parameter the prefixes are rather
        # simple:
        if start_node.v_is_root:

            if group_type_name == PARAMETER_GROUP:
                return 'parameters.'+name

            if group_type_name == CONFIG_GROUP:
                return 'config.'+name

        return name


    def _add_from_leaf_instance(self, start_node, instance):
        """Adds a given parameter or result instance to the tree.

        Checks to which subtree the instances belongs and calls
        :func:`~pypet.naturalnaming.NaturalNamingInterface._add_generic` with the corresponding
        matching arguments

        :param start_node: The parent node that was called to add the instance to

        :param instance: The instance to add

        :return: The added parameter or result

        """
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
        """Adds a new group node to the tree based on the group's name.

        Checks to which subtree the group belongs and calls
        :func:`~pypet.naturalnaming.NaturalNamingInterface._add_generic` with the corresponding
        matching arguments.

        :param start_node: The parent node that was called to add the group to

        :param instance: The name of the new group

        :return: The new added group

        """
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



    def _add_generic(self,start_node, type_name, group_type_name, args, kwargs):
        """Adds a given item to the tree irrespective of the subtree.

        Infers the subtree from the arguments.

        :param start_node: The parental node the adding was initiated from

        :param type_name:

            The type of the new instance. Whether it is a parameter, parameter group, config,
            config group, etc. See the name of the corresponding constants at the top of this
            python module.


        :param group_type_name:

            Type of the subbranch. i.e. whether the item is added to the 'parameters',
            'results' etc. These subbranch types are named as the group names
            (e.g. 'PARAMETER_GROUP') in order to have less constants.
            For all constants used see beginning of this python module.

        :param args:

            Arguments specifying how the item is added.

            If len(args)==1 and the argument is the a given instance of a result or parameter,
            this one is added to the tree.

            Otherwise it is checked if the first argument is a class specifying how to
            construct a new item and the second argument is the name of the new class.

            If the first argument is not a class but a string, the string is assumed to be
            the name of the new instance.

            Additional args are later on used for the construction of the instance.

        :param kwargs:

            Additional keyword arguments that might be handed over to the instance constructor.

        :return: The new added instance

        """
        if type_name == group_type_name:
            # Wee add a group node, this can be only done by name:
            name = args[0]
            instance = None
            constructor = None

        else:
            ## We add a leaf node in the end:
            args = list(args)

            create_new = True

            # First check if the item is already a given instance
            if len(args) == 1 and len(kwargs)==0:
                item = args[0]
                try:
                    name = item.v_full_name
                    instance = item
                    constructor = None

                    create_new = False
                except AttributeError:
                    pass

            # If the item is not an instance yet, check if args[0] is a class and args[1] is
            # a string describing the new name of the instance.
            # If args[0] is not a class it is assumed to be the name of the new instance.
            if create_new:
                if inspect.isclass(args[0]):
                    constructor = args.pop(0)
                else:
                    constructor = None

                instance = None

                name = args.pop(0)

        # Check if the name fulfils the prefix conditions, if not change the name accordingly.
        name = self._add_prefix(name,start_node,group_type_name)


        return self._add_to_tree(start_node,name, type_name, group_type_name, instance,
                                            constructor, args,kwargs)


    def _add_to_tree(self, start_node, name, type_name, group_type_name,
                            instance, constructor, args, kwargs ):
        """Adds a new item to the tree.

        The item can be an already given instance or it is created new.

        :param start_node:

            Parental node the adding of the item was initiated from.

        :param name:

            Name of the new item

        :param type_name:

            Type of item 'RESULT', 'RESULT_GROUP', 'PARAMETER', etc. See name of constants
            at beginning of the python module.

        :param group_type_name:

            Name of the subbranch the item is added to 'RESULT_GROUP', 'PARAMETER_GROUP' etc.
            See name of constants at beginning of this python module.

        :param instance:

            Here an already given instance can be passed. If instance should be created new
            pass None.

        :param constructor:

            If instance should be created new pass a constructor class. If None is passed
            the standard constructor for the instance is chosen.

        :param args:

            Additional arguments passed to instance construction

        :param kwargs:

            Additional keyword arguments passed to instance construction

        :return: The new added instance

        :raises: ValueError if naming of the new item is invalid

        """

        # First check if the naming of the new item is appropriate
        split_name = name.split('.')

        faulty_names= self._check_names(split_name)

        if faulty_names:
            raise ValueError(
                'Your Parameter/Result/Node `%s` f_contains the following not admissible names: '
                '%s please choose other names.'
                % (name, faulty_names))


        # Then walk iteratively from the start node as specified by the new name and create
        # new empty groups on the fly
        try:
            act_node = start_node
            last_idx = len(split_name)-1
            for idx, name in enumerate(split_name):

                if not name in act_node._children:

                    if idx == last_idx and group_type_name != type_name:
                        # We are at the end of the chain and we add a leaf node

                        new_node = self._create_any_param_or_result(act_node.v_full_name,name,
                                                                    type_name,instance,constructor,
                                                                    args,kwargs)

                        self._flat_leaf_storage_dict[new_node.v_full_name] = new_node


                    else:
                        # We add a group node, can also be intermediate on the fly
                        new_node = self._create_any_group(act_node.v_full_name,name,
                                                          group_type_name)

                    act_node._children[name] = new_node

                    # Add the new instance also to the nested reference dictionaries
                    # to allow fast search
                    if not name in self._nodes_and_leaves:
                        self._nodes_and_leaves[name]={new_node.v_full_name:new_node}
                    else:
                        self._nodes_and_leaves[name][new_node.v_full_name]=new_node

                    run_name = new_node._creator_name
                    if not name in self._nodes_and_leaves_runs_sorted:
                        self._nodes_and_leaves_runs_sorted[name]={run_name:
                                                            {new_node.v_full_name:new_node}}
                    else:
                        if not run_name in self._nodes_and_leaves_runs_sorted[name]:
                            self._nodes_and_leaves_runs_sorted[name][run_name] = \
                                                            {new_node.v_full_name:new_node}
                        else:
                            self._nodes_and_leaves_runs_sorted[name][run_name]\
                                [new_node.v_full_name] = new_node

                else:
                    if idx == last_idx:
                        raise AttributeError('You already have a group/instance `%s` under '
                                             '`%s`' % (name,start_node.v_full_name))


                act_node = act_node._children[name]

            return act_node
        except:
            self._logger.error('Failed adding `%s` under `%s`.' %
                               (name, start_node.v_full_name))
            raise



    def _check_names(self, split_names):
        """Checks if a list contains strings with invalid names.

        Returns a description of the name violations. If names are correct the empty
        string is returned.

        :param split_names: List of strings

        """
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
                faulty_names = '%s %s is already an important shortcut,' % (faulty_names, split_name)


        name = split_names.pop()
        location = '.'.join(split_names)
        if len(name)>= pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH:
            faulty_names = '%s %s is too long the name can only have %d characters but it has %d,' % \
                           (faulty_names,name,len(name),pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH)

        if len(location) >= pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH:
            faulty_names = '%s %s is too long the location can only have %d characters but it has %d,' % \
                           (faulty_names,name,len(location),pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH)

        split_names.append(name)
        return faulty_names



    def _create_any_group(self, location, name, type_name):
        """Generically creates a new group inferring from the `type_name`."""
        if location:
            full_name = '%s.%s' % (location, name)
        else:
            full_name = name


        if type_name == RESULT_GROUP:
            instance= ResultGroup(self,full_name=full_name)

        elif type_name == PARAMETER_GROUP:
            instance= ParameterGroup(self,full_name=full_name)

        elif type_name == CONFIG_GROUP:
            instance= ConfigGroup(self,full_name=full_name)

        elif type_name == DERIVED_PARAMETER_GROUP:
            instance= DerivedParameterGroup(self,full_name=full_name)
        else:
            raise RuntimeError('You shall not pass!')

        self._root_instance._groups[instance.v_full_name]=instance

        return instance


    def _create_any_param_or_result(self, location, name, type_name, instance, constructor,
                                    args, kwargs):
        """Generically creates a novel parameter or result instance inferring from the `type_name`.

        If the instance is already supplied it is NOT constructed new.

        :param location:

            String specifying the location, e.g. 'results.run_00000007.mygroup'

        :param name:

            Name of the new result or parameter. Here the name no longer contains colons.

        :param type_name:

            Whether it is a parameter below parameters, config, derived parameters or whether
            it is a result.

        :param instance:

            The instance if it has been constructed somewhere else, otherwise None.

        :param constructor:

            A constructor used if instance needs to be constructed. If None the current standard
            constructor is chosen.

        :param args:

            Additional arguments passed to the constructor

        :param kwargs:

            Additional keyword arguments passed to the constructor

        :return: The new instance

        """
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

        self._logger.debug('Added `%s` to trajectory.' % full_name)

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
    def _apply_fast_access(data, fast_access):
        """Method that checks if fast access is possible and applies it if desired"""
        if fast_access and data.f_supports_fast_access():
            return data.f_get()
        else:
            return data


    def _iter_nodes(self, node, recursive=False, search_strategy=pypetconstants.BFS):
        """Returns an iterator over nodes hanging below a given start node.

        :param node:

            Start node

        :param recursive:

            Whether recursively also iterate over the children of the start node's children

        :param search_strategy:

            Breadth first search or depth first search

        :return: Iterator

        """
        as_run = self._get_as_run()

        if recursive:
            if search_strategy == pypetconstants.BFS:
                return NaturalNamingInterface._recursive_traversal_bfs(node, as_run)
            elif search_strategy == pypetconstants.DFS:
                return NaturalNamingInterface._recursive_traversal_dfs(node, as_run)
            else:
                raise ValueError('Your search method is not understood!')
        else:
            return node._children.itervalues()


    @staticmethod
    def _iter_leaves(node):
        """ Iterates over all leaves hanging below `node`."""
        for node in node.f_iter_nodes(recursive=True):
            if node.v_is_leaf:
                yield node
            else:
                continue

    def _to_dict(self,node,fast_access = True, short_names=False, copy=True):
        """ Returns a dictionary with pairings of (full) names as keys and instances as values.

        :param fast_access:

            If true parameter or result values are returned instead of the
            instances.

        :param short_names:

            If true keys are not full names but only the names.
            Raises a ValueError if the names are not unique.

        :return: dictionary

        :raises: ValueError

        """

        if (fast_access or short_names)  and not copy:
            raise ValueError('You can not request the original data with >>fast_access=True<< or'
                             ' >>short_names=True<<.')

        # First, let's check if we can return the `flat_leaf_storage_dict` or a copy of that, this
        # is faster than creating a novel dictionary by tree traversal.
        if node.v_is_root:
            temp_dict = self._flat_leaf_storage_dict

            if not fast_access and not short_names:
                if copy:
                    return temp_dict.copy()
                else:
                    return temp_dict

            else:
                iterator = temp_dict.itervalues()
        else:
            iterator=self._iter_leaves(node)

        # If not we need to build the dict by iterating recursively over all leaves:
        result_dict={}
        for val in iterator:
            if short_names:
                new_key = val.v_name
            else:
                new_key = val.v_full_name

            if new_key in result_dict:
                raise ValueError('Your short names are not unique!')

            new_val = self._apply_fast_access(val,fast_access)
            result_dict[new_key]=new_val

        return result_dict


    @staticmethod
    def _make_child_iterator(node, run_name):
        """Returns an iterator over a node's children.

        In case of using a trajectory as a run (setting 'v_as_run') some sub branches
        that do not belong to the run are blinded out.

        """
        if run_name is not None and node.v_depth == 1 and run_name in node._children:
            # Only consider one particular run and blind out the rest
            return [node._children[run_name]]
        else:
            return node._children.itervalues()

    @staticmethod
    def _recursive_traversal_bfs(node, run_name=None):
        """Iterator function traversing the tree below `node` in breadth first search manner.

        If `run_name` is given only sub branches of this run are considered and the rest is
        blinded out.

        """
        queue = iter([node])
        start = True

        while True:
            try:
                item = queue.next()
                if start:
                    start = False
                else:
                    yield item

                if not item._leaf:
                    queue = itools.chain(queue,
                                     NaturalNamingInterface._make_child_iterator(item, run_name))
            except StopIteration:
                break


    @staticmethod
    def _recursive_traversal_dfs(node, run_name=None):
        """Iterator function traversing the tree below `node` in depth first search manner.

        If `run_name` is given only sub branches of this run are considered and the rest is
        blinded out.

        """
        if not node._leaf:
            for child in NaturalNamingInterface._make_child_iterator(node, run_name):
                yield child
                for new_node in NaturalNamingInterface._recursive_traversal_dfs(child, run_name):
                    yield new_node



    def _very_fast_search(self, node, key, as_run):
        """Fast search for a node in the tree.

        The tree is not traversed but the reference dictionaries are searched.

        :param node:

            Parent node to start from

        :param key:

            Name of node to find

        :param as_run:

            If given only nodes belonging to this particular run are searched and the rest
            is blinded out.

        :return: The found node

        :raises:

            TooManyGroupsError:

                If search cannot performed fast enough, an alternative search method is needed.

            NotUniqueNodeError:

                If several nodes match the key criterion

        """

        parent_full_name = node.v_full_name

        # First find all nodes where the key matches the (short) name of the node
        if as_run is None:
            candidate_dict = self._nodes_and_leaves[key]
        else:
            temp_dict={}
            if as_run in self._nodes_and_leaves_runs_sorted[key]:
                temp_dict = self._nodes_and_leaves_runs_sorted[key][as_run]
                if len(temp_dict) > FAST_UPPER_BOUND:
                    raise pex.TooManyGroupsError('Too many nodes')

            temp_dict2={}
            if 'trajectory' in self._nodes_and_leaves_runs_sorted[key]:
                temp_dict2 = self._nodes_and_leaves_runs_sorted[key]['trajectory']
                if len(temp_dict2) > FAST_UPPER_BOUND:
                    raise pex.TooManyGroupsError('Too many nodes')

            candidate_dict = ChainMap(temp_dict,temp_dict2)

        # If there are to many potential candidates sequential search might be too slow
        if len(candidate_dict) > FAST_UPPER_BOUND:
            raise pex.TooManyGroupsError('Too many nodes')

        # Next check if the found candidates could be reached from the parent node
        result_node = None
        for goal_name in candidate_dict.iterkeys():

            if goal_name.startswith(parent_full_name):

                # In case of several solutions raise an error:
                if not result_node is None:
                    raise pex.NotUniqueNodeError('Node `%s` has been found more than once,'
                                                 'full name of first found is `%s` and of'
                                                 'second `%s`'
                                                 % (key,goal_name,result_node.v_full_name))

                result_node=candidate_dict[goal_name]

        return result_node

    def _get_as_run(self):
        """ Returns the run name in case of 'v_as_run' is set, otherwise None."""
        if not self._root_instance._is_run:
            return self._root_instance.v_as_run
        else:
            return None

    def _search(self,node,  key, check_uniqueness, search_strategy):
        """ Searches for an item in the tree below `node`

        :param node:

            The parent node below which the search is performed

        :param key:

            Name to search for. Can be the short name, the full name or parts of it

        :param check_uniqueness:

            Whether to check if search yields unique items

        :param search_strategy:

            BFS or DFS

        :return: The found node

        """
        as_run = self._get_as_run()

        # First the very fast search is tried that does not need tree traversal.
        try:
            return self._very_fast_search(node, key, as_run)
        except pex.TooManyGroupsError:
            pass
        except pex.NotUniqueNodeError:
            if check_uniqueness:
                raise
            else:
                pass

        # Slowly traverse the entire tree
        nodes_iterator = self._iter_nodes(node, recursive=True,
                                                search_strategy=search_strategy)
        result_node = None
        for child in nodes_iterator:
            if key == child.v_name:

                # If result_node is not None means that we care about uniqueness and the search
                # has found more than a single solution.
                if not result_node is None:
                    raise pex.NotUniqueNodeError('Node `%s` has been found more than once,'
                                                 'full name of first found is `%s` and of '
                                                 'second `%s`'
                                                 % (key,child.v_full_name,result_node.v_full_name))

                result_node =  child
                # If we do not care about uniqueness we can return the first finding.
                if not check_uniqueness:
                    return result_node

        return result_node



    def _get(self,node, name, fast_access, check_uniqueness, search_strategy):
        """Searches for an item (parameter/result/group node) with the given `name`.

        :param node: The node below which the search is performed

        :param name: Name of the item (full name or parts of the full name)

        :param fast_access: If the result is a parameter, whether fast access should be applied.

        :param check_uniqueness:

            Whether it should be checked if the name unambiguously yields a single result.

        :param search_strategy: The search strategy (default and recommended is BFS)

        :return:

            The found instance (result/parameter/group node) or if fast access is True and you
            found a parameter or result that supports fast access, the contained value is returned.

        :raises:

            AttributeError if no node with the given name can be found

        """

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

        ## Check in O(1) if the item is one of the start node's children
        if len(split_name)==1 and not check_uniqueness:
            result = node._children.get(key,None)
        else:
            result = None

        if result is None:
            # Check in O(d) first if a full parameter/result name is given and
            # we might be able to find it in the flat storage dictionary or the group dictionary.
            # Here `d` refers to the depth of the tree
            fullname = '.'.join(split_name)

            if fullname.startswith(node.v_full_name):
                new_name = fullname
            else:
                new_name = node.v_full_name + '.' + fullname

            if new_name in self._flat_leaf_storage_dict:
                return self._apply_fast_access(self._flat_leaf_storage_dict[new_name],
                                                     fast_access=fast_access)

            if new_name in self._root_instance._groups:
                return self._root_instance._groups[new_name]

        # Check in O(N) with `N` number of groups and nodes
        # [Worst Case O(N), average case is better since looking into a single dict costs O(1)].
        # If `check_uniqueness=True`, search is slower since the full tree
        # is searched and we always need O(N).
        result = node
        for key in split_name:
            result = self._search(result,key, check_uniqueness, search_strategy)

        if result is None:
            raise AttributeError('The node or param/result `%s`, cannot be found.' % name)
        if result.v_is_leaf:
            return self._apply_fast_access(result, fast_access)
        else:
            return result


class NNGroupNode(NNTreeNode):
    """A group node hanging somewhere under the trajectory or single run root node.

    You can add other groups or parameters/results to it.

    """
    def __init__(self, nn_interface=None, full_name=''):
        super(NNGroupNode,self).__init__(full_name,leaf=False)
        self._children={}
        self._nn_interface=nn_interface

    def __str__(self):
        if not self.v_is_root:
            name = self.v_full_name
        else:
            name = self.v_name

        return '<%s>: %s: %s' % (self.f_get_class_name(),name,
                                 str([(key,str(type(val)))
                                      for key,val in self._children.iteritems()]))

    def f_children(self):
        """Returns the number of children of the group"""
        return len(self._children)

    def f_has_children(self):
        """Checks if node has children or not"""
        return len(self._children) == 0

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
        """Removes a child of the group.

        Note that groups and leaves are only removed from the current trajectory in RAM.
        If the trajectory is stored to disk, this data is not affected. Thus, removing children
        can be only be used to free RAM memory!

        If you want to free memory on disk via your storage service,
        use :func:`~pypet.trajectory.Trajectory.f_remove_items` of your trajectory.

        :param name: Name of child

        :param recursive:

            Must be true if child is a group that has children. Will remove
            the whole subtree in this case. Otherwise a Type Error is thrown.

        :raises:

            TypeError if recursive is false but there are children below the node.

            ValueError if child does not exist.

        """
        if not name in self._children:
                raise ValueError('Your group `%s` does not contain the child `%s`.' %
                                (self.v_full_name,name))

        else:
            child = self._children[name]

            if not child.v_is_leaf and child.f_has_children and not recursive:
                raise TypeError('Cannot remove child. It is a group with children. Use'
                                ' f_remove with >>recursive = True')
            else:
                self._nn_interface._remove_subtree(self,name)


    def f_contains(self, item, recursive = True):
        """Checks if the node contains a specific parameter or result.

        It is checked if the item can be found via the
        :func:`~pypet.naturalnaming.NNGroupNode.f_get` method.

        :param item: Parameter/Result name or instance.

            If a parameter or result instance is supplied it is also checked if
            the provided item and the found item are exactly the same instance, i.e.
            `id(item)==id(found_item)`.

        :param recursive:

            Whether the whole sub tree under the group should be checked or only
            its immediate children. Default is the whole sub tree.
            If `recursive=False` you must only specify the name not the full name.

        :return: True or False

        """

        # Check if an instance or a name was supplied by the user
        try:
            search_string = item.v_full_name
            name = item.v_name
        except AttributeError:
            search_string = item
            name = item
            item = None

        # # If the name to search for is the full name, we need to remove the name of the parent
        # # node for faster search
        # try:
        #     if search_string.startswith(self.v_full_name) and self.v_full_name != '':
        #         _, _, search_string = search_string.partition(self.v_full_name)
        # except AttributeError:
        #     return False

        if recursive:
            try:
                result = self.f_get(search_string)
            except AttributeError:
                return False
        else:
            if name in self._children:
                result = self._children[name]
            else:
                return False

        if item is not None:
            return id(item) == id(result)
        else:
            return True

    def __setattr__(self, key, value):
        if key.startswith('_'):
            # We set a private item
            self.__dict__[key] = value
        elif hasattr(self.__class__,key):
            # If we set a property we need this work around here:
            python_property = getattr(self.__class__,key)
            if python_property.fset is None:
                raise AttributeError('%s is read only!' % key)
            else:
                python_property.fset(self,value)
        else:
            # Otherwise we will set a value to an existing parameter.
            # Only works if the parameter exists. There is no new parameter created!
            instance = self.f_get(key)

            if not instance.v_is_parameter:
                raise AttributeError('You cannot assign values to a tree node or a list of nodes '
                                     'and results, it only works for parameters ')

            instance.f_set(value)

    def __getitem__(self, item):
        """Equivalent to calling `f_get(item)`.

        Per default the item is returned and fast access is not applied.

        """
        return self.f_get(item)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError('Trajectory node does not contain `%s`' % name)

        if not '_nn_interface' in self.__dict__:
            raise AttributeError('This is to avoid pickling issues')

        return self._nn_interface._get(self,name,fast_access=self._nn_interface._get_fast_access(),
                                       check_uniqueness=self._nn_interface._get_check_uniqueness(),
                                       search_strategy=self._nn_interface._get_search_strategy())

    def f_iter_nodes(self, recursive=False, search_strategy=pypetconstants.BFS):
        """Iterates over nodes hanging below this group.

        :param recursive: Whether to iterate the whole sub tree or only immediate children.

        :param search_strategy: Either BFS or DFS (BFS recommended)

        :return: Iterator over nodes

        """
        return self._nn_interface._iter_nodes(self,recursive=recursive,
                                             search_strategy=search_strategy)


    def f_iter_leaves(self):
        """Iterates (recursively) over all leaves hanging below the current group."""
        return self._nn_interface._iter_leaves(self)


    def f_get(self, name, fast_access=False, check_uniqueness=False,
              search_strategy=pypetconstants.BFS):
        """Searches for an item (parameter/result/group node) with the given `name`.

        :param name: Name of the item (full name or parts of the full name)

        :param fast_access: Whether fast access should be applied.

        :param check_uniqueness:

            Whether it should be checked if the name unambiguously yields
            a single result.

        :param search_strategy: The search strategy (default and recommended is BFS)

        :return:

            The found instance (result/parameter/group node) or if fast access is True and you
            found a parameter or result that supports fast access, the contained value is returned.

        :raises:

            AttributeError: If no node with the given name can be found

            NotUniqueNodeError

                If `check_uniqueness=True` and searching `name` yields more than
                one node




        """
        return self._nn_interface._get(self, name, fast_access=fast_access,
                                       check_uniqueness=check_uniqueness,
                                       search_strategy=search_strategy)

    def f_get_children(self, copy=True):
        """Returns a children dictionary.

        :param copy:

            Whether the group's original dictionary or a shallow copy is returned.
            If you want the real dictionary please do not modify it at all!

        :returns: Dictionary of nodes

        """
        if copy:
            return self._children.copy()
        else:
            return self._children

    def f_to_dict(self,fast_access = False, short_names=False):
        """Returns a dictionary with pairings of (full) names as keys and instances as values.

        :param fast_access:

            If True parameter or result values are returned instead of the instances.

        :param short_names:

            If true keys are not full names but only the names. Raises a ValueError
            if the names are not unique.

        :return: dictionary

        :raises: ValueError

        """
        return self._nn_interface._to_dict(self, fast_access=fast_access,short_names=short_names)


    def f_store_child(self,name,recursive=False):
        """Stores a child or recursively a subtree to disk.

        :param recursive:

            Whether recursively all children's children should be stored too.

        :raises: ValueError if the child does not exist.

        """
        if not name in self._children:
                raise ValueError('Your group `%s` does not contain the child `%s`.' %
                                (self.v_full_name,name))

        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.store(pypetconstants.TREE, self._children[name], trajectory_name=traj.v_name,
                              recursive=recursive)



    def f_load_child(self,name,recursive=False,load_data=pypetconstants.UPDATE_DATA):
        """Loads a child or recursively a subtree from disk.

        :param recursive:

            Whether recursively all children's children should be loaded too.

        :param load_data:

            Flag how to load the data.
            For how to choose 'load_data' see :ref:`more-on-loading`.

        """

        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.load(pypetconstants.TREE, self,child_name=name, trajectory_name=traj.v_name,
                             recursive=recursive, load_data=load_data, trajectory=traj)


class ParameterGroup(NNGroupNode):
    """ Group node in your trajectory, hanging below `traj.parameters`.

    You can add other groups or parameters to it.

    """
    def f_add_parameter_group(self,name):
        """Adds an empty parameter group under the current node.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is the trajectory (root), the prefix `'parameters'`
        is added to the full name.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        created.

        """
        return self._nn_interface._add_generic(self,type_name = PARAMETER_GROUP,
                                               group_type_name = PARAMETER_GROUP,
                                               args = (name,), kwargs={})

    def f_add_parameter(self,*args,**kwargs):
        """ Adds a parameter under the current node.

        There are two ways to add a new parameter either by adding a parameter instance:

        >>> new_parameter = Parameter('group1.group2.myparam', data=42, comment='Example!')
        >>> traj.f_add_parameter(new_parameter)

        Or by passing the values directly to the function, with the name being the first
        (non-keyword!) argument:

        >>> traj.f_add_parameter('group1.group2.myparam', data=42, comment='Example!')

        If you want to create a different parameter than the standard parameter, you can
        give the constructor as the first (non-keyword!) argument followed by the name
        (non-keyword!):

        >>> traj.f_add_parameter(PickleParameter,'group1.group2.myparam', data=42, comment='Example!')

        The full name of the current node is added as a prefix to the given parameter name.
        If the current node is the trajectory the prefix `'parameters'` is added to the name.

        """
        return self._nn_interface._add_generic(self,type_name = PARAMETER,
                                               group_type_name = PARAMETER_GROUP,
                                               args=args,kwargs=kwargs)

class ResultGroup(NNGroupNode):
    """Group node in your trajectory, hanging below `traj.results`.

    You can add other groups or results to it.

    """
    def f_add_result_group(self,name):
        """Adds an empty result group under the current node.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is the trajectory (root) adds the prefix `'results.trajectory'` to the
        full name.
        If current node is a single run (root) adds the prefix `'results.run_08%d%'` to the
        full name where `'08%d'` is replaced by the index of the current run.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        """


        return self._nn_interface._add_generic(self,type_name = RESULT_GROUP,
                                               group_type_name = RESULT_GROUP,
                                               args = (name,), kwargs={})

    def f_add_result(self,*args,**kwargs):
        """Adds a result under the current node.

        There are two ways to add a new result either by adding a result instance:

        >>> new_result = Result('group1.group2.myresult', 1666, x=3, y=4, comment='Example!')
        >>> traj.f_add_result(new_result)

        Or by passing the values directly to the function, with the name being the first
        (non-keyword!) argument:

        >>> traj.f_add_result('group1.group2.myresult', 1666, x=3, y=3,comment='Example!')


        If you want to create a different result than the standard result, you can
        give the constructor as the first (non-keyword!) argument followed by the name
        (non-keyword!):

        >>> traj.f_add_result(PickleResult,'group1.group2.myresult', 1666, x=3, y=3, comment='Example!')

        Additional arguments (here `1666`) or keyword arguments (here `x=3, y=3`) are passed
        onto the constructor of the result.


        Adds the full name of the current node as prefix to the name of the result.
        If current node is the trajectory (root) adds the prefix `'results.trajectory'` to the
        full name.
        If current node is a single run (root) adds the prefix `'results.run_08%d%'` to the
        full name where `'08%d'` is replaced by the index of the current run.

        """
        return self._nn_interface._add_generic(self,type_name = RESULT,
                                               group_type_name = RESULT_GROUP,
                                               args=args,kwargs=kwargs)


class DerivedParameterGroup(NNGroupNode):
    """Group node in your trajectory, hanging below `traj.derived_parameters`.

    You can add other groups or parameters to it.

    """
    def f_add_derived_parameter_group(self,name):
        """Adds an empty derived parameter group under the current node.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is the trajectory (root) adds the prefix `'derived_parameters.trajectory'`
        to the full name.
        If current node is a single run (root) adds the prefix `'derived_parameters.run_08%d%'`
        to the full name where `'08%d'` is replaced by the index of the current run.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        """

        return self._nn_interface._add_generic(self,type_name = DERIVED_PARAMETER_GROUP,
                                               group_type_name = DERIVED_PARAMETER_GROUP,
                                               args = (name,), kwargs={})

    def f_add_derived_parameter(self,*args,**kwargs):
        """Adds a derived parameter under the current group.

        Similar to
        :func:`~pypet.naturalnaming.ParameterGroup.f_add_parameter`

        Naming prefixes are added as in
        :func:`~pypet.naturalnaming.DerivedParameterGroup.f_add_derived_parameter_group`

        """
        return self._nn_interface._add_generic(self,type_name = DERIVED_PARAMETER,
                                               group_type_name = DERIVED_PARAMETER_GROUP,
                                               args=args,kwargs=kwargs)



class ConfigGroup(NNGroupNode):
    """Group node in your trajectory, hanging below `traj.config`.

    You can add other groups or parameters to it.

    """
    def f_add_config_group(self,name):
        """Adds an empty config group under the current node.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is the trajectory (root), the prefix `'config'` is added to the full name.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        """
        return self._nn_interface._add_generic(self,type_name = CONFIG_GROUP,
                                               group_type_name = CONFIG_GROUP,
                                               args = (name,), kwargs={})

    def f_add_config(self,*args,**kwargs):
        """Adds a config parameter under the current group.

        Similar to
        :func:`~pypet.naturalnaming.ParameterGroup.f_add_parameter`.

        If current group is the trajectory the prefix `'config'` is added to the name.

        """
        return self._nn_interface._add_generic(self,type_name = CONFIG,
                                               group_type_name = CONFIG_GROUP,
                                               args=args,kwargs=kwargs)




