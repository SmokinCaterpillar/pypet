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

    * :class:`~pypet.naturalnaming.KnowsTrajectory`

        A dummy class which adds the constant ``KNOWS_TRAJECTORY=True`` to a given class.
        This signals the trajectory to pass itself onto the class constructor.

"""

__author__ = 'Robert Meyer'

import inspect
import warnings
import keyword
import itertools as itools
import re
from collections import deque

from pypet.utils.decorators import deprecated, kwargs_api_change
import pypet.pypetexceptions as pex
import pypet.pypetconstants as pypetconstants
from pypet.annotations import WithAnnotations
from pypet.utils.helpful_classes import ChainMap, IteratorChain
from pypet.utils.helpful_functions import is_debug, nest_dictionary
from pypet.pypetlogging import HasLogger, DisableAllLogging
from pypet.slots import HasSlots


# For fetching:
STORE = 'STORE'  # We want to store stuff with the storage service
LOAD = 'LOAD'  # We want to load stuff with the storage service
REMOVE = 'REMOVE'  # We want to remove stuff, potentially from disk

# Group Constants
RESULT = 'RESULT'
RESULT_GROUP = 'RESULT_GROUP'
PARAMETER = 'PARAMETER'
PARAMETER_GROUP = 'PARAMETER_GROUP'
DERIVED_PARAMETER = 'DERIVED_PARAMETER'
DERIVED_PARAMETER_GROUP = 'DERIVED_PARAMETER_GROUP'
CONFIG = 'CONFIG'
CONFIG_GROUP = 'CONFIG_GROUP'
GROUP = 'GROUP'
LEAF = 'LEAF'
LINK = 'LINK'

# Types are not allowed to be added during single runs
SENSITIVE_TYPES = set([PARAMETER, PARAMETER_GROUP, CONFIG, CONFIG_GROUP])

# SUBTREE Mapping
SUBTREE_MAPPING = {'config': (CONFIG_GROUP, CONFIG),
                   'parameters': (PARAMETER_GROUP, PARAMETER),
                   'derived_parameters': (DERIVED_PARAMETER_GROUP, DERIVED_PARAMETER),
                   'results': (RESULT_GROUP, RESULT)}

# For fast searching of nodes in the tree:
# If there are more candidate solutions found by the fast search
# (that need to be checked sequentially) than this number
# a slow search with a full tree traversal is initiated.
FAST_UPPER_BOUND = 3

SHORTCUT_SET = set(['dpar', 'par', 'conf', 'res'])

CHECK_REGEXP = re.compile(r'^[A-Za-z0-9_-]+$')


class NNTreeNodeKids(HasSlots):

    __slots__ = ('_node',)

    def __init__(self, node):
        self._node = node

    def __getattr__(self, item):
        if item in self._node._children:
            return self._node._children[item]
        else:
            raise AttributeError('Group/Link/Leaf `%s` unknown for %s '
                                 '`%s`.' % (item, self._node.__class__.__name__,
                                            self._node.v_name))

    def __dir__(self):
        return self._node.f_dir_data()


class NNTreeNodeFunc(NNTreeNodeKids):

    __slots__ = ('_prefix',)

    def __init__(self, node):
        super(NNTreeNodeFunc, self).__init__(node)
        self._prefix = 'f_'

    def _is_part(self, name):
        return hasattr(self._node.__class__, name)

    def __getattr__(self, item):
        f_item = self._prefix + item
        if self._is_part(f_item):
            return getattr(self._node, f_item)
        else:
            raise AttributeError('Function/Property `%s` unknown for %s '
                                 '`%s`.' % (item, self._node.__class__.__name__,
                                            self._node.v_name))

    def __dir__(self):
        result = [x[2:] for x in dir(self._node) if x.startswith(self._prefix) and
                                                self._is_part(x)]
        return result


class NNTreeNodeVars(NNTreeNodeFunc):

    __slots__ = ()

    def __init__(self, node):
        super(NNTreeNodeVars, self).__init__(node)
        self._prefix = 'v_'

    def _is_part(self, name):
        if super(NNTreeNodeVars, self)._is_part(name):
            return True
        if name in self._node.__all_slots__:
            return True
        try:
            return name in self._node.__dict__
        except AttributeError:
            return False

    def __setattr__(self, key, value):
        if key.startswith('_'):
            return super(NNTreeNodeFunc, self).__setattr__(key, value)
        v_key = 'v_' + key
        if self._is_part(v_key):
            setattr(self._node, v_key, value)
        else:
            raise AttributeError('Property `%s` unknown for %s '
                                 '`%s`.' % (key, self._node.__class__.__name__,
                                            self._node.v_name))


class NNTreeNode(WithAnnotations):
    """ Abstract class to define the general node in the trajectory tree."""

    __slots__ = ('_is_leaf', '_stored', '_comment', '_depth', '_full_name', '_name',
                 '_run_branch', '_branch', '_vars', '_func')

    def __init__(self, full_name, comment, is_leaf):
        super(NNTreeNode, self).__init__()
        self._is_leaf = is_leaf  # Whether or not a node is a leaf, aka terminal node.
        self._stored = False
        self._comment = ''
        self._depth = 0
        self._full_name = None
        self._name = None
        self._run_branch = 'trajectory'
        self._branch = None
        self._vars = None
        self._func = None
        self.v_comment = comment

        self._rename(full_name)

    @property
    def vars(self):
        """Alternative naming, you can use `node.vars.name` instead of `node.v_name`"""
        if self._vars is None:
            self._vars = NNTreeNodeVars(self)
        return self._vars

    @property
    def func(self):
        """Alternative naming, you can use `node.func.name` instead of `node.f_func`"""
        if self._func is None:
            self._func = NNTreeNodeFunc(self)
        return self._func

    @property
    def v_stored(self):
        """Whether or not this tree node has been stored to disk before."""
        return self._stored

    @property
    def v_comment(self):
        """Should be a nice descriptive comment"""
        return self._comment

    @v_comment.setter
    def v_comment(self, comment):
        """Changes the comment"""
        comment = str(comment)
        self._comment = comment

    @property
    def v_depth(self):
        """ Depth of the node in the trajectory tree."""
        return self._depth

    @property
    def v_is_leaf(self):
        """Whether node is a leaf or not (i.e. it is a group node)"""
        return self._is_leaf

    @property
    def v_is_group(self):
        """Whether node is a group or not (i.e. it is a leaf node)"""
        return not self._is_leaf

    @property
    def v_is_root(self):
        """Whether the group is root (True for the trajectory and a single run object)"""
        return self._depth == 0

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
        return self._full_name[:-len(self._name) - 1]

    @property
    def v_run_branch(self):
        """ If this node is hanging below a branch named `run_XXXXXXXXX`.

        The branch name is either the name of a single run
        (e.g. 'run_00000009') or 'trajectory'.

        """
        return self._run_branch

    @property
    def v_branch(self):
        """The name of the branch/subtree, i.e. the first node below the root.

        The empty string in case of root itself.

        """
        return self._branch

    def _rename(self, full_name):
        """Renames the tree node"""
        self._full_name = full_name
        if full_name:
            self._name = full_name.rsplit('.', 1)[-1]

    def _set_details(self, depth, branch, run_branch):
        """Sets some details for internal handling."""
        self._depth = depth
        self._branch = branch
        self._run_branch = run_branch

    def f_get_class_name(self):
        """ Returns the class name of the parameter or result or group.

        Equivalent to `obj.__class__.__name__`

        """
        return self.__class__.__name__


class KnowsTrajectory(object):
    """ A dummy class which adds the constant ``KNOWS_TRAJECTORY=True`` to a given class.

    This signals the trajectory to pass itself onto the class constructor.

    Group nodes *know* the trajectory whereas leaf nodes don't.
    This has the advantage in case leaf nodes are pickled (because they are sent over a
    queue, for instance) only the item itself serialized and not the full tree.

    """
    __slots__ = ()
    KNOWS_TRAJECTORY = True


class NNLeafNode(NNTreeNode):
    """ Abstract class interface of result or parameter (see :mod:`pypet.parameter`)"""

    __slots__ = ('_is_parameter',)

    def __init__(self, full_name, comment, is_parameter):
        super(NNLeafNode, self).__init__(full_name=full_name, comment=comment, is_leaf=True)
        self._is_parameter = is_parameter

    def f_supports_fast_access(self):
        """Whether or not fast access can be supported by the parameter or result.

        ABSTRACT: Needs to be implemented by subclass.

        """
        return False

    @property
    def v_is_parameter(self):
        """Whether the node is a parameter or not (i.e. a result)"""
        return self._is_parameter

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

    def _load_flags(self):
        """ Currently not used because I let the storage service infer how to load
        stuff from the data itself.

        If you write your own parameter or result you can implement this function
        to make specifications on how to load data,
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
        raise NotImplementedError('Implement this!')

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


class NaturalNamingInterface(HasLogger):
    """Class to manage the tree structure of a trajectory.

    Handles search, insertion, etc.

    """

    def __init__(self, root_instance):

        # The root instance is a reference to the top node of the tree. This is either
        # a single run or the parent trajectory. This can change during runtime!
        self._root_instance = root_instance

        self._set_logger()

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
        # a particular run (by setting the v_crun property).
        self._nodes_and_leaves_runs_sorted = {}
        self._links_count =  {} # Dictionary of how often a link exists

        # Context Manager to disable logging for auto-loading
        self._disable_logging = DisableAllLogging()

        # List of names that are taboo. The user cannot create parameters or results that
        # contain these names.
        self._not_admissible_names = set(dir(self)) | set(dir(self._root_instance))
        self._python_keywords = set(keyword.kwlist)


    def _map_type_to_dict(self, type_name):
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
        elif type_name == LEAF:
            return root._other_leaves
        else:
            raise RuntimeError('You shall not pass!')

    def _fetch_from_string(self, store_load, name, args, kwargs):
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
        if not isinstance(name, str):
            raise TypeError('No string!')

        node = self._root_instance.f_get(name)

        return self._fetch_from_node(store_load, node, args, kwargs)

    def _fetch_from_node(self, store_load, node, args, kwargs):
        """Method used by f_store/load/remove_items to find a corresponding item in the tree.

        :param store_load: String constant specifying if we want to store, load or remove
        :param node: A group, parameter or result instance.
        :param args: Additional arguments passed to the storage service
        :param kwargs: Additional keyword arguments passed to the storage service

        :return:

            A formatted request that can be handled by the storage service, aka
            a tuple: (msg, item_to_store_load_or_remove, args, kwargs)

        """
        msg = self._node_to_msg(store_load, node)

        return msg, node, args, kwargs

    def _fetch_from_tuple(self, store_load, store_tuple, args, kwargs):
        """ Method used by f_store/load/remove_items to find a corresponding item in the tree.

        The input to the method should already be in the correct format, this method only
        checks for sanity.

        :param store_load: String constant specifying if we want to store, load or remove

        :param store_tuple:

            Tuple already in correct format (msg, item, args, kwargs). If args and kwargs
            are not given, they are taken from the supplied parameters

        :param args: Additional arguments passed to the storage service if len(store_tuple)<3

        :param kwargs:

            Additional keyword arguments passed to the storage service if
            ``len(store_tuple)<4``


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
            raise ValueError('Your argument tuple %s has to many entries, please call '
                             'store with [(msg,item,args,kwargs),...]' % str(store_tuple))

        # #dummy test
        _ = self._fetch_from_node(store_load, node, args, kwargs)

        return msg, node, args, kwargs

    @staticmethod
    def _node_to_msg(store_load, node):
        """Maps a given node and a store_load constant to the message that is understood by
        the storage service.

        """
        if node.v_is_leaf:
            if store_load == STORE:
                return pypetconstants.LEAF
            elif store_load == LOAD:
                return pypetconstants.LEAF
            elif store_load == REMOVE:
                return pypetconstants.DELETE
        else:
            if store_load == STORE:
                return pypetconstants.GROUP
            elif store_load == LOAD:
                return pypetconstants.GROUP
            elif store_load == REMOVE:
                return pypetconstants.DELETE

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
                item_tuple = self._fetch_from_string(store_load, iter_item, args, kwargs)
            except TypeError:
                try:
                    item_tuple = self._fetch_from_node(store_load, iter_item, args, kwargs)
                except AttributeError:
                    item_tuple = self._fetch_from_tuple(store_load, iter_item, args, kwargs)

            item = item_tuple[1]
            msg = item_tuple[0]

            if item.v_is_leaf:
                if only_empties and not item.f_is_empty():
                    continue
                if non_empties and item.f_is_empty():
                    continue

            # # Explored Parameters cannot be deleted, this would break the underlying hdf5 file
            # # structure
            # if (msg == pypetconstants.DELETE and
            #             item.v_full_name in self._root_instance._explored_parameters and
            #             len(self._root_instance._explored_parameters) == 1):
            #     raise TypeError('You cannot the last explored parameter of a trajectory stored '
            #                     'into an hdf5 file.')

            item_list.append(item_tuple)

        return item_list

    def _remove_subtree(self, start_node, name, predicate=None):
        """Removes a subtree from the trajectory tree.

        Does not delete stuff from disk only from RAM.

        :param start_node: The parent node from where to start
        :param name: Name of child which will be deleted and recursively all nodes below the child
        :param predicate:

            Predicate that can be used to compute for individual nodes if they should be removed
            ``True`` or kept ``False``.

        """
        def _delete_from_children(node, child_name):
            del node._children[child_name]
            if child_name in node._groups:
                del node._groups[child_name]
            elif child_name in node._leaves:
                del node._leaves[child_name]
            else:
                raise RuntimeError('You shall not pass!')

        def _remove_subtree_inner(node, predicate):

            if not predicate(node):
                return False
            elif node.v_is_group:
                for name_ in itools.chain(list(node._leaves.keys()),
                                          list(node._groups.keys())):
                    child_ = node._children[name_]
                    child_deleted = _remove_subtree_inner(child_, predicate)
                    if child_deleted:
                        _delete_from_children(node, name_)
                        del child_

                for link_ in list(node._links.keys()):
                    node.f_remove_link(link_)

                if len(node._children) == 0:
                    self._delete_node(node)
                    return True
                else:
                    return False
            else:
                self._delete_node(node)
                return True

        if name in start_node._links:
            start_node.f_remove_link(name)
        else:
            child = start_node._children[name]
            if predicate is None:
                predicate = lambda x: True

            if _remove_subtree_inner(child, predicate):
                _delete_from_children(start_node, name)
                del child
                return True
            else:
                return False

    def _delete_node(self, node):
        """Deletes a single node from the tree.

        Removes all references to the node.

        Note that the 'parameters', 'results', 'derived_parameters', and 'config' groups
        hanging directly below root cannot be deleted. Also the root node itself cannot be
        deleted. (This would cause a tremendous wave of uncontrollable self destruction, which
        would finally lead to the Apocalypse!)

        """
        full_name = node.v_full_name
        root = self._root_instance

        if full_name == '':
            # You cannot delete root
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

            elif full_name in root._other_leaves:
                del root._other_leaves[full_name]

            if full_name in root._explored_parameters:

                if root._stored:
                    # We always keep the explored parameters in case the trajectory was stored
                    root._explored_parameters[full_name] = None
                else:
                    del root._explored_parameters[full_name]
                if len(root._explored_parameters) == 0:
                    root.f_shrink()

            del self._flat_leaf_storage_dict[full_name]
        else:
            del root._all_groups[full_name]

            if full_name in root._run_parent_groups:
                del root._run_parent_groups[full_name]

        # Delete all links to the node
        if full_name in root._linked_by:
            linking = root._linked_by[full_name]
            for linking_name in list(linking.keys()):
                linking_group, link_set = linking[linking_name]
                for link in list(link_set):
                    linking_group.f_remove_link(link)
        
        if (node.v_location, node.v_name) in self._root_instance._new_nodes:
            del self._root_instance._new_nodes[(node.v_location, node.v_name)]

        # Finally remove all references in the dictionaries for fast search
        self._remove_from_nodes_and_leaves(node)

        # Remove circular references
        node._vars = None
        node._func = None

    def _remove_from_nodes_and_leaves(self, node):

        run_name = node.v_run_branch
        full_name = node.v_full_name
        name = node.v_name

        del self._nodes_and_leaves[name][full_name]
        if len(self._nodes_and_leaves[name]) == 0:
            del self._nodes_and_leaves[name]

        del self._nodes_and_leaves_runs_sorted[name][run_name][full_name]
        if len(self._nodes_and_leaves_runs_sorted[name][run_name]) == 0:
            del self._nodes_and_leaves_runs_sorted[name][run_name]
            if len(self._nodes_and_leaves_runs_sorted[name]) == 0:
                del self._nodes_and_leaves_runs_sorted[name]

    def _remove_node_or_leaf(self, instance, recursive=False):
        """Removes a single node from the tree.

        Only from RAM not from hdf5 file!

        :param instance: The node to be deleted

        :param recursive: If group nodes with children should be deleted

        """
        full_name = instance.v_full_name
        split_name = deque(full_name.split('.'))
        self._remove_along_branch(self._root_instance, split_name, recursive)

    def _remove_along_branch(self, actual_node, split_name, recursive=False):
        """Removes a given node from the tree.

        Starts from a given node and walks recursively down the tree to the location of the node
        we want to remove.

        We need to walk from a start node in case we want to check on the way back whether we got
        empty group nodes due to deletion.

        :param actual_node: Current node

        :param split_name: DEQUE of names to get the next nodes.

        :param recursive:

            To also delete all children of a group node

        :return: True if node was deleted, otherwise False

        """

        # If the names list is empty, we have reached the node we want to delete.

        if len(split_name) == 0:
            if actual_node.v_is_group and actual_node.f_has_children():
                if recursive:
                    for child in list(actual_node._children.keys()):
                        actual_node.f_remove_child(child, recursive=True)
                else:
                    raise TypeError('Cannot remove group `%s` it contains children. Please '
                                    'remove with `recursive=True`.' % actual_node.v_full_name)
            self._delete_node(actual_node)
            return True

        # Otherwise get the next node by using the first name in the list
        name = split_name.popleft()

        if name in actual_node._links:
            if len(split_name)>0:
                raise RuntimeError('You cannot remove nodes while hopping over links!')
            actual_node.f_remove_link(name)
        else:
            child = actual_node._children[name]

            if self._remove_along_branch(child, split_name, recursive=recursive):

                del actual_node._children[name]
                if name in actual_node._groups:
                    del actual_node._groups[name]
                elif name in actual_node._leaves:
                    del actual_node._leaves[name]
                else:
                    raise RuntimeError('You shall not pass!')
                del child
                return False

    def _translate_shortcut(self, name):
        """Maps a given shortcut to corresponding name

        * 'run_X' or 'r_X' to 'run_XXXXXXXXX'

        * 'crun' to the current run name in case of a
          single run instance if trajectory is used via `v_crun`

        * 'par' 'parameters'

        * 'dpar' to 'derived_parameters'

        * 'res' to 'results'

        * 'conf' to 'config'

        :return: True or False and the mapped name.

        """

        if isinstance(name, int):
            return True, self._root_instance.f_wildcard('$', name)

        if name.startswith('run_') or name.startswith('r_'):
            split_name = name.split('_')
            if len(split_name) == 2:
                index = split_name[1]
                if index.isdigit():
                    return True, self._root_instance.f_wildcard('$', int(index))
                elif index == 'A':
                    return True, self._root_instance.f_wildcard('$', -1)

        if name.startswith('runtoset_') or name.startswith('rts_'):
            split_name = name.split('_')
            if len(split_name) == 2:
                index = split_name[1]
                if index.isdigit():
                    return True, self._root_instance.f_wildcard('$set', int(index))
                elif index == 'A':
                    return True, self._root_instance.f_wildcard('$set', -1)

        if name in SHORTCUT_SET:
            if name == 'par':
                return True, 'parameters'
            elif name == 'dpar':
                return True, 'derived_parameters'
            elif name == 'res':
                return True, 'results'
            elif name == 'conf':
                return True, 'config'
            else:
                raise RuntimeError('You shall not pass!')

        return False, name

    def _add_prefix(self, split_names, start_node, group_type_name):
        """Adds the correct sub branch prefix to a given name.

        Usually the prefix is the full name of the parent node. In case items are added
        directly to the trajectory the prefixes are chosen according to the matching subbranch.

        For example, this could be 'parameters' for parameters or 'results.run_00000004' for
        results added to the fifth single run.

        :param split_names:

            List of names of the new node (e.g. ``['mynewgroupA', 'mynewgroupB', 'myresult']``).

        :param start_node:

            Parent node under which the new node should be added.

        :param group_type_name:

            Type name of subbranch the item belongs to
            (e.g. 'PARAMETER_GROUP', 'RESULT_GROUP' etc).


        :return: The name with the added prefix.

        """
        root = self._root_instance

        # If the start node of our insertion is root or one below root
        # we might need to add prefixes.
        # In case of derived parameters and results we also need to add prefixes containing the
        # subbranch and the current run in case of a single run.
        # For instance, a prefix could be 'results.runs.run_00000007'.
        prepend = []
        if start_node.v_depth < 3 and not group_type_name == GROUP:
            if start_node.v_depth == 0:

                if group_type_name == DERIVED_PARAMETER_GROUP:
                    if split_names[0] == 'derived_parameters':
                        return split_names
                    else:
                        prepend += ['derived_parameters']

                elif group_type_name == RESULT_GROUP:
                    if split_names[0] == 'results':
                        return split_names
                    else:
                        prepend += ['results']

                elif group_type_name == CONFIG_GROUP:
                    if split_names[0] == 'config':
                        return split_names
                    else:
                        prepend += ['config']

                elif group_type_name == PARAMETER_GROUP:
                    if split_names[0] == 'parameters':
                        return split_names[0]
                    else:
                        prepend += ['parameters']
                else:
                    raise RuntimeError('Why are you here?')

            # Check if we have to add a prefix containing the current run
            if root._is_run and root._auto_run_prepend:
                dummy = root.f_wildcard('$', -1)
                crun = root.f_wildcard('$')
                if any(name in root._run_information for name in split_names):
                    pass
                elif any(name == dummy for name in split_names):
                    pass
                elif (group_type_name == RESULT_GROUP or
                        group_type_name == DERIVED_PARAMETER_GROUP):

                    if start_node.v_depth == 0:
                        prepend += ['runs', crun]

                    elif start_node.v_depth == 1:

                        if len(split_names) == 1 and split_names[0] == 'runs':
                            return split_names
                        else:
                            prepend += ['runs', crun]

                    elif start_node.v_depth == 2 and start_node.v_name == 'runs':
                        prepend += [crun]

        if prepend:
            split_names = prepend + split_names

        return split_names

    @staticmethod
    def _determine_types(start_node, first_name, add_leaf, add_link):
        """Determines types for generic additions"""
        if start_node.v_is_root:
            where = first_name
        else:
            where = start_node._branch

        if where in SUBTREE_MAPPING:
            type_tuple = SUBTREE_MAPPING[where]
        else:
            type_tuple = (GROUP, LEAF)

        if add_link:
            return type_tuple[0], LINK
        if add_leaf:
            return type_tuple
        else:
            return type_tuple[0], type_tuple[0]

    def _add_generic(self, start_node, type_name, group_type_name, args, kwargs,
                     add_prefix=True, check_naming=True):
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

        :param add_prefix:

            If a prefix group, i.e. `results`, `config`, etc. should be added

        :param check_naming:

            If it should be checked for correct namings, can be set to ``False`` if data is loaded
            and we know that all names are correct.

        :return: The new added instance

        """
        args = list(args)
        create_new = True
        name = ''
        instance = None
        constructor = None

        add_link = type_name == LINK

        # First check if the item is already a given instance or we want to add a link
        if add_link:
            name = args[0]
            instance = args[1]
            create_new = False
        elif len(args) == 1 and len(kwargs) == 0:
            item = args[0]
            try:
                name = item.v_full_name
                instance = item

                create_new = False
            except AttributeError:
                pass

        # If the item is not an instance yet, check if args[0] is a class and args[1] is
        # a string describing the new name of the instance.
        # If args[0] is not a class it is assumed to be the name of the new instance.
        if create_new:
            if len(args) > 0 and inspect.isclass(args[0]):
                constructor = args.pop(0)
            if len(args) > 0 and isinstance(args[0], str):
                name = args.pop(0)
            elif 'name' in kwargs:
                name = kwargs.pop('name')
            elif 'full_name' in kwargs:
                name = kwargs.pop('full_name')
            else:
                raise ValueError('Could not determine a name of the new item you want to add. '
                                 'Either pass the name as positional argument or as a keyword '
                                 'argument `name`.')

        split_names = name.split('.')
        if check_naming:

            for idx, name in enumerate(split_names):
                translated_shortcut, name = self._translate_shortcut(name)
                replaced, name = self._replace_wildcards(name)
                if translated_shortcut or replaced:
                    split_names[idx] = name

            # First check if the naming of the new item is appropriate
            faulty_names = self._check_names(split_names, start_node)

            if faulty_names:
                full_name = '.'.join(split_names)
                raise ValueError(
                    'Your Parameter/Result/Node `%s` contains the following not admissible names: '
                    '%s please choose other names.' % (full_name, faulty_names))

            if add_link:
                if instance is None:
                    raise ValueError('You must provide an instance to link to!')
                if instance.v_is_root:
                    raise ValueError('You cannot create a link to the root node')
                if start_node.v_is_root and name in SUBTREE_MAPPING:
                    raise ValueError('`%s` is a reserved name for a group under root.' % name)
                if not self._root_instance.f_contains(instance, with_links=False, shortcuts=False):
                    raise ValueError('You can only link to items within the trajectory tree!')

        # Check if the name fulfils the prefix conditions, if not change the name accordingly.
        if add_prefix:
            split_names = self._add_prefix(split_names, start_node, group_type_name)

        if group_type_name == GROUP:
            add_leaf = type_name != group_type_name and not add_link
            # If this is equal we add a group node
            group_type_name, type_name = self._determine_types(start_node, split_names[0],
                                                               add_leaf, add_link)

        # Check if we are allowed to add the data
        if self._root_instance._is_run and type_name in SENSITIVE_TYPES:
            raise TypeError('You are not allowed to add config or parameter data or groups '
                            'during a single run.')

        return self._add_to_tree(start_node, split_names, type_name, group_type_name, instance,
                                 constructor, args, kwargs)

    def _replace_wildcards(self, name, run_idx=None):
        """Replaces the $ wildcards and returns True/False in case it was replaced"""
        if self._root_instance.f_is_wildcard(name):
            return True, self._root_instance.f_wildcard(name, run_idx)
        else:
            return False, name

    def _add_to_nodes_and_leaves(self, new_node):

        full_name = new_node.v_full_name
        name = new_node.v_name
        run_name = new_node._run_branch
        if not name in self._nodes_and_leaves:
            self._nodes_and_leaves[name] = {full_name: new_node}
        else:
            self._nodes_and_leaves[name][full_name] = new_node

        if not name in self._nodes_and_leaves_runs_sorted:
            self._nodes_and_leaves_runs_sorted[name] = {run_name:
                                                            {full_name:
                                                                 new_node}}
        else:
            if not run_name in self._nodes_and_leaves_runs_sorted[name]:
                self._nodes_and_leaves_runs_sorted[name][run_name] = \
                    {full_name: new_node}
            else:
                self._nodes_and_leaves_runs_sorted[name][run_name]\
                    [full_name] = new_node

    def _add_to_tree(self, start_node, split_names, type_name, group_type_name,
                     instance, constructor, args, kwargs):
        """Adds a new item to the tree.

        The item can be an already given instance or it is created new.

        :param start_node:

            Parental node the adding of the item was initiated from.

        :param split_names:

            List of names of the new item

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

        # Then walk iteratively from the start node as specified by the new name and create
        # new empty groups on the fly
        try:
            act_node = start_node
            last_idx = len(split_names) - 1
            add_link = type_name == LINK
            link_added = False
            # last_name = start_node.v_crun
            for idx, name in enumerate(split_names):
                if name not in act_node._children:
                    if idx == last_idx:
                        if add_link:
                            new_node = self._create_link(act_node, name, instance)
                            link_added = True
                        elif group_type_name != type_name:
                            # We are at the end of the chain and we add a leaf node

                            new_node = self._create_any_param_or_result(act_node,
                                                                        name,
                                                                        type_name,
                                                                        instance,
                                                                        constructor,
                                                                        args, kwargs)

                            self._flat_leaf_storage_dict[new_node.v_full_name] = new_node
                        else:
                            # We add a group as desired
                            new_node = self._create_any_group(act_node, name,
                                                              group_type_name,
                                                              instance,
                                                              constructor,
                                                              args, kwargs)
                    else:
                        # We add a group on the fly
                        new_node = self._create_any_group(act_node, name,
                                                          group_type_name)


                    if name in self._root_instance._run_information:
                        self._root_instance._run_parent_groups[act_node.v_full_name] = act_node
                    if self._root_instance._is_run:
                        if link_added:
                            self._root_instance._new_links[(act_node.v_full_name, name)] = \
                                (act_node, new_node)
                        else:
                            self._root_instance._new_nodes[(act_node.v_full_name, name)] = \
                                (act_node, new_node)
                else:
                    if name in act_node._links:
                        raise AttributeError('You cannot hop over links when adding '
                                             'data to the tree. '
                                             'There is a link called `%s` under `%s`.' %
                                             (name, act_node.v_full_name))
                    if idx == last_idx:
                        if self._root_instance._no_clobber:
                            self._logger.warning('You already have a group/instance/link `%s` '
                                                 'under `%s`. '
                                                 'However, you set `v_no_clobber=True`, '
                                                 'so I will ignore your addition of '
                                                 'data.' % (name, act_node.v_full_name))
                        else:
                            raise AttributeError('You already have a group/instance/link `%s` '
                                                 'under `%s`' % (name, act_node.v_full_name))
                act_node = act_node._children[name]
            return act_node
        except:
            self._logger.error('Failed adding `%s` under `%s`.' %
                               (name, start_node.v_full_name))
            raise

    def _remove_link(self, act_node, name):
        linked_node = act_node._links[name]
        full_name = linked_node.v_full_name
        linking = self._root_instance._linked_by[full_name]
        link_set = linking[act_node.v_full_name][1]
        link_set.remove(name)
        if len(link_set) == 0:
            del linking[act_node.v_full_name]
        if len(linking) == 0:
            del self._root_instance._linked_by[full_name]
            del linking
        del act_node._links[name]
        del act_node._children[name]
        self._links_count[name] = self._links_count[name] - 1
        if self._links_count[name] < 1:
            del self._links_count[name]
        if (act_node.v_full_name, name) in self._root_instance._new_links:
            del self._root_instance._new_links[(act_node.v_full_name, name)]

    def _create_link(self, act_node, name, instance):
        """Creates a link and checks if names are appropriate
        """

        act_node._links[name] = instance
        act_node._children[name] = instance

        full_name = instance.v_full_name
        if full_name not in self._root_instance._linked_by:
            self._root_instance._linked_by[full_name] = {}
        linking = self._root_instance._linked_by[full_name]
        if act_node.v_full_name not in linking:
            linking[act_node.v_full_name] = (act_node, set())
        linking[act_node.v_full_name][1].add(name)

        if name not in self._links_count:
            self._links_count[name] = 0
        self._links_count[name] = self._links_count[name] + 1

        self._logger.debug('Added link `%s` under `%s` pointing '
                           'to `%s`.' % (name, act_node.v_full_name,
                                         instance.v_full_name))
        return instance

    def _check_names(self, split_names, parent_node=None):
        """Checks if a list contains strings with invalid names.

        Returns a description of the name violations. If names are correct the empty
        string is returned.

        :param split_names: List of strings

        :param parent_node:

            The parental node from where to start (only applicable for node names)

        """

        faulty_names = ''

        if parent_node is not None and parent_node.v_is_root and split_names[0] == 'overview':
            faulty_names = '%s `overview` cannot be added directly under the root node ' \
                           'this is a reserved keyword,' % (faulty_names)

        for split_name in split_names:

            if len(split_name) == 0:
                faulty_names = '%s `%s` contains no characters, please use at least 1,' % (
                    faulty_names, split_name)

            elif split_name.startswith('_'):
                faulty_names = '%s `%s` starts with a leading underscore,' % (
                    faulty_names, split_name)

            elif re.match(CHECK_REGEXP, split_name) is None:
                faulty_names = '%s `%s` contains non-admissible characters ' \
                               '(use only [A-Za-z0-9_-]),' % \
                               (faulty_names, split_name)

            elif '$' in split_name:
                if split_name not in self._root_instance._wildcard_keys:
                    faulty_names = '%s `%s` contains `$` but has no associated ' \
                                   'wildcard function,' % (faulty_names, split_name)

            elif split_name in self._not_admissible_names:
                warnings.warn('`%s` is a method/attribute of the '
                              'trajectory/treenode/naminginterface, you may not be '
                              'able to access it via natural naming but only by using '
                              '`[]` square bracket notation. ' % split_name,
                              category=SyntaxWarning)

            elif split_name in self._python_keywords:
                warnings.warn('`%s` is a python keyword, you may not be '
                              'able to access it via natural naming but only by using '
                              '`[]` square bracket notation. ' % split_name,
                              category=SyntaxWarning)

        name = split_names[-1]
        if len(name) >= pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH:
            faulty_names = '%s `%s` is too long the name can only have %d characters but it has ' \
                           '%d,' % \
                           (faulty_names, name, len(name),
                            pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH)

        return faulty_names

    def _create_any_group(self, parent_node, name, type_name, instance=None, constructor=None,
                          args=None, kwargs=None):
        """Generically creates a new group inferring from the `type_name`."""

        if args is None:
            args = []

        if kwargs is None:
            kwargs = {}

        full_name = self._make_full_name(parent_node.v_full_name, name)

        if instance is None:
            if constructor is None:
                if type_name == RESULT_GROUP:
                    constructor = ResultGroup
                elif type_name == PARAMETER_GROUP:
                    constructor = ParameterGroup
                elif type_name == CONFIG_GROUP:
                    constructor = ConfigGroup
                elif type_name == DERIVED_PARAMETER_GROUP:
                    constructor = DerivedParameterGroup
                elif type_name == GROUP:
                    constructor = NNGroupNode
                else:
                    raise RuntimeError('You shall not pass!')
            instance = self._root_instance._construct_instance(constructor, full_name,
                                                               *args, **kwargs)
        else:
            instance._rename(full_name)
            # Check if someone tries to add a particular standard group to a branch where
            # it does not belong:
            if type_name == RESULT_GROUP:
                if type(instance) in (NNGroupNode,
                                   ParameterGroup,
                                   ConfigGroup,
                                   DerivedParameterGroup):
                    raise TypeError('You cannot add a `%s` type of group under results' %
                                    str(type(instance)))
            elif type_name == PARAMETER_GROUP:
                if type(instance) in (NNGroupNode,
                                   ResultGroup,
                                   ConfigGroup,
                                   DerivedParameterGroup):
                    raise TypeError('You cannot add a `%s` type of group under parameters' %
                                    str(type(instance)))
            elif type_name == CONFIG_GROUP:
                if type(instance) in (NNGroupNode,
                                   ParameterGroup,
                                   ResultGroup,
                                   DerivedParameterGroup):
                    raise TypeError('You cannot add a `%s` type of group under config' %
                                    str(type(instance)))
            elif type_name == DERIVED_PARAMETER_GROUP:
                if type(instance) in (NNGroupNode,
                                   ParameterGroup,
                                   ConfigGroup,
                                   ResultGroup):
                    raise TypeError('You cannot add a `%s` type of group under derived '
                                    'parameters' % str(type(instance)))
            elif type_name == GROUP:
                if type(instance) in (ResultGroup,
                                   ParameterGroup,
                                   ConfigGroup,
                                   DerivedParameterGroup):
                    raise TypeError('You cannot add a `%s` type of group under other data' %
                                    str(type(instance)))
            else:
                raise RuntimeError('You shall not pass!')

        self._set_details_tree_node(parent_node, name, instance)
        instance._nn_interface = self
        self._root_instance._all_groups[instance.v_full_name] = instance
        self._add_to_nodes_and_leaves(instance)
        parent_node._children[name] = instance
        parent_node._groups[name] = instance

        return instance

    def _create_any_param_or_result(self, parent_node, name, type_name, instance, constructor,
                                    args, kwargs):
        """Generically creates a novel parameter or result instance inferring from the `type_name`.

        If the instance is already supplied it is NOT constructed new.

        :param parent_node:

            Parent trajectory node

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
        full_name = self._make_full_name(parent_node.v_full_name, name)
        if instance is None:
            if constructor is None:
                if type_name == RESULT:
                    constructor = root._standard_result
                elif type_name in [PARAMETER, CONFIG, DERIVED_PARAMETER]:
                    constructor = root._standard_parameter
                else:
                    constructor = root._standard_leaf
            instance = root._construct_instance(constructor, full_name, *args, **kwargs)
        else:
            instance._rename(full_name)

        self._set_details_tree_node(parent_node, name, instance)

        where_dict = self._map_type_to_dict(type_name)
        full_name = instance._full_name

        if full_name in where_dict:
            raise AttributeError(full_name + ' is already part of trajectory,')

        if type_name != RESULT and full_name in root._changed_default_parameters:
            self._logger.info(
                'You have marked parameter %s for change before, so here you go!' %
                full_name)

            change_args, change_kwargs = root._changed_default_parameters.pop(full_name)
            instance.f_set(*change_args, **change_kwargs)

        where_dict[full_name] = instance
        self._add_to_nodes_and_leaves(instance)
        parent_node._children[name] = instance
        parent_node._leaves[name] = instance

        if full_name in self._root_instance._explored_parameters:
            instance._explored = True  # Mark this parameter as explored.
            self._root_instance._explored_parameters[full_name] = instance

        self._logger.debug('Added `%s` to trajectory.' % full_name)

        return instance

    @staticmethod
    def _make_full_name(location, name):
        if location:
            return '%s.%s' % (location, name)
        else:
            return name

    def _set_details_tree_node(self, parent_node, name, instance):
        """Renames a given `instance` based on `parent_node` and `name`.

        Adds meta information like depth as well.

        """
        depth = parent_node._depth + 1
        if parent_node.v_is_root:
            branch = name  # We add below root
        else:
            branch = parent_node._branch
        if name in self._root_instance._run_information:
            run_branch = name
        else:
            run_branch = parent_node._run_branch

        instance._set_details(depth, branch, run_branch)

    @staticmethod
    def _apply_fast_access(data, fast_access):
        """Method that checks if fast access is possible and applies it if desired"""
        if fast_access and data.f_supports_fast_access():
            return data.f_get()
        else:
            return data

    def _iter_nodes(self, node, recursive=False, max_depth=float('inf'),
                    with_links=True, in_search=False, predicate=None):
        """Returns an iterator over nodes hanging below a given start node.

        :param node:

            Start node

        :param recursive:

            Whether recursively also iterate over the children of the start node's children

        :param max_depth:

            Maximum depth to search for

        :param in_search:

            if it is used during get search and if detailed info should be returned

        :param with_links:

            If links should be considered

        :param predicate:

            A predicate to filter nodes

        :return: Iterator

        """
        def _run_predicate(x, run_name_set):
            branch = x.v_run_branch
            return branch == 'trajectory' or branch in run_name_set

        if max_depth is None:
            max_depth = float('inf')

        if predicate is None:
            predicate = lambda x: True
        elif isinstance(predicate, (tuple, list)):
            # Create a predicate from a list of run names or run indices
            run_list = predicate
            run_name_set = set()
            for item in run_list:
                if item == -1:
                    run_name_set.add(self._root_instance.f_wildcard('$', -1))
                elif isinstance(item, int):
                    run_name_set.add(self._root_instance.f_idx_to_run(item))
                else:
                    run_name_set.add(item)
            predicate = lambda x: _run_predicate(x, run_name_set)

        if recursive:
            return NaturalNamingInterface._recursive_traversal_bfs(node,
                                            self._root_instance._linked_by,
                                            max_depth, with_links,
                                            in_search, predicate)
        else:
            iterator = (x for x in self._make_child_iterator(node, with_links) if
                        predicate(x[2]))
            if in_search:
                return iterator # Here we return tuples: (depth, name, object)
            else:
                return (x[2] for x in iterator) # Here we only want the objects themselves

    def _to_dict(self, node, fast_access=True, short_names=False, nested=False,
                 copy=True, with_links=True):
        """ Returns a dictionary with pairings of (full) names as keys and instances as values.

        :param fast_access:

            If true parameter or result values are returned instead of the
            instances.

        :param short_names:

            If true keys are not full names but only the names.
            Raises a ValueError if the names are not unique.

        :param nested:

            If true returns a nested dictionary.

        :param with_links:

            If links should be considered

        :return: dictionary

        :raises: ValueError

        """

        if (fast_access or short_names or nested) and not copy:
            raise ValueError('You can not request the original data with >>fast_access=True<< or'
                             ' >>short_names=True<< of >>nested=True<<.')

        if nested and short_names:
            raise ValueError('You cannot use short_names and nested at the '
                             'same time.')

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
                iterator = temp_dict.values()
        else:
            iterator = node.f_iter_leaves(with_links=with_links)

        # If not we need to build the dict by iterating recursively over all leaves:
        result_dict = {}
        for val in iterator:
            if short_names:
                new_key = val.v_name
            else:
                new_key = val.v_full_name

            if new_key in result_dict:
                raise ValueError('Your short names are not unique. '
                                 'Duplicate key `%s`!' % new_key)

            new_val = self._apply_fast_access(val, fast_access)
            result_dict[new_key] = new_val

        if nested:
            if node.v_is_root:
                nest_dict = result_dict
            else:
                # remove the name of the current node
                # such that the nested dictionary starts with the children
                strip = len(node.v_full_name) + 1
                nest_dict = {key[strip:]: val for key, val in result_dict.items()}
            result_dict = nest_dictionary(nest_dict, '.')

        return result_dict

    @staticmethod
    def _make_child_iterator(node, with_links, current_depth=0):
        """Returns an iterator over a node's children.

        In case of using a trajectory as a run (setting 'v_crun') some sub branches
        that do not belong to the run are blinded out.

        """
        cdp1 = current_depth + 1
        if with_links:
            iterator = ((cdp1, x[0], x[1]) for x in node._children.items())
        else:
            leaves = ((cdp1, x[0], x[1]) for x in node._leaves.items())
            groups = ((cdp1, y[0], y[1]) for y in node._groups.items())
            iterator = itools.chain(groups, leaves)
        return iterator

    @staticmethod
    def _recursive_traversal_bfs(node, linked_by=None,
                                 max_depth=float('inf'),
                                 with_links=True, in_search=False, predicate=None):
        """Iterator function traversing the tree below `node` in breadth first search manner.

        If `run_name` is given only sub branches of this run are considered and the rest is
        blinded out.

        """

        if predicate is None:
            predicate = lambda x: True

        iterator_queue = IteratorChain([(0, node.v_name, node)])
        #iterator_queue = iter([(0, node.v_name, node)])
        start = True
        visited_linked_nodes = set([])

        while True:
            try:
                depth, name, item = next(iterator_queue)
                full_name = item._full_name
                if start or predicate(item):
                    if full_name in visited_linked_nodes:
                        if in_search:
                            # We need to return the node again to check if a link to the node
                            # has to be found
                            yield depth, name, item
                    elif depth <= max_depth:
                        if start:
                            start = False
                        else:
                            if in_search:
                                yield depth, name, item
                            else:
                                yield item

                        if full_name in linked_by:
                            visited_linked_nodes.add(full_name)

                        if not item._is_leaf and depth < max_depth:
                            child_iterator = NaturalNamingInterface._make_child_iterator(item,
                                                                        with_links,
                                                                        current_depth=depth)
                            iterator_queue.add(child_iterator)
                            #iterator_queue = itools.chain(iterator_queue, child_iterator)
            except StopIteration:
                break

    def _get_candidate_dict(self, key, crun, use_upper_bound=True):
        # First find all nodes where the key matches the (short) name of the node
        try:
            if crun is None:
                return self._nodes_and_leaves[key]
            # This can be false in case of links which are not added to the run sorted nodes and leaves
            else:
                temp_dict = {}
                if crun in self._nodes_and_leaves_runs_sorted[key]:
                    temp_dict = self._nodes_and_leaves_runs_sorted[key][crun]
                    if use_upper_bound and len(temp_dict) > FAST_UPPER_BOUND:
                        raise pex.TooManyGroupsError('Too many nodes')

                temp_dict2 = {}
                if 'trajectory' in self._nodes_and_leaves_runs_sorted[key]:
                    temp_dict2 = self._nodes_and_leaves_runs_sorted[key]['trajectory']
                    if use_upper_bound and len(temp_dict) + len(temp_dict2) > FAST_UPPER_BOUND:
                        raise pex.TooManyGroupsError('Too many nodes')

                return ChainMap(temp_dict, temp_dict2)
        except KeyError:
            # We end up here if `key` is actually a link
            return {}

    def _very_fast_search(self, node, key, max_depth, with_links, crun):
        """Fast search for a node in the tree.

        The tree is not traversed but the reference dictionaries are searched.

        :param node:

            Parent node to start from

        :param key:

            Name of node to find

        :param max_depth:

            Maximum depth.

        :param with_links:

            If we work with links than we can only be sure to found the node in case we
            have a single match. Otherwise the other match might have been linked as well.

        :param crun:

            If given only nodes belonging to this particular run are searched and the rest
            is blinded out.

        :return: The found node and its depth

        :raises:

            TooManyGroupsError:

                If search cannot performed fast enough, an alternative search method is needed.

            NotUniqueNodeError:

                If several nodes match the key criterion

        """

        if key in self._links_count:
            return

        parent_full_name = node.v_full_name
        starting_depth = node.v_depth
        candidate_dict = self._get_candidate_dict(key, crun)

        # If there are to many potential candidates sequential search might be too slow
        if with_links:
            upper_bound = 1
        else:
            upper_bound = FAST_UPPER_BOUND
        if len(candidate_dict) > upper_bound:
            raise pex.TooManyGroupsError('Too many nodes')

        # Next check if the found candidates could be reached from the parent node
        result_node = None
        for goal_name in candidate_dict:

            # Check if we have found a matching node
            if goal_name.startswith(parent_full_name):
                candidate = candidate_dict[goal_name]
                if candidate.v_depth - starting_depth <= max_depth:
                    # In case of several solutions raise an error:
                    if result_node is not None:
                        raise pex.NotUniqueNodeError('Node `%s` has been found more than once, '
                                                     'full name of first occurrence is `%s` and of'
                                                     'second `%s`'
                                                     % (key, goal_name, result_node.v_full_name))
                    result_node = candidate

        if result_node is not None:
            return result_node, result_node.v_depth

    def _search(self, node, key, max_depth=float('inf'), with_links=True, crun=None):
        """ Searches for an item in the tree below `node`

        :param node:

            The parent node below which the search is performed

        :param key:

            Name to search for. Can be the short name, the full name or parts of it

        :param max_depth:

            maximum search depth.

        :param with_links:

            If links should be considered

        :param crun:

            Used for very fast search if we know we operate in a single run branch

        :return: The found node and the depth it was found for

        """

        # If we find it directly there is no need for an exhaustive search
        if key in node._children and (with_links or key not in node._links):
            return node._children[key], 1

        # First the very fast search is tried that does not need tree traversal.
        try:
            result = self._very_fast_search(node, key, max_depth, with_links, crun)
            if result:
                return result
        except pex.TooManyGroupsError:
            pass
        except pex.NotUniqueNodeError:
            pass

        # Slowly traverse the entire tree
        nodes_iterator = self._iter_nodes(node, recursive=True,
                                          max_depth=max_depth, in_search=True,
                                          with_links=with_links)
        result_node = None
        result_depth = float('inf')
        for depth, name, child in nodes_iterator:

            if depth > result_depth:
                # We can break here because we enter a deeper stage of the tree and we
                # cannot find matching node of the same depth as the one we found
                break

            if key == name:
                # If result_node is not None means that we care about uniqueness and the search
                # has found more than a single solution.
                if result_node is not None:
                    raise pex.NotUniqueNodeError('Node `%s` has been found more than once within '
                                                 'the same depth %d. '
                                                 'Full name of first occurrence is `%s` and of '
                                                 'second `%s`'
                                                 % (key, child.v_depth, result_node.v_full_name,
                                                    child.v_full_name))

                result_node = child
                result_depth = depth

        return result_node, result_depth

    def _backwards_search(self, start_node, split_name, max_depth=float('inf'), shortcuts=True):
        """ Performs a backwards search from the terminal node back to the start node

        :param start_node:

            The node from where search starts, or here better way where backwards search should
            end.

        :param split_name:

            List of names

        :param max_depth:

            Maximum search depth where to look for

        :param shortcuts:

            If shortcuts are allowed

        """

        result_list = [] # Result list of all found items
        full_name_set = set() # Set containing full names of all found items to avoid finding items
        # twice due to links

        colon_name = '.'.join(split_name)
        key = split_name[-1]
        candidate_dict = self._get_candidate_dict(key, None, use_upper_bound=False)
        parent_full_name = start_node.v_full_name

        split_length = len(split_name)

        for candidate_name in candidate_dict:
            # Check if candidate startswith the parent's name
            candidate = candidate_dict[candidate_name]
            if key != candidate.v_name or candidate.v_full_name in full_name_set:
                # If this is not the case we do have link, that we need to skip
                continue

            if candidate_name.startswith(parent_full_name):
                if parent_full_name != '':
                    reduced_candidate_name = candidate_name[len(parent_full_name) + 1:]
                else:
                    reduced_candidate_name = candidate_name

                candidate_split_name = reduced_candidate_name.split('.')

                if len(candidate_split_name) > max_depth:
                    break

                if len(split_name) == 1 or reduced_candidate_name.endswith(colon_name):
                    result_list.append(candidate)
                    full_name_set.add(candidate.v_full_name)

                elif shortcuts:

                    candidate_set = set(candidate_split_name)
                    climbing = True
                    for name in split_name:
                        if name not in candidate_set:
                            climbing = False
                            break

                    if climbing:
                        count = 0
                        candidate_length = len(candidate_split_name)
                        for idx in range(candidate_length):

                            if idx + split_length - count > candidate_length:
                                break

                            if split_name[count] == candidate_split_name[idx]:
                                count += 1
                                if count == len(split_name):
                                    result_list.append(candidate)
                                    full_name_set.add(candidate.v_full_name)
                                    break

        return result_list

    def _get_all(self, node, name, max_depth, shortcuts):
        """ Searches for all occurrences of `name` under `node`.

        :param node:

            Start node

        :param name:

            Name what to look for can be longer and separated by colons, i.e.
            `mygroupA.mygroupB.myparam`.

        :param max_depth:

            Maximum depth to search for relative to start node.

        :param shortcuts:

            If shortcuts are allowed

        :return:

            List of nodes that match the name, empty list if nothing was found.

        """

        if max_depth is None:
            max_depth = float('inf')

        if isinstance(name, list):
            split_name = name
        elif isinstance(name, tuple):
            split_name = list(name)
        elif isinstance(name, int):
            split_name = [name]
        else:
            split_name = name.split('.')

        for idx, key in enumerate(split_name):
            _, key = self._translate_shortcut(key)
            _, key = self._replace_wildcards(key)
            split_name[idx] = key

        return self._backwards_search(node, split_name, max_depth, shortcuts)

    def _check_flat_dicts(self, node, split_name):

        # Check in O(d) first if a full parameter/result name is given and
        # we might be able to find it in the flat storage dictionary or the group dictionary.
        # Here `d` refers to the depth of the tree
        fullname = '.'.join(split_name)

        if fullname.startswith(node.v_full_name):
            new_name = fullname
        else:
            new_name = node.v_full_name + '.' + fullname

        if new_name in self._flat_leaf_storage_dict:
            return self._flat_leaf_storage_dict[new_name]

        if new_name in self._root_instance._all_groups:
            return self._root_instance._all_groups[new_name]

        return None

    def _get(self, node, name, fast_access,
             shortcuts, max_depth, auto_load, with_links):
        """Searches for an item (parameter/result/group node) with the given `name`.

        :param node: The node below which the search is performed

        :param name: Name of the item (full name or parts of the full name)

        :param fast_access: If the result is a parameter, whether fast access should be applied.

        :param max_depth:

            Maximum search depth relative to start node.

        :param auto_load:

            If data should be automatically loaded

        :param with_links

            If links should be considered

        :return:

            The found instance (result/parameter/group node) or if fast access is True and you
            found a parameter or result that supports fast access, the contained value is returned.

        :raises:

            AttributeError if no node with the given name can be found.
            Raises errors that are raised by the storage service if `auto_load=True` and
            item cannot be found.

        """
        if auto_load and not with_links:
            raise ValueError('If you allow auto-loading you mus allow links.')

        if isinstance(name, list):
            split_name = name
        elif isinstance(name, tuple):
            split_name = list(name)
        elif isinstance(name, int):
            split_name = [name]
        else:
            split_name = name.split('.')

        if node.v_is_root:
            # We want to add `parameters`, `config`, `derived_parameters` and `results`
            # on the fly if they don't exist
            if len(split_name) == 1 and split_name[0] == '':
                return node
            key = split_name[0]
            _, key = self._translate_shortcut(key)
            if key in SUBTREE_MAPPING and key not in node._children:
                node.f_add_group(key)

        if max_depth is None:
            max_depth = float('inf')

        if len(split_name) > max_depth and shortcuts:
            raise ValueError(
                'Name of node to search for (%s) is longer thant the maximum depth %d' %
                (str(name), max_depth))

        try_auto_load_directly1 = False
        try_auto_load_directly2 = False
        wildcard_positions = []

        root = self._root_instance
        # # Rename shortcuts and check keys:
        for idx, key in enumerate(split_name):
            translated_shortcut, key = self._translate_shortcut(key)
            if translated_shortcut:
                split_name[idx] = key

            if key[0] == '_':
                raise AttributeError('Leading underscores are not allowed '
                                     'for group or parameter '
                                     'names. Cannot return %s.' % key)

            is_wildcard = self._root_instance.f_is_wildcard(key)
            if (not is_wildcard and key not in self._nodes_and_leaves and
                    key not in self._links_count):
                try_auto_load_directly1 = True
                try_auto_load_directly2 = True

            if is_wildcard:
                wildcard_positions.append((idx, key))
                if root.f_wildcard(key) not in self._nodes_and_leaves:
                    try_auto_load_directly1 = True
                if root.f_wildcard(key, -1) not in self._nodes_and_leaves:
                    try_auto_load_directly2 = True

        run_idx = root.v_idx
        wildcard_exception = None # Helper variable to store the exception thrown in case
        # of using a wildcard, to be re-thrown later on.

        if try_auto_load_directly1 and try_auto_load_directly2 and not auto_load:
            for wildcard_pos, wildcard in wildcard_positions:
                split_name[wildcard_pos] = root.f_wildcard(wildcard, run_idx)
            raise AttributeError('%s is not part of your trajectory or it\'s tree. ' %
                                 str('.'.join(split_name)))

        if run_idx > -1:
            # If we count the wildcard we have to perform the search twice,
            # one with a run name and one with the dummy:
            with self._disable_logging:
                try:
                    for wildcard_pos, wildcard in wildcard_positions:
                        split_name[wildcard_pos] = root.f_wildcard(wildcard, run_idx)

                    result = self._perform_get(node, split_name, fast_access,
                                               shortcuts, max_depth, auto_load, with_links,
                                               try_auto_load_directly1)
                    return result
                except (pex.DataNotInStorageError, AttributeError) as exc:
                    wildcard_exception = exc

        if wildcard_positions:
            for wildcard_pos, wildcard in wildcard_positions:
                split_name[wildcard_pos] = root.f_wildcard(wildcard, -1)
        try:
            return self._perform_get(node, split_name, fast_access,
                                     shortcuts, max_depth, auto_load, with_links,
                                     try_auto_load_directly2)
        except (pex.DataNotInStorageError, AttributeError):
            # Re-raise the old error in case it was thronw already
            if wildcard_exception is not None:
                raise wildcard_exception
            else:
                raise

    def _perform_get(self, node, split_name, fast_access,
                     shortcuts, max_depth, auto_load, with_links,
                     try_auto_load_directly):
        """Searches for an item (parameter/result/group node) with the given `name`.

        :param node: The node below which the search is performed

        :param split_name: Name split into list according to '.'

        :param fast_access: If the result is a parameter, whether fast access should be applied.

        :param max_depth:

            Maximum search depth relative to start node.

        :param auto_load:

            If data should be automatically loaded

        :param with_links:

            If links should be considered.

        :param try_auto_load_directly:

            If one should skip search and directly try auto_loading

        :return:

            The found instance (result/parameter/group node) or if fast access is True and you
            found a parameter or result that supports fast access, the contained value is returned.

        :raises:

            AttributeError if no node with the given name can be found
            Raises errors that are raiesd by the storage service if `auto_load=True`

        """

        result = None
        name = '.'.join(split_name)

        if len(split_name) > max_depth:
            raise AttributeError('The node or param/result `%s`, cannot be found under `%s`'
                                 'The name you are looking for is larger than the maximum '
                                 'search depth.' %
                                 (name, node.v_full_name))

        if shortcuts and not try_auto_load_directly:
            first = split_name[0]

            if len(split_name) == 1 and first in node._children and (with_links or
                                                                    first not in node._links):
                result = node._children[first]
            else:

                result = self._check_flat_dicts(node, split_name)

                if result is None:
                    # Check in O(N) with `N` number of groups and nodes
                    # [Worst Case O(N), average case is better
                    # since looking into a single dict costs O(1)].
                    result = node
                    crun = None
                    for key in split_name:
                        if key in self._root_instance._run_information:
                            crun = key
                        result, depth = self._search(result, key, max_depth, with_links, crun)
                        max_depth -= depth
                        if result is None:
                            break

        elif not try_auto_load_directly:
            result = node
            for name in split_name:
                if name in result._children and (with_links or not name in result._links):
                    result = result._children[name]
                else:
                    raise AttributeError(
                        'You did not allow for shortcuts and `%s` was not directly '
                        'found  under node `%s`.' % (name, result.v_full_name))

        if result is None and auto_load:
            try:
                result = node.f_load_child('.'.join(split_name),
                                           load_data=pypetconstants.LOAD_DATA)
                if (self._root_instance.v_idx != -1 and
                            result.v_is_leaf and
                            result.v_is_parameter and
                            result.v_explored):
                    result._set_parameter_access(self._root_instance.v_idx)
            except:
                self._logger.error('Error while auto-loading `%s` under `%s`.' %
                                   (name, node.v_full_name))
                raise

        if result is None:
            raise AttributeError('The node or param/result `%s`, cannot be found under `%s`' %
                                 (name, node.v_full_name))
        if result.v_is_leaf:
            if auto_load and result.f_is_empty():

                try:
                    self._root_instance.f_load_item(result)
                    if (self._root_instance.v_idx != -1 and
                            result.v_is_parameter and
                            result.v_explored):
                        result._set_parameter_access(self._root_instance.v_idx)
                except:
                    self._logger.error('Error while auto-loading `%s` under `%s`. I found the '
                                       'item but I could not load the data.' %
                                       (name, node.v_full_name))
                    raise

            return self._apply_fast_access(result, fast_access)
        else:
            return result


class NNGroupNode(NNTreeNode, KnowsTrajectory):
    """A group node hanging somewhere under the trajectory or single run root node.

    You can add other groups or parameters/results to it.

    """

    __slots__ = ('_children_', '_links_', '_groups_', '_leaves_',
                 '_nn_interface', '_kids')

    def __init__(self, full_name='', trajectory=None, comment=''):
        super(NNGroupNode, self).__init__(full_name, comment=comment, is_leaf=False)
        self._children_ = None
        self._links_ = None
        self._groups_ = None
        self._leaves_ = None
        self._kids = None
        if trajectory is not None:
            self._nn_interface = trajectory._nn_interface
        else:
            self._nn_interface = None

    @property
    def _children(self):
        if self._children_ is None:
            self._children_ = {}
        return self._children_

    @property
    def _links(self):
        if self._links_ is None:
            self._links_ = {}
        return self._links_

    @property
    def _groups(self):
        if self._groups_ is None:
            self._groups_ = {}
        return self._groups_

    @property
    def _leaves(self):
        if self._leaves_ is None:
            self._leaves_ = {}
        return self._leaves_

    @property
    def kids(self):
        """Alternative naming, you can use `node.kids.name` instead of `node.name`
        for easier tab completion."""
        if self._kids is None:
            self._kids = NNTreeNodeKids(self)
        return self._kids

    def __copy__(self):
        """Shallow copy includes copy of full tree but not leave nodes"""
        root_copy = self.v_root.__copy__()
        return root_copy.f_get(self.v_full_name,
                               auto_load=False,
                               shortcuts=False,
                               with_links=False)

    def __repr__(self):
        return '<%s>' % self.__str__()

    def _get_children_representation(self):
        children_string_list = []

        for idx, key in enumerate(self._children):
            children_string_list.append('(%s: %s)' % (key, str(type(self._children[key]))))

            if idx == 5:
                children_string_list.append('...')
                break

        children_string = ', '.join(children_string_list)

        return children_string

    def __str__(self):
        if self.v_comment:
            commentstring = ' (`%s`)' % self.v_comment
        else:
            commentstring = ''

        children_string = self._get_children_representation()

        return '%s %s%s: %s' % (self.f_get_class_name(), self.v_full_name, commentstring,
                                children_string)

    def _add_group_from_storage(self, args, kwargs):
        """Can be called from storage service to create a new group to bypass name checking"""
        return self._nn_interface._add_generic(self,
                                                type_name=GROUP,
                                                group_type_name=GROUP,
                                                args=args,
                                                kwargs=kwargs,
                                                add_prefix=False,
                                                check_naming=False)

    def _add_leaf_from_storage(self, args, kwargs):
        """Can be called from storage service to create a new leaf to bypass name checking"""
        return self._nn_interface._add_generic(self,
                                                type_name=LEAF,
                                                group_type_name=GROUP,
                                                args=args, kwargs=kwargs,
                                                add_prefix=False,
                                                check_naming=False)

    def f_dir_data(self):
        """Returns a list of all children names"""
        if (self._nn_interface is not None and
                    self._nn_interface._root_instance is not None
                        and self.v_root.v_auto_load):
            try:
                if self.v_is_root:
                    self.f_load(recursive=True, max_depth=1,
                                load_data=pypetconstants.LOAD_SKELETON,
                                with_meta_data=False,
                                with_run_information=False)
                else:
                    self.f_load(recursive=True, max_depth=1, load_data=pypetconstants.LOAD_SKELETON)
            except Exception as exc:
                pass
        return list(self._children.keys())

    def __dir__(self):
        """Adds all children to auto-completion"""
        result = super(NNGroupNode, self).__dir__()
        if not is_debug():
            result.extend(self.f_dir_data())
        return result

    def __iter__(self):
        """Equivalent to call :func:`~pypet.naturalnaming.NNGroupNode.f_iter_nodes`

        Whether to iterate recursively is determined by `v_iter_recursive`.

        """
        return self.f_iter_nodes(recursive=self.v_root.v_iter_recursive)

    def f_debug(self):
        """Creates a dummy object containing the whole tree to make unfolding easier.

        This method is only useful for debugging purposes.
        If you use an IDE and want to unfold the trajectory tree, you always need to
        open the private attribute `_children`. Use to this function to create a new
        object that contains the tree structure in its attributes.

        Manipulating the returned object does not change the original tree!

        """
        return self._debug()

    def _debug(self):
        """Creates a dummy object containing the whole tree to make unfolding easier.

        This method is only useful for debugging purposes.
        If you use an IDE and want to unfold the trajectory tree, you always need to
        open the private attribute `_children`. Use to this function to create a new
        object that contains the tree structure in its attributes.

        Manipulating the returned object does not change the original tree!

        """

        class Bunch(object):
            """Dummy container class"""
            pass

        debug_tree = Bunch()

        if not self.v_annotations.f_is_empty():
            debug_tree.v_annotations = self.v_annotations
        if not self.v_comment == '':
            debug_tree.v_comment = self.v_comment

        for leaf_name in self._leaves:
            leaf = self._leaves[leaf_name]
            setattr(debug_tree, leaf_name, leaf)

        for link_name in self._links:
            linked_node = self._links[link_name]
            setattr(debug_tree, link_name, 'Link to `%s`' % linked_node.v_full_name)

        for group_name in self._groups:
            group = self._groups[group_name]
            setattr(debug_tree, group_name, group._debug())

        return debug_tree

    def f_get_parent(self):
        """Returns the parent of the node.

        Raises a TypeError if current node is root.

        """
        if self.v_is_root:
            raise TypeError('Root does not have a parent')
        elif self.v_location == '':
            return self.v_root
        else:
            return self.v_root.f_get(self.v_location, fast_access=False, shortcuts=False)

    def f_add_group(self, *args, **kwargs):
        """Adds an empty generic group under the current node.

        You can add to a generic group anywhere you want. So you are free to build
        your parameter tree with any structure. You do not necessarily have to follow the
        four subtrees `config`, `parameters`, `derived_parameters`, `results`.

        If you are operating within these subtrees this simply calls the corresponding adding
        function.

        Be aware that if you are within a single run and you add items not below a group
        `run_XXXXXXXX` that you have to manually
        save the items. Otherwise they will be lost after the single run is completed.

        """

        return self._nn_interface._add_generic(self, type_name=GROUP,
                                               group_type_name=GROUP,
                                               args=args, kwargs=kwargs, add_prefix=False)

    def f_add_link(self, name_or_item, full_name_or_item=None):
        """Adds a link to an existing node.

        Can be called as ``node.f_add_link(other_node)`` this will add a link the `other_node`
        with the link name as the name of the node.

        Or can be called as ``node.f_add_link(name, other_node)`` to add a link to the
        `other_node` and the given `name` of the link.

        In contrast to addition of groups and leaves,  colon separated names
        are **not** allowed, i.e. ``node.f_add_link('mygroup.mylink', other_node)``
        does not work.

        """
        if isinstance(name_or_item, str):
            name = name_or_item
            if isinstance(full_name_or_item, str):
                instance = self.v_root.f_get(full_name_or_item)
            else:
                instance =  full_name_or_item
        else:
            instance = name_or_item
            name = instance.v_name

        return self._nn_interface._add_generic(self, type_name=LINK,
                                               group_type_name=GROUP, args=(name, instance),
                                               kwargs={},
                                               add_prefix=False)

    def f_remove_link(self, name):
        """ Removes a link from from the current group node with a given name.

        Does not delete the link from the hard drive. If you want to do this,
        checkout :func:`~pypet.trajectory.Trajectory.f_delete_links`

        """
        if name not in self._links:
            raise ValueError('No link with name `%s` found under `%s`.' % (name, self._full_name))

        self._nn_interface._remove_link(self, name)

    def f_add_leaf(self, *args, **kwargs):
        """Adds an empty generic leaf under the current node.

        You can add to a generic leaves anywhere you want. So you are free to build
        your trajectory tree with any structure. You do not necessarily have to follow the
        four subtrees `config`, `parameters`, `derived_parameters`, `results`.

        If you are operating within these subtrees this simply calls the corresponding adding
        function.

        Be aware that if you are within a single run and you add items not below a group
        `run_XXXXXXXX` that you have to manually
        save the items. Otherwise they will be lost after the single run is completed.

        """

        return self._nn_interface._add_generic(self, type_name=LEAF,
                                               group_type_name=GROUP,
                                               args=args, kwargs=kwargs,
                                               add_prefix=False)

    def f_links(self):
        """Returns the number of links of the group"""
        return len(self._links)

    def f_has_links(self):
        """Checks if node has children or not"""
        return len(self._links) != 0

    def f_children(self):
        """Returns the number of children of the group"""
        return len(self._children)

    def f_has_children(self):
        """Checks if node has children or not"""
        return len(self._children) != 0

    def f_leaves(self):
        """Returns the number of immediate leaves of the group"""
        return len(self._leaves)

    def f_has_leaves(self):
        """Checks if node has leaves or not"""
        return len(self._leaves) != 0

    def f_groups(self):
        """Returns the number of immediate groups of the group"""
        return len(self._groups)

    def f_has_groups(self):
        """Checks if node has groups or not"""
        return len(self._groups) != 0

    def __contains__(self, item):
        """Equivalent to calling :func:`~pypet.naturalnaming.NNGroupNode.f_contains`.

        Whether to allow shortcuts is taken from `v_shortcuts`.
        Whether to stop at a given depth is taken from `v_max_depth`.

        """
        return self.f_contains(item,
                               shortcuts=self.v_root.v_shortcuts,
                               max_depth=self.v_root.v_max_depth,
                               with_links=self.v_root.v_with_links)

    def f_remove(self, recursive=True, predicate=None):
        """Recursively removes the group and all it's children.

        :param recursive:

            If removal should be applied recursively. If not, node can only be removed
            if it has no children.

        :param predicate:

            In case of recursive removal, you can selectively remove nodes in the tree.
            Predicate which can evaluate for each node to ``True`` in order to remove the node or
            ``False`` if the node should be kept. Leave ``None`` if you want to remove all nodes.

        """
        parent = self.f_get_parent()
        parent.f_remove_child(self.v_name, recursive=recursive, predicate=predicate)

    def f_remove_child(self, name, recursive=False, predicate=None):
        """Removes a child of the group.

        Note that groups and leaves are only removed from the current trajectory in RAM.
        If the trajectory is stored to disk, this data is not affected. Thus, removing children
        can be only be used to free RAM memory!

        If you want to free memory on disk via your storage service,
        use :func:`~pypet.trajectory.Trajectory.f_delete_items` of your trajectory.

        :param name:

            Name of child, naming by grouping is NOT allowed ('groupA.groupB.childC'),
            child must be direct successor of current node.

        :param recursive:

            Must be true if child is a group that has children. Will remove
            the whole subtree in this case. Otherwise a Type Error is thrown.

        :param predicate:

            Predicate which can evaluate for each node to ``True`` in order to remove the node or
            ``False`` if the node should be kept. Leave ``None`` if you want to remove all nodes.

        :raises:

            TypeError if recursive is false but there are children below the node.

            ValueError if child does not exist.

        """
        if name not in self._children:
            raise ValueError('Your group `%s` does not contain the child `%s`.' %
                             (self.v_full_name, name))
        else:
            child = self._children[name]
            if (name not in self._links and
                    not child.v_is_leaf and
                    child.f_has_children() and
                    not recursive):
                raise TypeError('Cannot remove child. It is a group with children. Use'
                                ' f_remove with ``recursive = True``')
            else:
                self._nn_interface._remove_subtree(self, name, predicate)

    @kwargs_api_change('backwards_search')
    def f_contains(self, item, with_links=True, shortcuts=False, max_depth=None):
        """Checks if the node contains a specific parameter or result.

        It is checked if the item can be found via the
        :func:`~pypet.naturalnaming.NNGroupNode.f_get` method.

        :param item: Parameter/Result name or instance.

            If a parameter or result instance is supplied it is also checked if
            the provided item and the found item are exactly the same instance, i.e.
            `id(item)==id(found_item)`.

        :param with_links:

            If links are considered.

        :param shortcuts:

            Shortcuts is `False` the name you supply must
            be found in the tree WITHOUT hopping over nodes in between.
            If `shortcuts=False` and you supply a
            non colon separated (short) name, than the name must be found
            in the immediate children of your current node.
            Otherwise searching via shortcuts is allowed.

        :param max_depth:

            If shortcuts is `True` than the maximum search depth
            can be specified. `None` means no limit.

        :return: True or False

        """

        # Check if an instance or a name was supplied by the user
        try:
            search_string = item.v_full_name
            parent_full_name = self.v_full_name

            if not search_string.startswith(parent_full_name):
                return False

            if parent_full_name != '':
                search_string = search_string[len(parent_full_name) + 1:]
            else:
                search_string = search_string

            shortcuts = False # if we search for a particular item we do not allow shortcuts

        except AttributeError:
            search_string = item
            item = None

        if search_string == '':
            return False # To allow to search for nodes wit name = '', which are never part
            # of the trajectory

        try:
            result = self.f_get(search_string,
                                shortcuts=shortcuts, max_depth=max_depth, with_links=with_links)
        except AttributeError:
            return False

        if item is not None:
            return id(item) == id(result)
        else:
            return True

    def __setitem__(self, key, value):
        split_key = key.split('.')
        last_key = split_key.pop()
        current = self
        for key_ in split_key:
            current = self._nn_interface._get(current, key_,
                                   fast_access=self.v_root.v_fast_access,
                                   shortcuts=self.v_root.v_shortcuts,
                                   max_depth=self.v_root.v_max_depth,
                                   auto_load=self.v_root.v_auto_load,
                                   with_links=self.v_root.v_with_links)

        setattr(current, last_key, value)

    def __setattr__(self, key, value):
        if key.startswith('_'):
            # We set a private attribute
            super(NNGroupNode, self).__setattr__(key, value)
        elif hasattr(self.__class__, key):
            # If we set a property we need this work around here:
            python_property = getattr(self.__class__, key)
            if python_property.fset is None:
                raise AttributeError('%s is read only!' % key)
            else:
                python_property.fset(self, value)
        elif isinstance(value, (NNGroupNode, NNLeafNode)):
            old_name = value.v_full_name
            try:
                _, key = self._nn_interface._translate_shortcut(key)
                if self.v_root.f_contains(value, shortcuts=False, with_links=False):
                    self.f_add_link(key, value)
                else:
                    name = value.v_full_name
                    if name == '':
                        value._rename(key)
                    elif name != key and not name.startswith(key + '.'):
                        raise AttributeError('The name of your element and the key do not match: '
                                             '`%s` != `%s`' % (name, key))
                    if isinstance(value, NNGroupNode):
                        self.f_add_group(value)
                    else:
                        self.f_add_leaf(value)
            except:
                value._set_details(old_name, None, None)
                raise
        else:
            instance = self.f_get(key)
            if instance.v_is_parameter or instance.f_supports_fast_access():
                instance.f_set(value)
            else:
                raise AttributeError('Cannot change the value of the result `%s` because '
                                     'it contains more than one data '
                                     'item.' % instance.v_full_name)

    def __getitem__(self, item):
        """Equivalent to calling `__getattr__`.

        Per default the item is returned and fast access is applied.

        """
        return self._nn_interface._get(self, item,
                                       fast_access=self.v_root.v_fast_access,
                                       shortcuts=self.v_root.v_shortcuts,
                                       max_depth=self.v_root.v_max_depth,
                                       auto_load=self.v_root.v_auto_load,
                                       with_links=self.v_root.v_with_links)

    # @no_prefix_getattr
    def __getattr__(self, name):
        if isinstance(name, str) and name.startswith('_'):
            raise AttributeError('`%s` is not part of your trajectory or it\'s tree.' % name)
        return self._nn_interface._get(self, name,
                                       fast_access=self.v_root.v_fast_access,
                                       shortcuts=self.v_root.v_shortcuts,
                                       max_depth=self.v_root.v_max_depth,
                                       auto_load=self.v_root.v_auto_load,
                                       with_links=self.v_root.v_with_links)

    @property
    def v_root(self):
        """Link to the root of the tree, i.e. the trajectory"""
        return self._nn_interface._root_instance

    def f_iter_nodes(self, recursive=True, with_links=True, max_depth=None, predicate=None):
        """Iterates recursively (default) over nodes hanging below this group.

        :param recursive: Whether to iterate the whole sub tree or only immediate children.

        :param with_links: If links should be considered

        :param max_depth: Maximum depth in search tree relative to start node (inclusive)

        :param predicate:

            A predicate function that is applied for each node and only returns the node
            if it evaluates to ``True``. If ``False``
            and you iterate recursively also the children are spared.

            Leave to `None` if you don't want to filter and simply iterate over all nodes.


            For example, to iterate only over groups you could use:

            >>> traj.f_iter_nodes(recursive=True, predicate=lambda x: x.v_is_group)

            To blind out all runs except for a particular set, you can simply pass a tuple
            of run indices with -1 referring to the ``run_ALL`` node.

            For instance

            >>> traj.f_iter_nodes(recursive=True, predicate=(0,3,-1))

            Will blind out all nodes hanging below a group named ``run_XXXXXXXXX``
            (including the group) except ``run_00000000``, ``run_00000003``, and ``run_ALL``.


        :return: Iterator over nodes

        """
        return self._nn_interface._iter_nodes(self, recursive=recursive, with_links=with_links,
                                              max_depth=max_depth,
                                              predicate=predicate)

    def f_iter_leaves(self, with_links=True):
        """Iterates (recursively) over all leaves hanging below the current group.

        :param with_links:

            If links should be ignored, leaves hanging below linked nodes are not listed.

        :returns:

            Iterator over all leaf nodes

        """
        for node in self.f_iter_nodes(with_links=with_links):
            if node.v_is_leaf:
                yield node

    def f_get_all(self, name, max_depth=None, shortcuts=True):
        """ Searches for all occurrences of `name` under `node`.

        Links are NOT considered since nodes are searched bottom up in the tree.

        :param node:

            Start node

        :param name:

            Name of what to look for, can be separated by colons, i.e.
            ``'mygroupA.mygroupB.myparam'``.

        :param max_depth:

            Maximum search depth relative to start node.
            `None` for no limit.

        :param shortcuts:

            If shortcuts are allowed, otherwise the stated name defines a
            consecutive name.For instance. ``'mygroupA.mygroupB.myparam'`` would
            also find ``mygroupA.mygroupX.mygroupB.mygroupY.myparam`` if shortcuts
            are allowed, otherwise not.

        :return:

            List of nodes that match the name, empty list if nothing was found.

        """
        return self._nn_interface._get_all(self, name, max_depth=max_depth, shortcuts=shortcuts)

    @kwargs_api_change('backwards_search')
    def f_get_default(self, name, default=None, fast_access=True, with_links=True,
              shortcuts=True, max_depth=None, auto_load=False):
        """ Similar to `f_get`, but returns the default value if `name` is not found in the
        trajectory.

        This function uses the `f_get` method and will return the default value
        in case `f_get` raises an AttributeError or a DataNotInStorageError.
        Other errors are not handled.

        In contrast to `f_get`, fast access is True by default.

        """
        try:
            return self.f_get(name, fast_access=fast_access,
                           shortcuts=shortcuts,
                           max_depth=max_depth,
                           auto_load=auto_load,
                           with_links=with_links)

        except (AttributeError, pex.DataNotInStorageError):
            return default

    @kwargs_api_change('backwards_search')
    def f_get(self, name, fast_access=False, with_links=True,
              shortcuts=True, max_depth=None, auto_load=False):
        """Searches and returns an item (parameter/result/group node) with the given `name`.

        :param name: Name of the item (full name or parts of the full name)

        :param fast_access: Whether fast access should be applied.

        :param with_links:

            If links are considered. Cannot be set to ``False`` if ``auto_load`` is ``True``.

        :param shortcuts:

            If shortcuts are allowed and the trajectory can *hop* over nodes in the
            path.

        :param max_depth:

            Maximum depth relative to starting node (inclusive).
            `None` means no depth limit.

        :param auto_load:

            If data should be loaded from the storage service if it cannot be found in the
            current trajectory tree. Auto-loading will load group and leaf nodes currently
            not in memory and it will load data into empty leaves. Be aware that auto-loading
            does not work with shortcuts.

        :return:

            The found instance (result/parameter/group node) or if fast access is True and you
            found a parameter or result that supports fast access, the contained value is returned.

        :raises:

            AttributeError: If no node with the given name can be found

            NotUniqueNodeError

                In case of forward search if more than one candidate node is found within a
                particular depth of the tree. In case of backwards search if more than
                one candidate is found regardless of the depth.

            DataNotInStorageError:

                In case auto-loading fails

            Any exception raised by the StorageService in case auto-loading is enabled

        """
        return self._nn_interface._get(self, name, fast_access=fast_access,
                                       shortcuts=shortcuts,
                                       max_depth=max_depth,
                                       auto_load=auto_load,
                                       with_links=with_links)

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

    def f_get_groups(self, copy=True):
        """Returns a dictionary of groups hanging immediately below this group.

        :param copy:

            Whether the group's original dictionary or a shallow copy is returned.
            If you want the real dictionary please do not modify it at all!

        :returns: Dictionary of nodes

        """
        if copy:
            return self._groups.copy()
        else:
            return self._groups

    def f_get_leaves(self, copy=True):
        """Returns a dictionary of all leaves hanging immediately below this group.

        :param copy:

            Whether the group's original dictionary or a shallow copy is returned.
            If you want the real dictionary please do not modify it at all!

        :returns: Dictionary of nodes

        """
        if copy:
            return self._leaves.copy()
        else:
            return self._leaves

    def f_get_links(self, copy=True):
        """Returns a link dictionary.

        :param copy:

            Whether the group's original dictionary or a shallow copy is returned.
            If you want the real dictionary please do not modify it at all!

        :returns: Dictionary of nodes

        """
        if copy:
            return self._links.copy()
        else:
            return self._links

    def f_to_dict(self, fast_access=False, short_names=False, nested=False, with_links=True):
        """Returns a dictionary with pairings of (full) names as keys and instances as values.

        This will iteratively traverse the tree and add all nodes below this group to
        the dictionary.

        :param fast_access:

            If True parameter or result values are returned instead of the instances.

        :param short_names:

            If true keys are not full names but only the names. Raises a ValueError
            if the names are not unique.

        :param nested:

            If dictionary should be nested

        :param with_links:

            If links should be considered

        :return: dictionary

        :raises: ValueError

        """
        return self._nn_interface._to_dict(self, fast_access=fast_access, short_names=short_names,
                                           nested=nested, with_links=with_links)

    def f_store_child(self, name, recursive=False, store_data=pypetconstants.STORE_DATA,
                      max_depth=None):
        """Stores a child or recursively a subtree to disk.

        :param name:

            Name of child to store. If grouped ('groupA.groupB.childC') the path along the way
            to last node in the chain is stored. Shortcuts are NOT allowed!

        :param recursive:

            Whether recursively all children's children should be stored too.

        :param store_data:

            For how to choose 'store_data' see :ref:`more-on-storing`.

        :param max_depth:

            In case `recursive` is `True`, you can specify the maximum depth to store
            data relative from current node. Leave `None` if you don't want to limit
            the depth.

        :raises: ValueError if the child does not exist.

        """
        if not self.f_contains(name, shortcuts=False):
            raise ValueError('Your group `%s` does not (directly) contain the child `%s`. '
                             'Please not that shortcuts are not allowed for `f_store_child`.' %
                             (self.v_full_name, name))

        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.store(pypetconstants.TREE, self, name,
                              trajectory_name=traj.v_name,
                              recursive=recursive,
                              store_data=store_data,
                              max_depth=max_depth)

    def f_store(self, recursive=True, store_data=pypetconstants.STORE_DATA,
                max_depth=None):
        """Stores a group node to disk

        :param recursive:

            Whether recursively all children should be stored too. Default is ``True``.

        :param store_data:

            For how to choose 'store_data' see :ref:`more-on-storing`.

        :param max_depth:

            In case `recursive` is `True`, you can specify the maximum depth to store
            data relative from current node. Leave `None` if you don't want to limit
            the depth.

        """
        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.store(pypetconstants.GROUP, self,
                              trajectory_name=traj.v_name,
                              recursive=recursive,
                              store_data=store_data,
                              max_depth=max_depth)

    def f_load_child(self, name, recursive=False, load_data=pypetconstants.LOAD_DATA,
                     max_depth=None):
        """Loads a child or recursively a subtree from disk.

        :param name:

            Name of child to load. If grouped ('groupA.groupB.childC') the path along the way
            to last node in the chain is loaded. Shortcuts are NOT allowed!

        :param recursive:

            Whether recursively all nodes below the last child should be loaded, too.
            Note that links are never evaluated recursively. Only the linked node
            will be loaded if it does not exist in the tree, yet. Any nodes or links
            of this linked node are not loaded.

        :param load_data:

            Flag how to load the data.
            For how to choose 'load_data' see :ref:`more-on-loading`.

        :param max_depth:

            In case `recursive` is `True`, you can specify the maximum depth to load
            load data relative from current node. Leave `None` if you don't want to limit
            the depth.

        :returns:

            The loaded child, in case of grouping ('groupA.groupB.childC') the last
            node (here 'childC') is returned.

        """

        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.load(pypetconstants.TREE, self, name,
                             trajectory_name=traj.v_name,
                             load_data=load_data,
                             recursive=recursive,
                             max_depth=max_depth)

        return self.f_get(name, shortcuts=False)

    def f_load(self, recursive=True, load_data=pypetconstants.LOAD_DATA,
               max_depth=None):
        """Loads a group from disk.

        :param recursive:

            Default is ``True``.
            Whether recursively all nodes below the current node should be loaded, too.
            Note that links are never evaluated recursively. Only the linked node
            will be loaded if it does not exist in the tree, yet. Any nodes or links
            of this linked node are not loaded.

        :param load_data:

            Flag how to load the data.
            For how to choose 'load_data' see :ref:`more-on-loading`.

        :param max_depth:

            In case `recursive` is `True`, you can specify the maximum depth to load
            load data relative from current node.

        :returns:

            The node itself.

        """

        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.load(pypetconstants.GROUP, self,
                             trajectory_name=traj.v_name,
                             load_data=load_data,
                             recursive=recursive,
                             max_depth=max_depth)
        return self


class ParameterGroup(NNGroupNode):
    """ Group node in your trajectory, hanging below `traj.parameters`.

    You can add other groups or parameters to it.

    """
    __slots__ = ()

    def f_add_parameter_group(self, *args, **kwargs):
        """Adds an empty parameter group under the current node.

        Can be called with ``f_add_parameter_group('MyName', 'this is an informative comment')``
        or ``f_add_parameter_group(name='MyName', comment='This is an informative comment')``
        or with a given new group instance:
        ``f_add_parameter_group(ParameterGroup('MyName', comment='This is a comment'))``.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is the trajectory (root), the prefix `'parameters'`
        is added to the full name.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        created.

        """
        return self._nn_interface._add_generic(self, type_name=PARAMETER_GROUP,
                                               group_type_name=PARAMETER_GROUP,
                                               args=args, kwargs=kwargs)

    def f_add_parameter(self, *args, **kwargs):
        """ Adds a parameter under the current node.

        There are two ways to add a new parameter either by adding a parameter instance:

        >>> new_parameter = Parameter('group1.group2.myparam', data=42, comment='Example!')
        >>> traj.f_add_parameter(new_parameter)

        Or by passing the values directly to the function, with the name being the first
        (non-keyword!) argument:

        >>> traj.f_add_parameter('group1.group2.myparam', 42, comment='Example!')

        If you want to create a different parameter than the standard parameter, you can
        give the constructor as the first (non-keyword!) argument followed by the name
        (non-keyword!):

        >>> traj.f_add_parameter(PickleParameter,'group1.group2.myparam', data=42, comment='Example!')

        The full name of the current node is added as a prefix to the given parameter name.
        If the current node is the trajectory the prefix `'parameters'` is added to the name.

        Note, all non-keyword and keyword parameters apart from the optional constructor
        are passed on as is to the constructor.

        Moreover, you always should specify a default data value of a parameter,
        even if you want to explore it later.

        """
        return self._nn_interface._add_generic(self, type_name=PARAMETER,
                                               group_type_name=PARAMETER_GROUP,
                                               args=args, kwargs=kwargs)

    f_apar = f_add_parameter  # Abbreviation of the function


class ResultGroup(NNGroupNode):
    """Group node in your trajectory, hanging below `traj.results`.

    You can add other groups or results to it.

    """

    __slots__ = ()

    def f_add_result_group(self, *args, **kwargs):
        """Adds an empty result group under the current node.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is a single run (root) adds the prefix `'results.runs.run_08%d%'` to the
        full name where `'08%d'` is replaced by the index of the current run.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        """

        return self._nn_interface._add_generic(self, type_name=RESULT_GROUP,
                                               group_type_name=RESULT_GROUP,
                                               args=args, kwargs=kwargs)

    def f_add_result(self, *args, **kwargs):
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
        If current node is a single run (root) adds the prefix `'results.runs.run_08%d%'` to the
        full name where `'08%d'` is replaced by the index of the current run.

        """
        return self._nn_interface._add_generic(self, type_name=RESULT,
                                               group_type_name=RESULT_GROUP,
                                               args=args, kwargs=kwargs)

    f_ares = f_add_result  # Abbreviation of the function


class DerivedParameterGroup(NNGroupNode):
    """Group node in your trajectory, hanging below `traj.derived_parameters`.

    You can add other groups or parameters to it.

    """

    __slots__ = ()

    def f_add_derived_parameter_group(self, *args, **kwargs):
        """Adds an empty derived parameter group under the current node.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is a single run (root) adds the prefix `'derived_parameters.runs.run_08%d%'`
        to the full name where `'08%d'` is replaced by the index of the current run.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        """

        return self._nn_interface._add_generic(self, type_name=DERIVED_PARAMETER_GROUP,
                                               group_type_name=DERIVED_PARAMETER_GROUP,
                                               args=args, kwargs=kwargs)

    def f_add_derived_parameter(self, *args, **kwargs):
        """Adds a derived parameter under the current group.

        Similar to
        :func:`~pypet.naturalnaming.ParameterGroup.f_add_parameter`

        Naming prefixes are added as in
        :func:`~pypet.naturalnaming.DerivedParameterGroup.f_add_derived_parameter_group`

        """
        return self._nn_interface._add_generic(self, type_name=DERIVED_PARAMETER,
                                               group_type_name=DERIVED_PARAMETER_GROUP,
                                               args=args, kwargs=kwargs)

    f_adpar = f_add_derived_parameter  # Abbreviation of the function


class ConfigGroup(NNGroupNode):
    """Group node in your trajectory, hanging below `traj.config`.

    You can add other groups or parameters to it.

    """

    __slots__ = ()

    def f_add_config_group(self, *args, **kwargs):
        """Adds an empty config group under the current node.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is the trajectory (root), the prefix `'config'` is added to the full name.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        """
        return self._nn_interface._add_generic(self, type_name=CONFIG_GROUP,
                                               group_type_name=CONFIG_GROUP,
                                               args=args, kwargs=kwargs)

    def f_add_config(self, *args, **kwargs):
        """Adds a config parameter under the current group.

        Similar to
        :func:`~pypet.naturalnaming.ParameterGroup.f_add_parameter`.

        If current group is the trajectory the prefix `'config'` is added to the name.

        """
        return self._nn_interface._add_generic(self, type_name=CONFIG,
                                               group_type_name=CONFIG_GROUP,
                                               args=args, kwargs=kwargs)

    f_aconf=f_add_config  # Abbreviation of the function
