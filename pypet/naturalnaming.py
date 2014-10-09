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
import re

from pypet.utils.decorators import deprecated
import pypet.pypetexceptions as pex
import pypet.compat as compat
import pypet.pypetconstants as pypetconstants
from pypet.annotations import WithAnnotations
from pypet.utils.helpful_classes import ChainMap
from pypet.utils.helpful_functions import is_debug
from pypet.pypetlogging import HasLogger, DisableLogger


# For fetching:
STORE = 'STORE'  # We want to store stuff with the storage service
LOAD = 'LOAD'  # We want to load stuff with the storage service
REMOVE = 'REMOVE'  # We want to remove stuff, potentially from disk


# Group Constants
RESULT = 'RESULT'
RESULT_GROUP = 'RESULTGROUP'
PARAMETER = 'PARAMETER'
PARAMETER_GROUP = 'PARAMETER_GROUP'
DERIVED_PARAMETER = 'DERIVED_PARAMETER'
DERIVED_PARAMETER_GROUP = 'DERIVED_PARAMETER_GROUP'
CONFIG = 'CONFIG'
CONFIG_GROUP = 'CONFIG_GROUP'
GROUP = 'GROUP'
LEAF = 'LEAF'

# Types are not allowed to be added during single runs
SENSITIVE_TYPES = set([PARAMETER, PARAMETER_GROUP, CONFIG, CONFIG_GROUP])

LENGTH_WARNING_THRESHOLD = 100

# SUBTREE Mapping
SUBTREE_MAPPING = {'config': (CONFIG_GROUP, CONFIG),
                   'parameters': (PARAMETER_GROUP, PARAMETER),
                   'derived_parameters': (DERIVED_PARAMETER_GROUP, DERIVED_PARAMETER),
                   'results': (RESULT_GROUP, RESULT)}

# For fast searching of nodes in the tree:
# If there are more candidate solutions found by the fast search
# (that need to be checked sequentially) than this number
# a slow search with a full tree traversal is initiated.
FAST_UPPER_BOUND = 2

SHORTCUT_SET = set(['crun', 'dpar', 'par', 'conf', 'res'])

CHECK_REGEXP = re.compile(r'^[A-Za-z0-9_-]+$')


class NNTreeNode(WithAnnotations):
    """ Abstract class to define the general node in the trajectory tree."""

    def __init__(self, full_name, comment, leaf):
        super(NNTreeNode, self).__init__()

        self._rename(full_name)

        self._leaf = leaf  # Whether or not a node is a leaf, aka terminal node.

        self._stored = False
        self._comment = ''
        self.v_comment = comment

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
    @deprecated(msg='Please use `v_is_leaf` instead.')
    def v_leaf(self):
        """Whether node is a leaf or not (i.e. it is a group node)

        DEPRECATED: Please use v_is_leaf!

        """
        return self.v_is_leaf

    @property
    def v_is_leaf(self):
        """Whether node is a leaf or not (i.e. it is a group node)"""
        return self._leaf

    @deprecated(msg='Please use property `v_is_root` instead.')
    def f_is_root(self):
        """Whether the group is root (True for the trajectory and a single run object)

        DEPRECATED: Please use property v_is_root!

        """
        return self.v_is_root

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
        """ Renames the parameter or result."""
        split_name = full_name.split('.')

        # The full name of root is '' (the empty string)
        if full_name != '':
            self._depth = len(split_name)
        else:
            self._depth = 0

        self._full_name = full_name
        self._name = split_name[-1]

        if self.v_is_root:
            self._branch = ''
        else:
            self._branch = split_name[0]

        # In case of results and derived parameters the creator can be a single run
        # parameters and configs are always created by the original trajectory
        self._run_branch = 'trajectory'
        self._run_branch_pos = -1  # Remembers at which position the branching occured
        # -1 if there is no branching
        if pypetconstants.RUN_NAME in full_name:
            head, tail = full_name.split(pypetconstants.RUN_NAME)
            self._run_branch_pos = head.count('.')
            branch = pypetconstants.RUN_NAME + tail.split('.')[0]
            if branch != pypetconstants.RUN_NAME_DUMMY:
                self._run_branch = branch

    def f_get_class_name(self):
        """ Returns the class name of the parameter or result or group.

        Equivalent to `obj.__class__.__name__`

        """
        return self.__class__.__name__


class NNLeafNode(NNTreeNode):
    """ Abstract class interface of result or parameter (see :mod:`pypet.parameter`)"""

    def __init__(self, full_name, comment, parameter):
        super(NNLeafNode, self).__init__(full_name=full_name, comment=comment, leaf=True)
        self._parameter = parameter

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

        self._run_or_traj_name = root_instance.v_name

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
        # a particular run (by setting the v_as_run property).
        self._nodes_and_leaves_runs_sorted = {}

        # List of names that are taboo. The user cannot create parameters or results that
        # contain these names.
        self._not_admissible_names = set(dir(self)) | set(dir(self._root_instance))

        # Context Manager to disable logging for auto-loading
        self._disable_logger = DisableLogger()


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

    def _change_root(self, new_root):
        """ Changes the root of the whole tree.

        This is called on creation of single runs to take over the tree from its parent
        trajectory and vice versa.

        """
        new_root._children = self._root_instance._children
        self._root_instance = new_root
        self._run_or_traj_name = self._root_instance.v_name

    def _get_backwards_search(self):
        return self._root_instance.v_backwards_search

    def _get_fast_access(self):
        return self._root_instance.v_fast_access

    def _get_shortcuts(self):
        return self._root_instance.v_shortcuts

    def _get_max_depth(self):
        return self._root_instance.v_max_depth

    def _get_iter_recursive(self):
        return self._root_instance.v_iter_recursive

    def _get_auto_load(self):
        return self._root_instance.v_auto_load

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
        if not isinstance(name, compat.base_type):
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

            # Explored Parameters cannot be removed, this would break the underlying hdf5 file
            # structure
            if (msg == pypetconstants.DELETE and
                        item.v_full_name in self._root_instance._explored_parameters):
                raise TypeError('You cannot remove an explored parameter of a trajectory stored '
                                'into an hdf5 file.')

            item_list.append(item_tuple)

        return item_list

    def _remove_subtree(self, start_node, name):
        """Removes a subtree from the trajectory tree.

        Does not delete stuff from disk only from RAM.

        :param start_node: The parent node from where to start
        :param name: Name of child which will be deleted and recursively all nodes below the child

        """

        def _remove_subtree_inner(node):

            if not node.v_is_leaf:
                for name_ in compat.listkeys(node._children):
                    child_ = node._children[name_]
                    _remove_subtree_inner(child_)
                    del node._children[name_]
                    del child_

            self._delete_node(node)

        child = start_node._children[name]

        _remove_subtree_inner(child)
        del start_node._children[name]

    def _delete_node(self, node):
        """Deletes a single node from the tree.

        Removes all references to the node.

        Note that the 'parameters', 'results', 'derived_parameters', and 'config' groups
        hanging directly below root cannot be deleted. Also the root node itself cannot be
        deleted. (This would cause a tremendous wave of uncontrollable self destruction, which
        would finally lead to the Apocalypse!)

        """
        full_name = node.v_full_name
        name = node.v_name
        run_name = node.v_run_branch

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

            if full_name in root._run_parent_groups:
                del root._run_parent_groups[full_name]

            if full_name in root._explored_parameters:
                del root._explored_parameters[full_name]

                # If we remove an explored parameter and the trajectory was not stored to disk
                # before we need to check if there are no explored parameters left. If so
                # the length of the trajectory is shrunk to 1.
                if len(root._explored_parameters) == 0:
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

    def _remove_recursive(self, actual_node, split_name, remove_empty_groups):
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
        if len(split_name) == 0:
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

    def _translate_into_shortcut(self, name):
        """Maps a given shortcut to corresponding name

        * 'run_X' or 'r_X' to 'run_XXXXXXXXX'

        * 'crun' to the current run name in case of a
          single run instance if trajectory is used via `v_as_run`

        * 'par' 'parameters'

        * 'dpar' to 'derived_parameters'

        * 'res' to 'results'

        * 'conf' to 'config'

        :return: The mapped name or None if no shortcut is matched.

        """

        if name == -1:
            return pypetconstants.RUN_NAME_DUMMY
        elif name == -2:
            if self._root_instance._as_run != pypetconstants.RUN_NAME_DUMMY:
                return '$'
            else:
                return pypetconstants.RUN_NAME_DUMMY
        elif isinstance(name, int):
            return pypetconstants.FORMATTED_RUN_NAME % name

        if name.startswith('r'):
            if name.startswith('run_') or name.startswith('r_'):
                split_name = name.split('_')
                if len(split_name) == 2:
                    index = split_name[1]
                    if index.isdigit():
                        if len(index) < pypetconstants.FORMAT_ZEROS:
                            return pypetconstants.FORMATTED_RUN_NAME % int(index)

        if name in SHORTCUT_SET:
            if name == 'crun':
                if self._root_instance._as_run != pypetconstants.RUN_NAME_DUMMY:
                    return '$'
                else:
                    return pypetconstants.RUN_NAME_DUMMY

            if name == 'par':
                return 'parameters'

            if name == 'dpar':
                return 'derived_parameters'

            if name == 'res':
                return 'results'

            if name == 'conf':
                return 'config'

        return None

    def _add_prefix(self, name, start_node, group_type_name):
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

        add = ''

        if start_node.v_depth < 3 and not group_type_name == GROUP:
            if start_node.v_depth == 0:

                if group_type_name == DERIVED_PARAMETER_GROUP:
                    if name == 'derived_parameters' or name.startswith('derived_parameters.'):
                        return name
                    else:
                        add += 'derived_parameters.'

                elif group_type_name == RESULT_GROUP:
                    if name == 'results' or name.startswith('results.'):
                        return name
                    else:
                        add += 'results.'

                elif group_type_name == CONFIG_GROUP:
                    if name == 'config' or name.startswith('config.'):
                        return name
                    else:
                        add += 'config.'

                elif group_type_name == PARAMETER_GROUP:
                    if name == 'parameters' or name.startswith('parameters.'):
                        return name
                    else:
                        add += 'parameters.'
                else:
                    raise RuntimeError('Why are you here?')

            # Check if we have to add
            if ('.$.' in name or name.startswith('$.') or name.endswith('.$') or name == '$' or
                            '.' + pypetconstants.RUN_NAME in name or
                    name.startswith(pypetconstants.RUN_NAME)):
                pass

            elif name and (root._is_run and (group_type_name == RESULT_GROUP or
                                                     group_type_name == DERIVED_PARAMETER_GROUP)):

                if start_node.v_depth == 0:
                    add = add + 'runs.' + root.v_name + '.'

                elif start_node.v_depth == 1:

                    if name == 'runs':
                        return name
                    else:
                        add = add + 'runs.' + root.v_name + '.'

                elif start_node.v_depth == 2 and start_node.v_name == 'runs':
                    add += root.v_name + '.'

        name = add + name

        return name

    @staticmethod
    def _determine_types(start_node, name, add_leaf):
        """Determines types for generic additions"""
        if start_node.v_is_root:
            where = name.split('.')[0]
            if where == 'overview':
                raise ValueError(
                    'Sorry, you are not allowed to have an `overview` subtree directly under '
                    'the root node.')
        else:
            where = start_node._branch

        if where in SUBTREE_MAPPING:
            type_tuple = SUBTREE_MAPPING[where]
        else:
            type_tuple = (GROUP, LEAF)

        if add_leaf:
            return type_tuple
        else:
            return type_tuple[0], type_tuple[0]

    def _add_generic(self, start_node, type_name, group_type_name, args, kwargs, add_prefix=True):
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
            args = list(args)
            name = args.pop(0)
            instance = None
            constructor = None

            if group_type_name == GROUP:
                group_type_name, type_name = self._determine_types(start_node, name, False)

        else:
            # # We add a leaf node in the end:
            args = list(args)

            create_new = True
            name = ''
            instance = None
            constructor = None

            # First check if the item is already a given instance
            if len(args) == 1 and len(kwargs) == 0:
                item = args[0]
                try:
                    name = item.v_full_name
                    instance = item
                    # constructor = None

                    create_new = False
                except AttributeError:
                    pass

            # If the item is not an instance yet, check if args[0] is a class and args[1] is
            # a string describing the new name of the instance.
            # If args[0] is not a class it is assumed to be the name of the new instance.
            if create_new:
                if inspect.isclass(args[0]):
                    constructor = args.pop(0)
                    # else:
                # constructor = None

                # instance = None

                name = args.pop(0)

            if group_type_name == GROUP:
                group_type_name, type_name = self._determine_types(start_node, name, True)

        # Check if we are allowed to add the data
        if self._root_instance._is_run and type_name in SENSITIVE_TYPES:
            raise TypeError('You are not allowed to add config or parameter data or groups '
                            'during a single run.')

        # Check if the name fulfils the prefix conditions, if not change the name accordingly.
        if add_prefix:
            name = self._add_prefix(name, start_node, group_type_name)

        name = self._replace_wildcards(name)

        return self._add_to_tree(start_node, name, type_name, group_type_name, instance,
                                 constructor, args, kwargs)

    def _replace_wildcards(self, name):
        """Replaces the $ wildcards"""
        if self._root_instance._is_run:
            name = name.replace('$', self._root_instance.v_name)
        else:
            name = name.replace('$', pypetconstants.RUN_NAME_DUMMY)

        return name

    def _add_to_tree(self, start_node, name, type_name, group_type_name,
                     instance, constructor, args, kwargs):
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

        faulty_names = self._check_names(split_name, start_node)

        if faulty_names:
            raise ValueError(
                'Your Parameter/Result/Node `%s` contains the following not admissible names: '
                '%s please choose other names.'
                % (name, faulty_names))

        # Then walk iteratively from the start node as specified by the new name and create
        # new empty groups on the fly
        try:
            act_node = start_node
            last_idx = len(split_name) - 1
            # last_name = start_node.v_name
            for idx, name in enumerate(split_name):

                if not name in act_node._children:

                    if idx == last_idx and group_type_name != type_name:
                        # We are at the end of the chain and we add a leaf node

                        new_node = self._create_any_param_or_result(act_node.v_full_name, name,
                                                                    type_name, instance,
                                                                    constructor,
                                                                    args, kwargs)

                        self._flat_leaf_storage_dict[new_node.v_full_name] = new_node

                    else:
                        # We add a group node, can also be intermediate on the fly
                        if idx == last_idx:
                            # We add a group as desired
                            new_node = self._create_any_group(act_node.v_full_name, name,
                                                              group_type_name, args, kwargs)
                        else:
                            # We add a group on the fly
                            new_node = self._create_any_group(act_node.v_full_name, name,
                                                              group_type_name)

                    act_node._children[name] = new_node

                    # Add the new instance also to the nested reference dictionaries
                    # to allow fast search
                    if not name in self._nodes_and_leaves:
                        self._nodes_and_leaves[name] = {new_node.v_full_name: new_node}
                    else:
                        self._nodes_and_leaves[name][new_node.v_full_name] = new_node

                    run_name = new_node._run_branch
                    if not name in self._nodes_and_leaves_runs_sorted:
                        self._nodes_and_leaves_runs_sorted[name] = {run_name:
                                                                        {new_node.v_full_name:
                                                                             new_node}}
                    else:
                        if not run_name in self._nodes_and_leaves_runs_sorted[name]:
                            self._nodes_and_leaves_runs_sorted[name][run_name] = \
                                {new_node.v_full_name: new_node}
                        else:
                            self._nodes_and_leaves_runs_sorted[name][run_name]\
                                [new_node.v_full_name] = new_node

                    if (name.startswith(pypetconstants.RUN_NAME) and
                                name != pypetconstants.RUN_NAME_DUMMY):
                        self._root_instance._run_parent_groups[act_node.v_full_name] = act_node

                else:
                    if idx == last_idx:
                        raise AttributeError('You already have a group/instance `%s` under '
                                             '`%s`' % (name, act_node.v_full_name))

                act_node = act_node._children[name]
                # last_name = name

            return act_node
        except:
            self._logger.error('Failed adding `%s` under `%s`.' %
                               (name, start_node.v_full_name))
            raise

    def _check_names(self, split_names, parent_node=None):
        """Checks if a list contains strings with invalid names.

        Returns a description of the name violations. If names are correct the empty
        string is returned.

        :param split_names: List of strings

        :param parent_node:

            The parental node from where to start (only applicable for node names)

        """

        if parent_node is None:
            parent_length = 0
            parent_run_count = 0
        else:
            parent_length = len(parent_node.v_full_name)
            parent_run_count = int(parent_node._run_branch_pos >= 0)

        faulty_names = ''

        for split_name in split_names:

            if re.match(CHECK_REGEXP, split_name) is None:
                faulty_names = '%s `%s` contains non-admissible characters ' \
                               '(use only [A-Za-z0-9_-]),' % \
                               (faulty_names, split_name)

            if split_name in self._not_admissible_names:
                faulty_names = '%s `%s` is a method/attribute of the ' \
                               'trajectory/treenode/naminginterface,' % \
                               (faulty_names, split_name)

            if split_name[0] == '_':
                faulty_names = '%s `%s` starts with a leading underscore,' % (
                    faulty_names, split_name)

            # if ' ' in split_name:
            # faulty_names = '%s `%s` contains white space(s),' % (faulty_names, split_name)

            if not self._translate_into_shortcut(split_name) is None:
                faulty_names = '%s `%s` is already an important shortcut,' % (
                    faulty_names, split_name)

        name = split_names[-1]
        location = '.'.join(split_names[:-1])
        if len(name) >= pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH:
            faulty_names = '%s `%s` is too long the name can only have %d characters but it has ' \
                           '%d,' % \
                           (faulty_names, name, len(name),
                            pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH)

        if parent_length + len(location) >= pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH:
            faulty_names = '%s `%s` is too long the location can only have ' \
                           '%d characters but it has %d,' % \
                           (faulty_names, location, len(location),
                            pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH)

        if (parent_run_count + int(name.startswith(pypetconstants.RUN_NAME)) +
                int(location.startswith(pypetconstants.RUN_NAME)) +
                location.count('.' + pypetconstants.RUN_NAME) > 1):
            faulty_names = '%s `%s` contains a more than one branch with ' \
                           'a run name starting with ' \
                           '`%s`,' % (faulty_names,
                                      parent_node.v_full_name + '.' + '.'.join(split_names),
                                      pypetconstants.RUN_NAME)
        return faulty_names

    def _create_any_group(self, location, name, type_name, args=None, kwargs=None):
        """Generically creates a new group inferring from the `type_name`."""
        if location:
            full_name = '%s.%s' % (location, name)
        else:
            full_name = name

        if args is None:
            args = []

        if kwargs is None:
            kwargs = {}

        if type_name == RESULT_GROUP:
            instance = ResultGroup(self, full_name, *args, **kwargs)

        elif type_name == PARAMETER_GROUP:
            instance = ParameterGroup(self, full_name, *args, **kwargs)

        elif type_name == CONFIG_GROUP:
            instance = ConfigGroup(self, full_name, *args, **kwargs)

        elif type_name == DERIVED_PARAMETER_GROUP:
            instance = DerivedParameterGroup(self, full_name, *args, **kwargs)
        elif type_name == GROUP:
            instance = NNGroupNode(self, full_name, *args, **kwargs)
        else:
            raise RuntimeError('You shall not pass!')

        self._root_instance._groups[instance.v_full_name] = instance

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
                    constructor = root._standard_result
                elif type_name in [PARAMETER, CONFIG, DERIVED_PARAMETER]:
                    constructor = root._standard_parameter
                else:
                    constructor = root._standard_leaf

            instance = constructor(full_name, *args, **kwargs)
        else:
            instance._rename(full_name)

        where_dict = self._map_type_to_dict(type_name)

        if full_name in where_dict:
            raise AttributeError(full_name + ' is already part of trajectory,')

        if type_name != RESULT:
            if full_name in root._changed_default_parameters:
                self._logger.info(
                    'You have marked parameter %s for change before, so here you go!' %
                    full_name)

                change_args, change_kwargs = root._changed_default_parameters.pop(full_name)
                instance.f_set(*change_args, **change_kwargs)

        where_dict[full_name] = instance

        self._logger.debug('Added `%s` to trajectory.' % full_name)

        return instance

    @staticmethod
    def _apply_fast_access(data, fast_access):
        """Method that checks if fast access is possible and applies it if desired"""
        if fast_access and data.f_supports_fast_access():
            return data.f_get()
        else:
            return data


    def _iter_nodes(self, node, recursive=False, total_depth=float('inf')):
        """Returns an iterator over nodes hanging below a given start node.

        :param node:

            Start node

        :param recursive:

            Whether recursively also iterate over the children of the start node's children


        :param max_depth:

            Maximum depth to search for

        :return: Iterator

        """
        as_run = self._get_as_run()

        if recursive:
            return NaturalNamingInterface._recursive_traversal_bfs(node, as_run, total_depth)
        else:
            return compat.itervalues(node._children)


    @staticmethod
    def _iter_leaves(node):
        """ Iterates over all leaves hanging below `node`."""
        for node in node.f_iter_nodes(recursive=True):
            if node.v_is_leaf:
                yield node
            else:
                continue

    def _to_dict(self, node, fast_access=True, short_names=False, copy=True):
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

        if (fast_access or short_names) and not copy:
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
                iterator = compat.itervalues(temp_dict)
        else:
            iterator = self._iter_leaves(node)

        # If not we need to build the dict by iterating recursively over all leaves:
        result_dict = {}
        for val in iterator:
            if short_names:
                new_key = val.v_name
            else:
                new_key = val.v_full_name

            if new_key in result_dict:
                raise ValueError('Your short names are not unique. Duplicate key `%s`!' % new_key)

            new_val = self._apply_fast_access(val, fast_access)
            result_dict[new_key] = new_val

        return result_dict

    @staticmethod
    def _make_child_iterator(node, run_name):
        """Returns an iterator over a node's children.

        In case of using a trajectory as a run (setting 'v_as_run') some sub branches
        that do not belong to the run are blinded out.

        """
        if run_name != pypetconstants.RUN_NAME_DUMMY and run_name in node._children:
            # Only consider one particular run and blind out the rest, but include
            # all other subbranches
            node_list = [node._children[run_name]]
            for child_name in node._children:
                if not (child_name.startswith(pypetconstants.RUN_NAME)
                        and child_name != pypetconstants.RUN_NAME_DUMMY):
                    node_list.append(node._children[child_name])
            return node_list
        else:
            return compat.itervalues(node._children)

    @staticmethod
    def _recursive_traversal_bfs(node, run_name=None, total_depth=float('inf')):
        """Iterator function traversing the tree below `node` in breadth first search manner.

        If `run_name` is given only sub branches of this run are considered and the rest is
        blinded out.

        """
        queue = iter([node])
        start = True

        while True:
            try:
                item = next(queue)
                if start:
                    start = False
                else:
                    yield item

                if not item._leaf and item._depth < total_depth:
                    queue = itools.chain(queue,
                                         NaturalNamingInterface._make_child_iterator(item,
                                                                                     run_name))
            except StopIteration:
                break


    # @staticmethod
    # def _recursive_traversal_dfs(node, run_name=None, total_depth=float('inf')):
    # """Iterator function traversing the tree below `node` in depth first search manner.
    #
    # If `run_name` is given only sub branches of this run are considered and the rest is
    # blinded out.
    #
    # """
    # if not node._leaf and node._depth < total_depth:
    # for child in NaturalNamingInterface._make_child_iterator(node, run_name):
    # yield child
    # for new_node in NaturalNamingInterface._recursive_traversal_dfs(child, run_name):
    # yield new_node

    def _get_candidate_dict(self, key, as_run, use_upper_bound=True):
        # First find all nodes where the key matches the (short) name of the node
        if as_run == pypetconstants.RUN_NAME_DUMMY:
            return self._nodes_and_leaves[key]
        else:
            temp_dict = {}
            if as_run in self._nodes_and_leaves_runs_sorted[key]:
                temp_dict = self._nodes_and_leaves_runs_sorted[key][as_run]
                if use_upper_bound and len(temp_dict) > FAST_UPPER_BOUND:
                    raise pex.TooManyGroupsError('Too many nodes')

            temp_dict2 = {}
            if 'trajectory' in self._nodes_and_leaves_runs_sorted[key]:
                temp_dict2 = self._nodes_and_leaves_runs_sorted[key]['trajectory']
                if use_upper_bound and len(temp_dict2) > FAST_UPPER_BOUND:
                    raise pex.TooManyGroupsError('Too many nodes')

            return ChainMap(temp_dict, temp_dict2)

    def _get_as_run(self):
        """ Returns the run name in case of 'v_as_run' is set, otherwise None."""
        return self._root_instance._as_run

    def _very_fast_search(self, node, key, as_run, total_depth=float('inf')):
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

        candidate_dict = self._get_candidate_dict(key, as_run)

        # If there are to many potential candidates sequential search might be too slow
        if len(candidate_dict) > FAST_UPPER_BOUND:
            raise pex.TooManyGroupsError('Too many nodes')

        # Next check if the found candidates could be reached from the parent node
        result_node = None
        for goal_name in candidate_dict:

            if goal_name.startswith(parent_full_name):

                # In case of several solutions raise an error:
                if not result_node is None:
                    raise pex.NotUniqueNodeError('Node `%s` has been found more than once,'
                                                 'full name of first occurrence is `%s` and of'
                                                 'second `%s`'
                                                 % (key, goal_name, result_node.v_full_name))

                candidate = candidate_dict[goal_name]
                if candidate._depth <= total_depth:
                    result_node = candidate_dict[goal_name]

        return result_node

    def _search(self, node, key, max_depth=float('inf')):
        """ Searches for an item in the tree below `node`

        :param node:

            The parent node below which the search is performed

        :param key:

            Name to search for. Can be the short name, the full name or parts of it

        :param max_depth:

            maximum search depth.

        :return: The found node

        """
        as_run = self._get_as_run()

        total_depth = node._depth + max_depth

        # First the very fast search is tried that does not need tree traversal.
        try:
            return self._very_fast_search(node, key, as_run, total_depth)
        except pex.TooManyGroupsError:
            pass
        except pex.NotUniqueNodeError:
            pass

        # Slowly traverse the entire tree
        nodes_iterator = self._iter_nodes(node, recursive=True,
                                          total_depth=total_depth)
        result_node = None
        result_depth = float('inf')
        for child in nodes_iterator:

            if child._depth > result_depth:
                # We can break here because we enter a deeper stage of the tree and we
                # cannot find matching node of the same depth as the one we found
                break

            if key == child._name:

                # If result_node is not None means that we care about uniqueness and the search
                # has found more than a single solution.
                if result_node is not None:
                    raise pex.NotUniqueNodeError('Node `%s` has been found more than once within '
                                                 'the same depth %d.'
                                                 'Full name of first occurrence is `%s` and of '
                                                 'second `%s`'
                                                 % (key, child.v_depth, result_node.v_full_name,
                                                    child.v_full_name))

                result_node = child
                result_depth = result_node._depth

        return result_node

    def _backwards_search(self, start_node, split_name, max_depth=float('inf')):
        """ Performs a backwards search from the terminal node back to the start node

        :param start_node:

            The node from where search starts, or here better way where backwards search should
            end.

        :param split_name:

            List of node names that must exist on the path from split_name[-1] back to start node.

        :param max_depth:

            Maximum search depth where to look for

        :return:
        """

        result_list = []
        as_run = self._get_as_run()
        key = split_name[-1]
        candidate_dict = self._get_candidate_dict(key, as_run, use_upper_bound=False)
        parent_full_name = start_node.v_full_name

        split_length = len(split_name)

        if len(candidate_dict) > LENGTH_WARNING_THRESHOLD:
            self._logger.warning('Backwards search found more than %d possible candidates'
                                 '(it found %d potential terminal nodes for `%s`). '
                                 'Better use forward search and try to avoid '
                                 'shortcuts for faster performance.' %
                                 (LENGTH_WARNING_THRESHOLD, len(candidate_dict), key))

        for candidate_name in candidate_dict:

            # Check if candidate startswith the parent's name
            if candidate_name.startswith(parent_full_name):
                if parent_full_name != '':
                    reduced_candidate_name = candidate_name[len(parent_full_name) + 1:]
                else:
                    reduced_candidate_name = candidate_name

                candidate_split_name = reduced_candidate_name.split('.')

                if len(candidate_split_name) > max_depth:
                    break

                if len(split_name) == 1:
                    result_list.append(candidate_dict[candidate_name])
                else:

                    candidate_set = set(candidate_split_name)
                    climbing = True
                    for name in split_name:
                        if not name in candidate_set:
                            climbing = False
                            break

                    if climbing:
                        count = 0
                        candidate_length = len(candidate_split_name)
                        for idx in compat.xrange(candidate_length):

                            if idx + split_length - count > candidate_length:
                                break

                            if split_name[count] == candidate_split_name[idx]:
                                count += 1
                                if count == len(split_name):
                                    result_list.append(candidate_dict[candidate_name])
                                    break

        return result_list

    def _get_all(self, node, name, max_depth):
        """ Searches for all occurrences of `name` under `node`.

        :param node:

            Start node

        :param name:

            Name what to look for can be longer and separated by colons, i.e.
            `mygroupA.mygroupB.myparam`.

        :param max_depth:

            Maximum depth to search for relative to start node.

        :return:

            List of nodes that match the name, empty list if nothing was found.

        """

        if max_depth is None:
            max_depth = float('inf')

        return self._backwards_search(node, name.split('.'), max_depth)

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

        if new_name in self._root_instance._groups:
            return self._root_instance._groups[new_name]

        return None

    def _get(self, node, name, fast_access, backwards_search,
             shortcuts, max_depth, auto_load):
        """Searches for an item (parameter/result/group node) with the given `name`.

        :param node: The node below which the search is performed

        :param name: Name of the item (full name or parts of the full name)

        :param fast_access: If the result is a parameter, whether fast access should be applied.


        :param backwards_search:

            If the tree should be searched backwards in case more than one name/location is given.
            For instance, `groupA,groupC,valD` can be used for backwards search.
            The starting group will look for `valD` first and try to find a way back
            and check if it passes by `groupA` and `groupC`.

        :param max_depth:

            Maximum search depth relative to start node.

        :param auto_load:

            If data should be automatically loaded

        :return:

            The found instance (result/parameter/group node) or if fast access is True and you
            found a parameter or result that supports fast access, the contained value is returned.

        :raises:

            AttributeError if no node with the given name can be found.
            Raises errors that are raised by the storage service if `auto_load=True` and
            item cannot be found.

        """
        if isinstance(name, (tuple, list)):
            split_name = name
        elif isinstance(name, int):
            split_name = [name]
        else:
            split_name = name.split('.')

        if max_depth is None:
            max_depth = float('inf')

        if len(split_name) > max_depth and shortcuts:
            raise ValueError(
                'Name of node to search for (%s) is longer thant the maximum depth %d' %
                (str(name), max_depth))

        try_auto_load_directly1 = False
        try_auto_load_directly2 = False
        wildcard_pos = -1

        # # Rename shortcuts and check keys:
        for idx, key in enumerate(split_name):
            translated_shortcut = self._translate_into_shortcut(key)
            if translated_shortcut:
                key = translated_shortcut
                split_name[idx] = key

            if key[0] == '_':
                raise AttributeError('Leading underscores are not allowed for group or parameter '
                                     'names. Cannot return %s.' % key)

            if not key in self._nodes_and_leaves and key != '$':
                try_auto_load_directly1 = True
                try_auto_load_directly2 = True

            if key == '$':
                wildcard_pos = idx
                if self._root_instance._as_run not in self._nodes_and_leaves:
                    try_auto_load_directly1 = True
                if pypetconstants.RUN_NAME_DUMMY not in self._nodes_and_leaves:
                    try_auto_load_directly2 = True

        if try_auto_load_directly1 and try_auto_load_directly2 and not auto_load:
            raise AttributeError('%s is not part of your trajectory or it\'s tree.' %
                                 str(name))

        if wildcard_pos > -1:
            # If we count the wildcard we have to perform the search twice,
            # one with a run name and one with the dummy:

            with self._disable_logger:
                try:
                    as_run = self._root_instance._as_run
                    if as_run == pypetconstants.RUN_NAME_DUMMY:
                        # If our trajectory is not set to a particular run we can skip this part
                        raise AttributeError
                    split_name[wildcard_pos] = as_run
                    result = self._perform_get(node, split_name, fast_access, backwards_search,
                                               shortcuts, max_depth, auto_load,
                                               try_auto_load_directly1)
                    return result
                except (pex.DataNotInStorageError, AttributeError):
                    split_name[wildcard_pos] = pypetconstants.RUN_NAME_DUMMY

        return self._perform_get(node, split_name, fast_access, backwards_search,
                                 shortcuts, max_depth, auto_load, try_auto_load_directly2)

    def _perform_get(self, node, split_name, fast_access, backwards_search,
                     shortcuts, max_depth, auto_load, try_auto_load_directly):
        """Searches for an item (parameter/result/group node) with the given `name`.

        :param node: The node below which the search is performed

        :param split_name: Name split into list according to '.'

        :param fast_access: If the result is a parameter, whether fast access should be applied.

        :param backwards_search:

            If the tree should be searched backwards in case more than one name/location is given.
            For instance, `groupA,groupC,valD` can be used for backwards search.
            The starting group will look for `valD` first and try to find a way back
            and check if it passes by `groupA` and `groupC`.

        :param max_depth:

            Maximum search depth relative to start node.

        :param auto_load:

            If data should be automatically loaded

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

        if shortcuts and not try_auto_load_directly:
            first = split_name[0]

            if len(split_name) == 1 and first in node._children:
                result = node._children[first]
            else:

                result = self._check_flat_dicts(node, split_name)

                if result is None:

                    if backwards_search and len(split_name) > 1:
                        # # Do backwards search if we have a colon separated name
                        result_list = self._backwards_search(node, split_name, max_depth)

                        if len(result_list) == 0:
                            result = None
                        elif len(result_list) == 1:
                            result = result_list.pop()
                        else:
                            raise pex.NotUniqueNodeError(
                                'Node `%s` has been found more than once. '
                                'Full name of first occurrence is `%s` '
                                'and of '
                                'another `%s`. In total there are %d '
                                'occurrences.'
                                % (name, result_list[0].v_full_name,
                                   result_list[1].v_full_name, len(result_list)))
                    else:

                        # Check in O(N) with `N` number of groups and nodes
                        # [Worst Case O(N), average case is better
                        # since looking into a single dict costs O(1)].
                        result = node
                        for key in split_name:
                            result = self._search(result, key, max_depth)
                            if result is None:
                                break
        elif not try_auto_load_directly:
            result = node
            for name in split_name:
                if not name in result._children:
                    raise AttributeError(
                        'You did not allow for shortcuts and `%s` was not directly '
                        'found  under node `%s`.' % (name, result.v_full_name))
                result = result._children[name]

        if result is None and auto_load:
            try:
                result = node.f_load_child('.'.join(split_name),
                                           load_data=pypetconstants.LOAD_DATA)
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
                except:
                    self._logger.error('Error while auto-loading `%s` under `%s`. I found the '
                                       'item but I could not load the data.' %
                                       (name, node.v_full_name))
                    raise

            return self._apply_fast_access(result, fast_access)
        else:
            return result


class NNGroupNode(NNTreeNode):
    """A group node hanging somewhere under the trajectory or single run root node.

    You can add other groups or parameters/results to it.

    """

    def __init__(self, nn_interface=None, full_name='', comment=''):
        super(NNGroupNode, self).__init__(full_name, comment=comment, leaf=False)
        self._children = {}
        self._nn_interface = nn_interface

    def __str__(self):
        if not self.v_is_root:
            name = self.v_full_name
        else:
            name = self.v_name

        return '<%s>: %s: %s' % (self.f_get_class_name(), name,
                                 str([(key, str(type(self._children[key])))
                                      for key in self._children]))

    def __dir__(self):
        """Adds all children to auto-completion"""
        result = dir(type(self)) + compat.listkeys(self.__dict__)
        if not is_debug():
            result.extend(self._children.keys())
        return result

    def __iter__(self):
        """Equivalent to call :func:`~pypet.naturalnaming.NNGroupNode.f_iter_nodes`

        Whether to iterate recursively is determined by `v_iter_recursive`.

        """
        return self.f_iter_nodes(recursive=self._nn_interface._get_iter_recursive())

    def _debug(self):
        """Creates a dummy object containing the whole tree to make unfolding easier.

        This method is only useful for debugging purposes.
        If you use an IDE and want to unfold the trajectory tree, you always need to
        open the private attribute `_children`. Use to this function to create a new
        object that contains the tree structure in its attributes.

        Manipulating the returned object does not change the original tree!

        """

        class Bunch:
            def __init__(self, **kwds):
                self.__dict__.update(kwds)

        debug_tree = Bunch()
        if not self.v_annotations.f_is_empty():
            debug_tree.v_annotations = self.v_annotations
        if not self.v_comment == '':
            debug_tree.v_comment = self.v_comment
        for child_name in self._children:
            child = self._children[child_name]
            if child.v_is_leaf:
                setattr(debug_tree, child_name, child)
            else:
                setattr(debug_tree, child_name, child._debug())

        return debug_tree

    def f_add_group(self, name, comment=''):
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
                                               args=(name, comment), kwargs={}, add_prefix=False)

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
                                               args=args, kwargs=kwargs)

    def f_children(self):
        """Returns the number of children of the group"""
        return len(self._children)

    def f_has_children(self):
        """Checks if node has children or not"""
        return len(self._children) != 0

    def __contains__(self, item):
        """Equivalent to calling :func:`~pypet.naturalnaming.NNGroupNode.f_contains`.

        Whether to allow shortcuts is taken from `v_shortcuts`.
        Whether to stop at a given depth is taken from `v_max_depth`.

        """
        return self.f_contains(item,
                               backwards_search=self._nn_interface._get_backwards_search(),
                               shortcuts=self._nn_interface._get_shortcuts(),
                               max_depth=self._nn_interface._get_max_depth())

    def f_remove_child(self, name, recursive=False):
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

        :raises:

            TypeError if recursive is false but there are children below the node.

            ValueError if child does not exist.

        """
        if not name in self._children:
            raise ValueError('Your group `%s` does not contain the child `%s`.' %
                             (self.v_full_name, name))

        else:
            child = self._children[name]

            if not child.v_is_leaf and child.f_has_children and not recursive:
                raise TypeError('Cannot remove child. It is a group with children. Use'
                                ' f_remove with >>recursive = True')
            else:
                self._nn_interface._remove_subtree(self, name)

    def f_contains(self, item, backwards_search=False,
                   shortcuts=False, max_depth=None):
        """Checks if the node contains a specific parameter or result.

        It is checked if the item can be found via the
        :func:`~pypet.naturalnaming.NNGroupNode.f_get` method.

        :param item: Parameter/Result name or instance.

            If a parameter or result instance is supplied it is also checked if
            the provided item and the found item are exactly the same instance, i.e.
            `id(item)==id(found_item)`.

        :param backwards_search:

            If backwards search should be allowed in case the name contains grouping.

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

        except AttributeError:
            search_string = item
            item = None

        try:
            result = self.f_get(search_string, backwards_search=backwards_search,
                                shortcuts=shortcuts, max_depth=max_depth)
        except AttributeError:
            return False

        if item is not None:
            return id(item) == id(result)
        else:
            return True

    def __setattr__(self, key, value):
        if key.startswith('_'):
            # We set a private item
            self.__dict__[key] = value
        elif hasattr(self.__class__, key):
            # If we set a property we need this work around here:
            python_property = getattr(self.__class__, key)
            if python_property.fset is None:
                raise AttributeError('%s is read only!' % key)
            else:
                python_property.fset(self, value)
        else:
            # Otherwise we will set a value to an existing parameter.
            # Only works if the parameter exists. There is no new parameter created!
            instance = self.f_get(key)

            if not instance.v_is_parameter:
                raise AttributeError('You cannot assign values to a tree node or a list of nodes '
                                     'and results, it only works for parameters ')

            instance.f_set(value)

    def __getitem__(self, item):
        """Equivalent to calling `__getattr__`.

        Per default the item is returned and fast access is applied.

        """
        return self.__getattr__(item)

    def __getattr__(self, name):
        if isinstance(name, compat.base_type) and name.startswith('_'):
            raise AttributeError('Trajectory node does not contain `%s`' % name)

        if not '_nn_interface' in self.__dict__:
            raise AttributeError('This is to avoid pickling issues')

        return self._nn_interface._get(self, name,
                                       fast_access=self._nn_interface._get_fast_access(),
                                       backwards_search=self._nn_interface._get_backwards_search(),
                                       shortcuts=self._nn_interface._get_shortcuts(),
                                       max_depth=self._nn_interface._get_max_depth(),
                                       auto_load=self._nn_interface._get_auto_load())

    def f_get_root(self):
        """Returns the root node of the tree.

        Either a full trajectory or a single run container.

        """
        return self._nn_interface._root_instance

    def f_iter_nodes(self, recursive=True):
        """Iterates recursively (default) over nodes hanging below this group.

        :param recursive: Whether to iterate the whole sub tree or only immediate children.

        :return: Iterator over nodes

        """
        return self._nn_interface._iter_nodes(self, recursive=recursive)

    def f_iter_leaves(self):
        """Iterates (recursively) over all leaves hanging below the current group."""
        return self._nn_interface._iter_leaves(self)

    def f_get_all(self, name, max_depth=None):
        """ Searches for all occurrences of `name` under `node`.

        :param node:

            Start node

        :param name:

            Name of what to look for, can be separated by colons, i.e.
            `mygroupA.mygroupB.myparam`.

        :param max_depth:

            Maximum search depth relative to start node.
            `None` for no limit.

        :return:

            List of nodes that match the name, empty list if nothing was found.

        """
        return self._nn_interface._get_all(self, name, max_depth=max_depth)

    def f_get(self, name, fast_access=False, backwards_search=False,
              shortcuts=True, max_depth=None, auto_load=False):
        """Searches and returns an item (parameter/result/group node) with the given `name`.

        :param name: Name of the item (full name or parts of the full name)

        :param fast_access: Whether fast access should be applied.


        :param backwards_search:

            If the tree should be searched backwards in case more than one name/location is given.
            For instance, `groupA,groupC,valD` can be used for backwards search.
            The starting group will look for `valD` first and try to find a way back
            and check if it passes by `groupA` and `groupC`.


        :param shortcuts:

            If shortcuts are allowed and the trajectory can *hop* over nodes in the
            path.

        :param max_depth:

            Maximum depth (relative to start node) how search should progress in tree.
            `None` means no depth limit.  Only relevant if `shortcuts` are allowed.

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

            Any exception raised by the StorageService in case auto-loading is enabled




        """
        return self._nn_interface._get(self, name, fast_access=fast_access,
                                       backwards_search=backwards_search,
                                       shortcuts=shortcuts,
                                       max_depth=max_depth,
                                       auto_load=auto_load)

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

    def f_to_dict(self, fast_access=False, short_names=False):
        """Returns a dictionary with pairings of (full) names as keys and instances as values.

        :param fast_access:

            If True parameter or result values are returned instead of the instances.

        :param short_names:

            If true keys are not full names but only the names. Raises a ValueError
            if the names are not unique.

        :return: dictionary

        :raises: ValueError

        """
        return self._nn_interface._to_dict(self, fast_access=fast_access, short_names=short_names)

    def f_store_child(self, name, recursive=False):
        """Stores a child or recursively a subtree to disk.

        :param name:

            Name of child to store. If grouped ('groupA.groupB.childC') the path along the way
            to last node in the chain is stored. Shortcuts are NOT allowed!

        :param recursive:

            Whether recursively all children's children should be stored too.

        :raises: ValueError if the child does not exist.

        """
        if not self.f_contains(name, shortcuts=False):
            raise ValueError('Your group `%s` does not (directly) contain the child `%s`. '
                             'Please not that shortcuts are not allowed for `f_store_child`.' %
                             (self.v_full_name, name))

        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.store(pypetconstants.TREE, self, name,
                              trajectory_name=traj.v_trajectory_name,
                              recursive=recursive)

    def f_load_child(self, name, recursive=False, load_data=pypetconstants.LOAD_DATA):
        """Loads a child or recursively a subtree from disk.

        :param name:

            Name of child to load. If grouped ('groupA.groupB.childC') the path along the way
            to last node in the chain is loaded. Shortcuts are NOT allowed!

        :param recursive:

            Whether recursively all nodes below the last child should be loaded, too.

        :param load_data:

            Flag how to load the data.
            For how to choose 'load_data' see :ref:`more-on-loading`.

        :returns:

            The loaded child, in case of grouping ('groupA.groupB.childC') the last
            node (here 'childC') is returned.

        """

        traj = self._nn_interface._root_instance
        storage_service = traj.v_storage_service

        storage_service.load(pypetconstants.TREE, self, child_name=name,
                             trajectory_name=traj.v_trajectory_name,
                             recursive=recursive, load_data=load_data, trajectory=traj)

        return self.f_get(name, shortcuts=False)


class ParameterGroup(NNGroupNode):
    """ Group node in your trajectory, hanging below `traj.parameters`.

    You can add other groups or parameters to it.

    """

    def f_add_parameter_group(self, name, comment=''):
        """Adds an empty parameter group under the current node.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is the trajectory (root), the prefix `'parameters'`
        is added to the full name.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        created.

        """
        return self._nn_interface._add_generic(self, type_name=PARAMETER_GROUP,
                                               group_type_name=PARAMETER_GROUP,
                                               args=(name, comment), kwargs={})

    def f_add_parameter(self, *args, **kwargs):
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
        return self._nn_interface._add_generic(self, type_name=PARAMETER,
                                               group_type_name=PARAMETER_GROUP,
                                               args=args, kwargs=kwargs)


class ResultGroup(NNGroupNode):
    """Group node in your trajectory, hanging below `traj.results`.

    You can add other groups or results to it.

    """

    def f_add_result_group(self, name, comment=''):
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
                                               args=(name, comment), kwargs={})

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


class DerivedParameterGroup(NNGroupNode):
    """Group node in your trajectory, hanging below `traj.derived_parameters`.

    You can add other groups or parameters to it.

    """

    def f_add_derived_parameter_group(self, name, comment=''):
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
                                               args=(name, comment), kwargs={})

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


class ConfigGroup(NNGroupNode):
    """Group node in your trajectory, hanging below `traj.config`.

    You can add other groups or parameters to it.

    """

    def f_add_config_group(self, name, comment=''):
        """Adds an empty config group under the current node.

        Adds the full name of the current node as prefix to the name of the group.
        If current node is the trajectory (root), the prefix `'config'` is added to the full name.

        The `name` can also contain subgroups separated via colons, for example:
        `name=subgroup1.subgroup2.subgroup3`. These other parent groups will be automatically
        be created.

        """
        return self._nn_interface._add_generic(self, type_name=CONFIG_GROUP,
                                               group_type_name=CONFIG_GROUP,
                                               args=(name, comment), kwargs={})

    def f_add_config(self, *args, **kwargs):
        """Adds a config parameter under the current group.

        Similar to
        :func:`~pypet.naturalnaming.ParameterGroup.f_add_parameter`.

        If current group is the trajectory the prefix `'config'` is added to the name.

        """
        return self._nn_interface._add_generic(self, type_name=CONFIG,
                                               group_type_name=CONFIG_GROUP,
                                               args=args, kwargs=kwargs)




