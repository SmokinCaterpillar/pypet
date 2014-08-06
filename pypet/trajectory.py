"""Module containing the trajectory containers.

:class:`~pypet.trajectory.Trajectory` is the basic container class to manage results and
parameters (see also :mod:`pypet.parameters`).

:class:`~pypet.trajectory.SingleRun` is a reduced Trajectory only containing the information
of a particular parameter combination in case of parameter exploration.
Note for simplicity it is the parent class of the Trajectory.
A SingleRun provides less functionality than the Trajectory.

"""

__author__ = 'Robert Meyer'

import datetime
import time
import hashlib
import importlib
import itertools as itools
import inspect
import copy as cp
import numpy as np
import sys

if sys.version_info < (2, 7, 0):
    from ordereddict import OrderedDict
else:
    from collections import OrderedDict
try:
    from future_builtins import zip, map, filter
except ImportError:  # not 2.6+ or is 3.x
    try:
        from itertools import izip as zip  # < 2.5 or 3.x
        from itertools import imap as map
        from itertools import ifilter as filter
    except ImportError:
        pass

import pypet.pypetexceptions as pex
import pypet.compat as compat
from pypet._version import __version__ as VERSION
import pypet.pypetconstants as pypetconstants
from pypet.naturalnaming import NNGroupNode, NaturalNamingInterface, ResultGroup, ParameterGroup, \
    DerivedParameterGroup, ConfigGroup, STORE, LOAD, REMOVE
from pypet.parameter import BaseParameter, BaseResult, Parameter, Result, ArrayParameter, \
    PickleResult, SparseParameter, SparseResult
import pypet.storageservice as storage


class SingleRun(DerivedParameterGroup, ResultGroup):
    """ Constitutes one specific parameter combination in a whole trajectory
    with parameter exploration.

    A SingleRun instance is accessed during the actual run phase of a trajectory
    (see also :class:`~pypet.trajectory.Trajectory`).
    There exists a SingleRun object for each point in the parameter space.

    Parameters can no longer be added, the parameter set is supposed to be complete before
    the actual running of the experiment. However, derived parameters can still be added.

    The instance of a SingleRun is never instantiated by the user but by the parent trajectory.

    """

    def __init__(self, name, idx, parent_trajectory):
        super(SingleRun, self).__init__()

        # We keep a reference to the parent trajectory.
        # In case of multiprocessing the parent trajectory usually does not contain the full
        # parameter exploration but only the current point in the parameter space.
        # This behavior can be altered by modifying `v_full_copy`.
        self._parent_trajectory = parent_trajectory

        self._name = name
        self._idx = idx

        self._set_start_time()  # Sets current time as start time, if using environment is reset
        # to time precise time point of start
        self._finish_timestamp = None  # End of run, set by the environemnt
        self._runtime = None  # Runtime in human readable format
        self._timestamp = None
        self._time = None

        self._trajectory_name = parent_trajectory.v_name
        self._trajectory_time = parent_trajectory.v_time
        self._trajectory_timestamp = parent_trajectory.v_timestamp

        self._parameters = parent_trajectory._parameters
        self._derived_parameters = parent_trajectory._derived_parameters
        self._results = parent_trajectory._results
        self._explored_parameters = parent_trajectory._explored_parameters
        self._config = parent_trajectory._config
        self._groups = parent_trajectory._groups
        self._run_parent_groups = parent_trajectory._run_parent_groups
        self._other_leaves = parent_trajectory._other_leaves

        # The single run takes over the nn_interface of the parent trajectory and
        # changes the root. This alters the nn_interface of the parent trajectory.
        # As long as the root note is changed, you should not tamper with the parent
        # trajectory at all.
        self._nn_interface = parent_trajectory._nn_interface
        self._nn_interface._change_root(self)

        self._storage_service = parent_trajectory._storage_service

        self._standard_parameter = parent_trajectory.v_standard_parameter
        self._standard_result = parent_trajectory.v_standard_result
        self._standard_leaf = parent_trajectory.v_standard_leaf
        self._fast_access = parent_trajectory.v_fast_access
        self._backwards_search = parent_trajectory.v_backwards_search
        self._shortcuts = parent_trajectory.v_shortcuts
        self._iter_recursive = parent_trajectory._iter_recursive
        self._max_depth = parent_trajectory._max_depth
        self._auto_load = parent_trajectory._auto_load

        self._stored = True

        self._dynamic_imports = parent_trajectory._dynamic_imports

        self._set_logger()

        self._is_run = True
        self._as_run = self.v_name

        # Single Run objects can have no annotations at the root node of the tree.
        # The hdf5 file later on only has a single root node. This would require a
        # complex merging of information which we want to avoid.
        self._annotations = None

        self._environment_hexsha = parent_trajectory.v_environment_hexsha
        self._environment_name = parent_trajectory.v_environment_name
        self._filename = parent_trajectory.v_filename

        # Only needed in parent trajectory.
        # But if we keep it here, we can have a simpler generic addition of elements
        # in the natural naming interface
        self._changed_default_parameters = {}

    @property
    def v_as_run(self):
        """In case of a single run, this returns simply the name of the run."""
        return self._name

    @property
    def v_filename(self):
        """The name and path of the hdf5 file in case you use the HDF5StorageService"""
        return self._filename

    def _set_start_time(self):
        """Sets the start timestamp and formatted time to the current time.

        First called from constructor.
        Can be called from the environment to reset the time, to time not the creation but
        the start of the run.

        """
        init_time = time.time()
        formatted_time = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        self._timestamp = init_time
        self._time = formatted_time

    def _set_finish_time(self):
        """Sets the finish time and computes the runtime in human readable format"""
        init_time = time.time()
        #formatted_time = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        self._finish_timestamp = init_time

        findatetime = datetime.datetime.fromtimestamp(self._finish_timestamp)
        startdatetime = datetime.datetime.fromtimestamp(self._timestamp)

        self._runtime = str(findatetime - startdatetime)


    def __len__(self):
        """ Length of a single run can only be 1 and nothing else!"""
        return 1


    def _create_class(self, class_name):
        """Dynamically creates a class.

        It is tried if the class can be created by the already given imports.
        If not the list of the dynamically loaded classes is used.

        """
        try:
            new_class = eval(class_name)

            if not inspect.isclass(new_class):
                raise TypeError('Not a class!')

            return new_class
        except (NameError, TypeError):
            for dynamic_class in self._dynamic_imports:
                # Dynamic classes can be provided directly as a Class instance,
                # for example as `MyCustomParameter`,
                # or as a string describing where to import the class from,
                # for instance as `'mypackage.mymodule.MyCustomParameter'`.
                if inspect.isclass(dynamic_class):
                    if class_name == dynamic_class.__name__:
                        return dynamic_class
                else:
                    # The class name is always the last in an import string,
                    # e.g. `'mypackage.mymodule.MyCustomParameter'`
                    class_name_to_test = dynamic_class.split('.')[-1]
                    if class_name == class_name_to_test:
                        new_class = self._load_class(dynamic_class)
                        return new_class
            raise ImportError('Could not create the class named `%s`.' % class_name)

    @staticmethod
    def _load_class(full_class_string):
        """Loads a class from a string naming the module and class name.

        For example:
        >>> Trajectory._load_class(full_class_string = 'pypet.brian.parameter.BrianParameter')
        <BrianParameter>

        """

        class_data = full_class_string.split(".")
        module_path = ".".join(class_data[:-1])
        class_str = class_data[-1]
        module = importlib.import_module(module_path)

        # We retrieve the Class from the module
        return getattr(module, class_str)


    @property
    def v_shortcuts(self):
        """Whether shortcuts are allowed if accessing data via natural naming or
        squared bracket indexing."""
        return self._shortcuts

    @v_shortcuts.setter
    def v_shortcuts(self, shortcuts):
        self._shortcuts = bool(shortcuts)


    @property
    def v_backwards_search(self):
        """Whether to apply backwards search in the tree if one searches a branch
        with the square brackets notation `[]`.
        """
        return self._backwards_search

    @v_backwards_search.setter
    def v_backwards_search(self, backwards_search):
        self._backwards_search = bool(backwards_search)

    @property
    def v_max_depth(self):
        """The maximum depth the tree should be searched if shortcuts are allowed.

        Set to `None` if there should be no depth limit.
        """
        return self._max_depth

    @v_max_depth.setter
    def v_max_depth(self, max_depth):
        self._max_depth = max_depth

    @property
    def v_iter_recursive(self):
        """Whether using `__iter__` should iterate only immediate children or
        recursively all nodes."""
        return self._iter_recursive

    @v_iter_recursive.setter
    def v_iter_recursive(self, iter_recursive):
        self._iter_recursive = bool(iter_recursive)


    @property
    def v_auto_load(self):
        """Whether the trajectory should attempt to load data on the fly.
        """
        return self._auto_load

    @v_auto_load.setter
    def v_auto_load(self, auto_load):
        self._auto_load = bool(auto_load)

    @property
    def v_timestamp(self):
        """Float timestamp of creation time"""
        return self._timestamp

    @property
    def v_time(self):
        """Formatted time string of the time the trajectory or run was created."""
        return self._time

    @property
    def v_standard_parameter(self):
        """ The standard parameter used for parameter creation"""
        return self._standard_parameter

    @v_standard_parameter.setter
    def v_standard_parameter(self, parameter):
        """Sets the standard parameter"""
        self._standard_parameter = parameter

    @property
    def v_standard_result(self):
        """The standard result class used for result creation """
        return self._standard_result

    @v_standard_result.setter
    def v_standard_result(self, result):
        """Sets standard result"""
        self._standard_result = result

    @property
    def v_standard_leaf(self):
        """The standard constructor used if you add a generic leaf.

        The constructor is only used if you do not add items under the usual four subtrees
        (`parameters`, `derived_parameters`, `config`, `results`).

        """
        return self._standard_leaf

    @v_standard_leaf.setter
    def v_standard_leaf(self, leaf):
        """Sets standard result"""
        self._standard_leaf = leaf

    @property
    def v_fast_access(self):
        """Whether parameter instances (False) or their values (True) are returned via natural
        naming.

        Works also for results if they contain a single item with the name of the result.

        Default is True.

        """
        return self._fast_access

    @v_fast_access.setter
    def v_fast_access(self, value):
        """Sets fast access"""
        self._fast_access = bool(value)

    @property
    def v_environment_hexsha(self):
        """If the trajectory is used with an environment this returns
        the SHA-1 code of the environment.

        """
        return self._environment_hexsha

    @property
    def v_environment_name(self):
        """If the trajectory is used with an environment this returns
        the name of the environment.

        """
        return self._environment_name

    @property
    def v_storage_service(self):
        """The service which is used to store a trajectory to disk"""
        return self._storage_service

    @staticmethod
    def _return_item_dictionary(param_dict, fast_access, copy):
        """Returns a dictionary containing either all parameters, all explored parameters,
        all config, all derived parameters, or all results.

        :param param_dict: The dictionary which is about to be returned
        :param fast_access: Whether to use fast access
        :param copy: If the original dict should be returned or a shallow copy

        :return: The dictionary

        :raises: ValueError if `copy=False` and fast_access=True`

        """

        if not copy and fast_access:
            raise ValueError('You cannot access the original dictionary and use fast access at the'
                             ' same time!')
        if not fast_access:
            if copy:
                return param_dict.copy()
            else:
                return param_dict
        else:
            resdict = {}
            for key in param_dict:
                param = param_dict[key]

                val = param.f_get()
                resdict[key] = val

            return resdict

    @property
    def v_trajectory_name(self):
        """Name of the (parent) trajectory"""
        return self._trajectory_name

    @property
    def v_trajectory_time(self):
        """Time (parent) trajectory was created"""
        return self._trajectory_time

    @property
    def v_trajectory_timestamp(self):
        """Float timestamp when (parent) trajectory was created"""
        return self._trajectory_timestamp

    @property
    def v_idx(self):
        """Index of the single run"""
        return self._idx

    def _finalize(self):
        """Called by the environment after storing to perform some rollback operations.

        All results and derived parameters created in the current run are removed.

        Important for single processing to not blow up the parent trajectory with the results
        of all runs.

        """
        for group_name in self._run_parent_groups:
            group = self._run_parent_groups[group_name]
            if group.f_contains(self.v_name):
                group.f_remove_child(self.v_name, recursive=True)


    def f_to_dict(self, fast_access=False, short_names=False, copy=True):
        """Returns a dictionary with pairings of (full) names as keys and instances/values.


        :param fast_access:

            If True, parameter values are returned instead of the instances.
            Works also for results if they contain a single item with the name of the result.

        :param short_names:

            If true, keys are not full names but only the names. Raises a ValueError
            if the names are not unique.

        :param copy:

            If `fast_access=False` and `short_names=False` you can access the original
            data dictionary if you set `copy=False`. If you do that, please do not
            modify anything! Raises ValueError if `copy=False` and `fast_access=True`
            or `short_names=True`.

        :return: dictionary

        :raises: ValueError

        """
        return self._nn_interface._to_dict(self, fast_access=fast_access,
                                           short_names=short_names,
                                           copy=copy)

    def f_get_config(self, fast_access=False, copy=True):
        """Returns a dictionary containing the full config names as keys and the config parameters
        or the config parameter data items as values.


        :param fast_access:

            Determines whether the parameter objects or their values are returned
            in the dictionary.

        :param copy:

            Whether the original dictionary or a shallow copy is returned.
            If you want the real dictionary please do not modify it at all!
            Not Copying and fast access do not work at the same time! Raises ValueError
            if fast access is true and copy false.

        :return: Dictionary containing the config data

        :raises: ValueError

        """
        return self._return_item_dictionary(self._config, fast_access, copy)

    def f_get_parameters(self, fast_access=False, copy=True):
        """ Returns a dictionary containing the full parameter names as keys and the parameters
         or the parameter data items as values.


        :param fast_access:

            Determines whether the parameter objects or their values are returned
            in the dictionary.

        :param copy:

            Whether the original dictionary or a shallow copy is returned.
            If you want the real dictionary please do not modify it at all!
            Not Copying and fast access do not work at the same time! Raises ValueError
            if fast access is true and copy false.

        :return: Dictionary containing the parameters.

        :raises: ValueError

        """
        return self._return_item_dictionary(self._parameters, fast_access, copy)


    def f_get_explored_parameters(self, fast_access=False, copy=True):
        """ Returns a dictionary containing the full parameter names as keys and the parameters
         or the parameter data items as values.


        :param fast_access:

            Determines whether the parameter objects or their values are returned
            in the dictionary.

        :param copy:

            Whether the original dictionary or a shallow copy is returned.
            If you want the real dictionary please do not modify it at all!
            Not Copying and fast access do not work at the same time! Raises ValueError
            if fast access is true and copy false.

        :return: Dictionary containing the parameters.

        :raises: ValueError

        """
        return self._return_item_dictionary(self._explored_parameters, fast_access, copy)

    def f_get_derived_parameters(self, fast_access=False, copy=True):
        """ Returns a dictionary containing the full parameter names as keys and the parameters
         or the parameter data items as values.


        :param fast_access:

            Determines whether the parameter objects or their values are returned
            in the dictionary.

        :param copy:

            Whether the original dictionary or a shallow copy is returned.
            If you want the real dictionary please do not modify it at all!
            Not Copying and fast access do not work at the same time! Raises ValueError
            if fast access is true and copy false.

        :return: Dictionary containing the parameters.

        :raises: ValueError

        """
        return self._return_item_dictionary(self._derived_parameters, fast_access, copy)

    def f_get_results(self, fast_access=False, copy=True):
        """ Returns a dictionary containing the full result names as keys and the corresponding
        result objects or result data items as values.


        :param fast_access:

            Determines whether the result objects or their values are returned
            in the dictionary. Works only for results if they contain a single item with
            the name of the result.

        :param copy:

            Whether the original dictionary or a shallow copy is returned.
            If you want the real dictionary please do not modify it at all!
            Not Copying and fast access do not work at the same time! Raises ValueError
            if fast access is true and copy false.

        :return: Dictionary containing the results.

        :raises: ValueError

        """
        return self._return_item_dictionary(self._results, fast_access, copy)

    def f_store(self):
        """Stores all data from the single run to disk.

        Looks for new data that is added below a group called `run_XXXXXXXXXX` and
        stores it where `XXXXXXXXX` is the index of this run.

        """
        self._storage_service.store(pypetconstants.SINGLE_RUN, self,
                                    trajectory_name=self.v_trajectory_name,
                                    store_final=False, store_data=True)


    def _store_final(self, store_data=False):
        """Signals the storage service that single run is completed

        :param store_data: If all data should be stored as in `f_store`.

        """
        self._storage_service.store(pypetconstants.SINGLE_RUN, self,
                                    trajectory_name=self.v_trajectory_name,
                                    store_final=True, store_data=store_data)

    def f_store_item(self, item, *args, **kwargs):
        """Stores a single item, see also :func:`~pypet.trajectory.SingleRun.f_store_items`."""
        self.f_store_items([item], *args, **kwargs)

    def f_store_items(self, iterator, *args, **kwargs):
        """Stores individual items to disk.

        This function is useful if you calculated very large results (or large derived parameters)
        during runtime and you want to write these to disk immediately and empty them afterwards
        to free some memory.

        Instead of storing individual parameters or results you can also store whole subtrees with
        :func:`~pypet.naturalnaming.NNGroupNode.f_store_child`.


        You can pass the following arguments to `f_store_items`:

        :param iterator:

            An iterable containing the parameters or results to store, either their
            names or the instances. You can also pass group instances or names here
            to store the annotations of the groups.

        :param non_empties:

            Optional keyword argument (boolean),
            if `True` will only store the subset of provided items that are not empty.
            Empty parameters or results found in `iterator` are simply ignored.

        :param args: Additional arguments passed to the storage service

        :param kwargs:

            If you use the standard hdf5 storage service, you can pass the following additional
            keyword argument:

            :param overwrite:

                List names of parts of your item that should
                be erased and overwritten by the new data in your leaf.
                You can also set `overwrite=True`
                to overwrite all parts.

                For instance:

                    >>> traj.f_add_result('mygroup.myresult', partA=42, partB=44, partC=46)
                    >>> traj.f_store()
                    >>> traj.mygroup.myresult.partA = 333
                    >>> traj.mygroup.myresult.partB = 'I am going to change to a string'
                    >>> traj.f_store_item('mygroup.myresult', overwrite=['partA', 'partB'])

                Will store `'mygroup.myresult'` to disk again and overwrite the parts
                `'partA'` and `'partB'` with the new values `333` and
                `'I am going to change to a string'`.
                The data stored as `partC` is not changed.

                Be aware that you need to specify the names of parts as they were stored
                to HDF5. Depending on how your leaf construction works, this may differ
                from the names the data might have in your leaf in the trajectory container.

                Note that massive overwriting will fragment and blow up your HDF5 file.
                Try to avoid changing data on disk whenever you can.

        :raises:

            TypeError:

                If the (parent) trajectory has never been stored to disk. In this case
                use :func:`pypet.trajectory.f_store` first.

            ValueError: If no item could be found to be stored.

        Note if you use the standard hdf5 storage service, there are no additional arguments
        or keyword arguments to pass!

        """

        if not self._stored:
            raise TypeError('Cannot store stuff for a trajectory that has never been '
                            'stored to disk. Please call traj.f_store(only_init=True) first.')

        fetched_items = self._nn_interface._fetch_items(STORE, iterator, args, kwargs)

        if fetched_items:
            self._storage_service.store(pypetconstants.LIST, fetched_items,
                                        trajectory_name=self.v_trajectory_name)
        else:
            raise ValueError('Your storage was not successful, could not find a single item '
                             'to store.')

    def f_load_item(self, item, *args, **kwargs):
        """Loads a single item, see also :func:`~pypet.trajectory.SingleRun.f_load_items`"""
        self.f_load_items([item], *args, **kwargs)

    def f_load_items(self, iterator, *args, **kwargs):
        """Loads parameters and results specified in `iterator`.

        You can directly list the Parameter objects or just their names.

        If names are given the `~pypet.trajectory.SingleRun.f_get` method is applied to find the
        parameters or results in the trajectory. Accordingly, the parameters and results
        you want to load must already exist in your trajectory (in RAM), probably they
        are just empty skeletons waiting desperately to handle data.
        If they do not exist in RAM yet, but have been stored to disk before,
        you can call :func:`~pypet.trajectory.Trajectory.f_update_skeleton` in order to
        bring your trajectory tree skeleton up to date. In case of a single run you can
        use the :func:`~pypet.naturalnaming.NNGroupNode.f_load_child` method to recursively
        load a subtree without any data.
        Then you can load the data of individual results or parameters one by one.

        If want to load the whole trajectory at once or ALL results and parameters that are
        still empty take a look at :func:`~pypet.trajectory.Trajectory.f_load`.
        As mentioned before, to load subtrees of your trajectory you might want to check out
        :func:`~pypet.naturalnaming.NNGroupNode.f_load_child`.

        To load a list of parameters or results with `f_load_items` you can pass
        the following arguments:

        :param iterator: A list with parameters or results to be loaded.

        :param only_empties:

            Optional keyword argument (boolean),
            if `True` only empty parameters or results are passed
            to the storage service to get loaded. Non-empty parameters or results found in
            `iterator` are simply ignored.

        :param args: Additional arguments directly passed to the storage service

        :param kwargs:

            Additional keyword arguments directly passed to the storage service
            (except the kwarg `only_empties`)

            If you use the standard hdf5 storage service, you can pass the following additional
            keyword arguments:

            :param load_only:

                If you load a result, you can partially load it and ignore the rest of data items.
                Just specify the name of the data you want to load. You can also provide a list,
                for example `load_only='spikes'`, `load_only=['spikes','membrane_potential']`.

                Be aware that you need to specify the names of parts as they were stored
                to HDF5. Depending on how your leaf construction works, this may differ
                from the names the data might have in your leaf in the trajectory container.

                A warning is issued if data specified in `load_only` cannot be found in the
                instances specified in `iterator`.

            :param load_except:

                Analogous to the above, but everything is loaded except names or parts
                specified in `load_except`.
                You cannot use `load_only` and `load_except` at the same time. If you do
                a ValueError is thrown.

                A warning is issued if names listed in `load_except` are not part of the
                items to load.

        """

        if not self._stored:
            raise TypeError(
                'Cannot load stuff from disk for a trajectory that has never been stored.')

        fetched_items = self._nn_interface._fetch_items(LOAD, iterator, args, kwargs)
        if fetched_items:
            self._storage_service.load(pypetconstants.LIST, fetched_items,
                                       trajectory_name=self.v_trajectory_name)
        else:
            self._logger.warning('Your loading was not successful, could not find a single item '
                                 'to load.')

    def f_remove_item(self, item, remove_empty_groups=False):
        """Removes a single item, see :func:`~pypet.trajectory.SingleRun.remove_items`"""
        self.f_remove_items([item], remove_empty_groups)

    def f_remove_items(self, iterator, remove_empty_groups=False):
        """Removes parameters, results or groups from the trajectory.

        This function ONLY removes items from your current trajectory and does not delete
        data stored to disk. If you want to delete data from disk, take a look at
        :func:`~pypet.trajectory.SingleRun.f_delete_items`.

        :param iterator:

            A sequence of items you want to remove. Either the instances themselves
            or strings with the names of the items.

        :param remove_empty_groups:

            If your deletion of the instance leads to empty groups,
            these will be deleted, too.

        """

        # Will format the request in a form that is understood by the storage service
        # aka (msg, item, args, kwargs)
        fetched_items = self._nn_interface._fetch_items(REMOVE, iterator, (), {})

        if fetched_items:

            for msg, item, dummy1, dummy2 in fetched_items:
                self._nn_interface._remove_node_or_leaf(item, remove_empty_groups)

        else:
            self._logger.warning('Your removal was not successful, could not find a single '
                                 'item to remove.')


    def f_delete_item(self, item, *args, **kwargs):
        """Deletes a single item, see :func:`~pypet.trajectory.SingleRun.delete_items`"""
        self.f_delete_items([item], *args, **kwargs)

    def f_delete_items(self, iterator, *args, **kwargs):
        """Deletes items from storage on disk.

        Per default the item is NOT removed from the trajectory.

        :param iterator:

            A sequence of items you want to remove. Either the instances themselves
            or strings with the names of the items.

        :param remove_empty_groups:

            If your deletion of the instance leads to empty groups,
            these will be deleted, too. Default is `False`.

        :param remove_from_trajectory:

            If items should also be removed from trajectory. Default is `False`.


        :param args: Additional arguments passed to the storage service

        :param kwargs: Additional keyword arguments passed to the storage service

            If you use the standard hdf5 storage service, you can pass the following additional
            keyword argument:

            :param delete_only:

                You can partially delete leaf nodes. Specify a list of parts of the result node
                that should be deleted like `delete_only=['mystuff','otherstuff']`.
                This wil only delete the hdf5 sub parts `mystuff` and `otherstuff` from disk.
                BE CAREFUL,
                erasing data partly happens at your own risk. Depending on how complex the
                loading process of your result node is, you might not be able to reconstruct
                any data due to partially deleting some of it.

                Be aware that you need to specify the names of parts as they were stored
                to HDF5. Depending on how your leaf construction works, this may differ
                from the names the data might have in your leaf in the trajectory container.

                If the hdf5 nodes you specified in `delete_only` cannot be found a warning
                is issued.

                Note that massive deletion will fragment your HDF5 file.
                Try to avoid changing data on disk whenever you can.

                If you want to erase a full node, simply ignore this argument or set to `None`.

            :param remove_from_item:

                If data that you want to delete from storage should also be removed from
                the items in `iterator` if they contain these. Default is `False`.

        """

        remove_empty_groups = kwargs.get('remove_empty_groups', False)
        remove_from_trajectory = kwargs.pop('remove_from_trajectory', False)

        # Will format the request in a form that is understood by the storage service
        # aka (msg, item, args, kwargs)
        fetched_items = self._nn_interface._fetch_items(REMOVE, iterator, args, kwargs)

        if fetched_items:

            try:
                self._storage_service.store(pypetconstants.LIST, fetched_items,
                                            trajectory_name=self.v_trajectory_name)
            except:
                self._logger.error('Could not remove `%s` from the trajectory. Maybe the'
                                   ' item(s) was/were never stored to disk.' % str(fetched_items))
                raise

            if remove_from_trajectory:
                for msg, item, dummy1, dummy2 in fetched_items:
                    self._nn_interface._remove_node_or_leaf(item, remove_empty_groups)

        else:
            self._logger.warning('Your removal was not successful, could not find a single '
                                 'item to remove.')


class Trajectory(SingleRun, ParameterGroup, ConfigGroup):
    """The trajectory manages results and parameters.

    The trajectory is the container to interact with before a simulation.
    During a run you work with :class:`~pypet.trajectory.SingleRun` instances created
    by the parent trajectory. They do not differ much from the parent trajectory, but they
    provide less functionality.

    You can add four types of data to the trajectory:

    * Config:

        These are special parameters specifying modalities of how to run your simulations.
        Changing a config parameter should NOT have any influence on the results you
        obtain from your simulations.

        They specify runtime environment parameters like how many CPUs you use for
        multiprocessing etc.

        In fact, if you use the default runtime environment of this project, the environment
        will add some config parameters to your trajectory.

        The method to add more config is :func:`~pypet.naturalnaming.ConfigGroup.f_add_config`

        Config parameters are put into the subtree `traj.config` (with `traj` being your
        trajectory instance).

    * Parameters:

        These are your primary ammunition in numerical simulations. They specify
        how your simulation works. They can only be added before the actual
        running of the simulation exploring the parameter space. They can be
        added via :func:`~pypet.naturalnaming.ParameterGroup.f_add_parameter`
        and be explored using :func:`~pypet.trajectory.Trajectory.f_explore`.
        Or to expand an existing trajectory use :func:`~pypet.trajectory.Trajectory.f_expand`.

        Your parameters should encompass all values that completely define your simulation,
        I recommend also storing random number generator seeds as parameters to
        guarantee that a simulation can be repeated exactly the way it was run the first time.

        Parameters are put into the subtree `traj.parameters`.

    * Derived Parameters:

        They are not much different from parameters except that they can be added anytime.

        Conceptually this encompasses stuff that is intermediately
        computed from the original parameters. For instance, as your original
        parameters you have a random number seed and some other parameters.
        From these you compute a connection matrix for a neural network.
        This connection matrix could be stored as a derived parameter.

        Derived parameters are added via
        :func:`~pypet.naturalnaming.DerivedParameterGroup.f_add_derived_parameter`.

        Derived parameters are put into the subtree `traj.derived_parameters`.
        They are further sorted into  `traj.derived_parameters.runs.run_XXXXXXXX` if they were
        added during a single run. `XXXXXXXX` is replaced by the index of the corresponding run,
        for example `run_00000001`.

    * Results:

        Result are added via the :func:`~pypet.naturalnaming.ResultGroup.f_add_result`.
        They are kept under the subtree `traj.results` and are further sorted into
        `traj.results.runs.run_XXXXXXXX` if they are added during a single run.

    There are several ways to access the parameters and results, to learn about these, fast access,
    and natural naming see :ref:`more-on-access`.


    In case you create a new trajectory you can pass the following arguments:

    :param name:

        Name of the trajectory, if `add_time=True` the current time is added as a string
        to the parameter name.

    :param add_time:

        Boolean whether to add the current time in human readable format to the trajectory name.

    :param comment:

        A useful comment describing the trajectory.

    :param dynamically_imported_classes:

        If you've written a custom parameter that needs to be loaded dynamically during runtime,
        this needs to be specified here as a list of classes or strings naming classes
        and there module paths. For example:
        `dynamically_imported_classes = ['pypet.parameter.PickleParameter',MyCustomParameter]`

        If you only have a single class to import, you do not need the list brackets:
        `dynamically_imported_classes = 'pypet.parameter.PickleParameter'`

    :param filename:

        If you want to use the default :class:`rageService`, you can specify the
        filename of the HDF5 file. If you specify the filename, the trajectory
        will automatically create the corresponding service object.

    :raises:

        ValueError: If the name of the trajectory contains invalid characters.

        TypeError: If the dynamically imported classes are not classes or strings.


    Example usage:

    >>> traj = Trajectory('ExampleTrajectory',dynamically_imported_classes=['Some.custom.class'],\
    comment = 'I am a neat example!', filename='experiment.hdf5', file_title='Experiments')

    """

    def __init__(self, name='my_trajectory', add_time=True, comment='',
                 dynamically_imported_classes=None,
                 filename=None):

        # We call the init of the grandparent class because a Single Run init requires
        # a parent trajectory which would yield circular dependencies. Besides, everything
        # we need is defined in the current constructor and we can skip the parent
        # class' constructor without problems.
        super(SingleRun, self).__init__()
        self._version = VERSION
        self._python = '.'.join([str(x) for x in sys.version_info[0:3]])

        init_time = time.time()
        formatted_time = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        self._timestamp = init_time
        self._time = formatted_time

        if add_time:
            self._name = name + '_' + str(formatted_time)
        else:
            self._name = name

        self._trajectory_name = self.v_name
        self._trajectory_time = self.v_time
        self._trajectory_timestamp = self.v_timestamp

        self._parameters = {}  # Contains all parameters
        self._derived_parameters = {}  # Contains all derived parameters
        self._results = {}  # Contains all results
        self._explored_parameters = {}  # Contains all explored parameters
        self._config = {}  # Contains all config parameters
        self._groups = {}  # Contains ALL groups regardless in which subtree they are
        self._run_parent_groups = {}  # Contains all groups which are parents of run groups
        self._other_leaves = {}  # Contains ALL other user added leaves

        self._changed_default_parameters = {}  # Needed for paremeter presetting

        self._single_run_ids = {}  # A bidrectional dictionary conataining the mapping between
        # a run name and the run index (e.g. `1 <-> 'run_00000001'`), in both directions

        self._run_information = {}  # Nested Dictionary with run names as keys and
        # dictionaries as values. The inner dictionaries contain meta information about the runs
        # like time of creation, whether they have been completed and so on.
        # Check function 'f_get_run_information' for a description

        # Per Definition the lenght is set to be 1. Even with an empty trajectory
        # in principle you could make a single run
        self._add_run_info(0)

        self._nn_interface = NaturalNamingInterface(root_instance=self)
        self._fast_access = True
        self._backwards_search = False
        self._shortcuts = True
        self._iter_recursive = False
        self._max_depth = None
        self._auto_load = False

        self._expansion_not_stored = False

        self._environment_hexsha = None
        self._environment_name = None

        if filename is None:
            self._storage_service = None
            self._filename = None
        else:
            self._filename = filename
            self._storage_service = storage.HDF5StorageService(filename=filename,
                                                       file_title=self.v_name)


        # Index of a trajectory is -1, if the trajectory should behave like a single run
        # and blind out other single run results, this can be changed via 'v_as_run'.
        self._idx = -1
        self._as_run = pypetconstants.RUN_NAME_DUMMY

        self._standard_parameter = Parameter
        self._standard_result = Result
        self._standard_leaf = Result

        self._full_copy = False

        self._dynamic_imports = ['pypet.parameter.PickleParameter']

        self._is_run = False

        # Helper variable: During a multiprocessing single run, the trajectory is usually
        # pickled without all the parameter exploration ranges and all run information
        # As a consequence, __len__ would return 1, so we need to store the length in this
        # helper variable to return the correct length during single runs.
        self._length_during_run = None

        if not dynamically_imported_classes is None:
            self.f_add_to_dynamic_imports(dynamically_imported_classes)

        faulty_names = self._nn_interface._check_names([name])

        if '.' in name:
            faulty_names += ' colons >>.<< are  not allowed in trajectory names,'

        if faulty_names:
            raise ValueError('Your Trajectory %s f_contains the following not admissible names: '
                             '%s please choose other names.'
                             % (name, faulty_names))

        self._set_logger()

        self._comment = ''
        self.v_comment = comment

        # We add the four major subtrees
        # self.f_add_parameter_group('parameters')
        # self.f_add_config_group('config')
        # self.f_add_result_group('results')
        # self.f_add_derived_parameter_group('derived_parameters')

    @property
    def v_filename(self):
        """The name and path of the hdf5 file in case you use the HDF4StorageService"""
        return self._filename


    @property
    def v_version(self):
        """The version of pypet that was used to create the trajectory"""
        return self._version

    @property
    def v_python(self):
        """The version of python as a string that was used to create the trajectory"""
        return self._python

    @property
    def v_comment(self):
        """Should be a nice descriptive comment"""
        return self._comment

    @v_comment.setter
    def v_comment(self, comment):
        """Sets the comment"""
        comment = str(comment)
        self._comment = comment


    @property
    def v_storage_service(self):
        """The service that can store the trajectory to disk or wherever.

        Default is None or if a filename was provided on construction
        the :class:`~pypet.storageservice.rageService`.

        """
        return self._storage_service

    @v_storage_service.setter
    def v_storage_service(self, service):
        """Sets the storage service"""
        self._storage_service = service
        if self._filename is None and hasattr(self._storage_service, 'filename'):
            self._filename = self._storage_service.filename


    @property
    def v_idx(self):
        """Index if you want to access the trajectory as a single run.

        You can turn the trajectory to behave like a single run object if you set
        `v_idx` to a particular index. Note that only integer values are appropriate here,
        not names of runs.

        Alternatively instead of directly setting `v_idx` you can call
        :func:`~pypet.trajectory.Trajectory.f_as_run:`. See it's documentation for a description
        of making the trajectory behave like a single run.

        Set to `-1` to make the trajectory turn everything back to default.

        """
        return self._idx

    @v_idx.setter
    def v_idx(self, idx):
        """Changes the index to make the trajectory behave as a single run"""
        self.f_as_run(idx)

    @property
    def v_as_run(self):
        """Run name if you want to access the trajectory as a single run.

        You can turn the trajectory to behave like a single run object if you set
        `v_as_run` to a particular run name. Note that only string values are appropriate here,
        not indices. Check the `v_idx` property if you want to provide an index.

        Alternatively instead of directly setting `v_as_run` you can call
        :func:`~pypet.trajectory.Trajectory.f_as_run:`. See it's documentation for a description
        of making the trajectory behave like a single run.

        Set to `None` to make the trajectory to turn everything back to default.

        """
        return self._as_run

    @v_as_run.setter
    def v_as_run(self, run_name):
        """Changes the run name to make the trajectory behave as a single run"""
        self.f_as_run(run_name)

    @property
    def v_full_copy(self):
        """Whether trajectory is copied fully during pickling or only the current
        parameter space point.

        Note if the trajectory is copied as a whole, also the single run objects created
        by the trajectory can access the full parameter space.

        Changing `v_full_copy` will also change `v_full_copy` of all explored parameters!

        """
        return self._full_copy

    @v_full_copy.setter
    def v_full_copy(self, val):
        """ Sets full copy mode of trajectory and (!) ALL explored parameters!"""
        if val != self._full_copy:
            self._full_copy = val
            for param in compat.itervalues(self._explored_parameters):
                param.v_full_copy = val


    def f_add_to_dynamic_imports(self, dynamically_imported_classes):
        """Adds classes or paths to classes to the trajectory to create custom parameters.

        :param dynamically_imported_classes:

            If you've written custom parameter that needs to be loaded dynamically during runtime,
            this needs to be specified here as a list of classes or strings naming classes
            and there module paths. For example:
            `dynamically_imported_classes = ['pypet.parameter.PickleParameter',MyCustomParameter]`

            If you only have a single class to import, you do not need the list brackets:
            `dynamically_imported_classes = 'pypet.parameter.PickleParameter'`

        """

        if not isinstance(dynamically_imported_classes, (list, tuple)):
            dynamically_imported_classes = [dynamically_imported_classes]

        for item in dynamically_imported_classes:
            if not (isinstance(item, compat.base_type) or inspect.isclass(item)):
                raise TypeError('Your dynamic import `%s` is neither a class nor a string.' %
                                str(item))

        self._dynamic_imports.extend(dynamically_imported_classes)


    def f_as_run(self, name_or_idx):
        """Can make the trajectory behave like a single run, for easier data analysis.

         Has the following effects:

        *
            `v_idx` and `v_as_run` are set to the appropriate index and run name

        *
            All explored parameters are set to the corresponding value in the exploration
            ranges, i.e. when you call :func:`~pypet.parameter.Parameter.f_get` (or fast access)
            on them you will get in return the value at the corresponding `v_idx` position
            in the exploration range.

        *
            If you perform a search in the trajectory tree, the trajectory will
            only search the run subtree under *results* and *derived_parameters* with the
            corresponding index.
            For instance, if you use `f_as_run('run_00000007')` or `f_as_run(7)`
            and search for `traj.results.z` this will search for `z` only in the subtree
            `traj.results.run_00000007`. Yet, you can still explicitly name other subtrees,
            i.e. `traj.results.run_00000004.z` will still work.

            Note that this functionality also effects the iterator functions
            :func:`~pypet.naturalnaming.NNGroupNode.f_iter_nodes` and
            :func:`~pypet.naturalnaming.NNGroupNode.f_iter_leaves`.

        """
        if (name_or_idx is None or name_or_idx == pypetconstants.RUN_NAME_DUMMY or
                    name_or_idx == -1):
            self.f_restore_default()
        else:
            if isinstance(name_or_idx, compat.base_type):
                self._idx = self.f_idx_to_run(name_or_idx)
                self._as_run = name_or_idx
            else:
                self._as_run = self.f_idx_to_run(name_or_idx)
                self._idx = name_or_idx

            self._set_explored_parameters_to_idx(self.v_idx)


    def f_iter_runs(self):
        """Makes the trajectory iterate over all runs.

        Note that after a full iteration, the trajectory is set back to normal.

        Thus, the following code snippet

        ::

            for run_name in traj.f_iter_runs():

                 # Do some stuff here...


        is equivalent to

        ::

            for run_name in traj.f_get_run_names(sort=True):
                traj.f_as_run(run_name)

                # Do some stuff here...

            traj.f_as_run(None)


        :return:

            Iterator over runs. The iterator itself will return the run names but modify
            the trajectory in each iteration and set it back do normal in the end.


        """

        for run_name in self.f_get_run_names(sort=True):
            self.f_as_run(run_name)

            yield run_name

        self.f_as_run(None)

    def f_idx_to_run(self, name_or_idx):
        """Converts an integer idx to the corresponding single run name and vice versa.

        :param name_or_idx: Name of a single run or an integer index

        :return: The corresponding idx or name of the single run

        Example usage:

        >>> traj.f_idx_to_run(4)
        'run_00000004'
        >>> traj.f_idx_to_run('run_00000000')
        0

        """
        return self._single_run_ids[name_or_idx]


    def f_get_run_names(self, sort=True):
        """Returns a list of run names.

        :param sort:

            Whether to get them sorted, will only require O(N) [and not O(N*log N)] since we
            use (sort of) bucket sort.

        """
        if sort:
            return [self.f_idx_to_run(idx) for idx in compat.xrange(len(self))]
        else:
            return compat.listkeys(self._run_information)


    def f_get_run_information(self, name_or_idx=None, copy=True):
        """Returns a dictionary containing information about a single run.

        The information dictionaries have the following key, value pairings:

            * completed: Boolean, whether a run was completed

            * idx: Index of a run

            * timestamp: Timestamp of the run as a float

            * time: Formatted time string

            * finish_timestamp: Timestamp of the finishing of the run

            * runtime: Total runtime of the run in human readable format

            * name: Name of the run

            * parameter_summary:

                A string summary of the explored parameter settings for the particular run

            * short_environment_hexsha: The short version of the environment SHA-1 code


        If no name or idx is given than a nested dictionary with keys as run names and
        info dictionaries as values is returned.

        :param name_or_idx: str or int

        :param copy:

            Whether you want the dictionary used by the trajectory or a copy. Note if
            you want the real thing, please do not modify it, i.e. popping or adding stuff. This
            could mess up your whole trajectory.

        :return:

            A run information dictionary or a nested dictionary of information dictionaries
            with the run names as keys.

        """
        if name_or_idx is None:
            if copy:
                return cp.deepcopy(self._run_information)
            else:
                return self._run_information
        try:
            if copy:
                # Since the information dictionaries only contain immutable items
                # (float, int, str)
                # the normal copy operation is sufficient
                return self._run_information[name_or_idx].copy()
            else:
                return self._run_information[name_or_idx]
        except KeyError:
            # Maybe the user provided an idx, this would yield a key error and we
            # have to convert it to a run name
            name_or_idx = self.f_idx_to_run(name_or_idx)
            if copy:
                return self._run_information[name_or_idx].copy()
            else:
                return self._run_information[name_or_idx]


    def _remove_incomplete_runs(self, start_timestamp, run_indices):
        """Requests the storage service to delete incomplete runs.

        Called by the environment if you resume a crashed trajectory to allow
        re-running of non-completed runs.

        :param finished_runs:

            Number of actually finished runs

        :param nruns:

            Number of runs that were supposed to be executed with this environment

        :return

            List of indices that were completed

        """
        self._logger.info('Removing incomplete runs.')

        index_set = set(run_indices)

        # First check if the completed runs are also finished runs (i.e. are part of the snapshot)
        # If not remove these
        for run_name in self._run_information:
            info_dict = self._run_information[run_name]
            completed = info_dict['completed']
            timestamp = info_dict['timestamp']
            idx = info_dict['idx']
            name = info_dict['name']
            if completed and timestamp >= start_timestamp and idx not in index_set:
                self._run_information[name]['completed'] = 0

        cleaned_run_indices = []
        for index in run_indices:
            if self.f_is_completed(index):
                cleaned_run_indices.append(index)

        # Next, delete all the data for not completed runs
        for run_name in self._run_information:
            info_dict = self._run_information[run_name]
            completed = info_dict['completed']

            if not completed:
                for where in ['results', 'derived_parameters']:

                    if self.f_contains('%s.runs.%s' % (where, run_name), shortcuts=False):
                        self[where].runs.f_remove_child(run_name, recursive=True)

                    delete_items = True
                    try:
                        run_node = self.f_load_child('%s.runs.%s' % (where, run_name),
                                                     recursive=True, load_data=1)
                    except Exception:
                        delete_items = False  # We end here if we could not load data

                    if delete_items:
                        self.f_delete_items(run_node.f_to_dict().values(),
                                            remove_empty_groups=True,
                                            remove_from_trajectory=True)

                        if self.f_contains('%s.runs.%s' % (where, run_name), shortcuts=False):
                            # We end here if there are still some empty groups left
                            still_empty = []
                            for node in run_node.f_iter_nodes():
                                if not node.f_has_children():
                                    still_empty.append(node)

                            if still_empty:
                                self.f_delete_items(still_empty, remove_from_trajectory=True,
                                                    remove_empty_groups=True)

                        if (self.f_contains('%s.runs.%s' % (where, run_name),
                                            shortcuts=False) and
                                self.f_get('%s.runs.%s').f_has_children()):
                            raise RuntimeError('Something is wrong!')

        return cleaned_run_indices


    def f_shrink(self):
        """ Shrinks the trajectory and removes all exploration ranges from the parameters.
        Only possible if the trajectory has not been stored to disk before or was loaded as new.

        :raises: TypeError if the trajectory was stored before.

        """
        if self._stored:
            raise TypeError('Your trajectory is already stored to disk or database, shrinking is '
                            'not allowed.')

        for param in compat.itervalues(self._explored_parameters):
            param.f_unlock()
            param._shrink()

        # If we shrink, we do not have any explored parameters left and we can erase all
        # run information, and the length of the trajectory is 1 again.
        self._explored_parameters = {}
        self._run_information = {}
        self._single_run_ids = {}
        self._add_run_info(0)

    def _preset(self, name, args, kwargs):
        """Generic preset function, marks a parameter or config for presetting."""
        if name in self:
            raise ValueError('Parameter `%s` is already part of your trajectory, use the normal'
                             'accessing routine to change config.' % name)
        else:
            self._changed_default_parameters[name] = (args, kwargs)

    def f_preset_config(self, config_name, *args, **kwargs):
        """Similar to func:`~pypet.trajectory.Trajectory.f_preset_parameter`"""

        if not config_name.startswith('config.'):
            config_name = 'config.' + config_name

        self._preset(config_name, args, kwargs)

    def f_preset_parameter(self, param_name, *args, **kwargs):
        """Presets parameter value before a parameter is added.

        Can be called before parameters are added to the Trajectory in order to change the
        values that are stored into the parameter on creation.

        After creation of a parameter, the instance of the parameter is called
        with `param.f_set(*args,**kwargs)` with `*args`, and `**kwargs` provided by the user
        with `f_preset_parameter`.

        Before an experiment is carried out it is checked if all parameters that were
        marked were also preset.

        :param param_name:

            The full name (!) of the parameter that is to be changed after its creation.

        :param args:

            Arguments that will be used for changing the parameter's data

        :param kwargs:

            Keyword arguments that will be used for changing the parameter's data

        Example:

        >>> traj.f_preset_parameter('groupA.param1', data=44)
        >>> traj.f_add_parameter('groupA.param1', data=11)
        >>> traj.parameters.groupA.param1
        44

        """

        if not param_name.startswith('parameters.'):
            param_name = 'parameters.' + param_name

        self._preset(param_name, args, kwargs)

    def _prepare_experiment(self):
        """Called by the environment to make some initial configurations before performing the
        individual runs.

        Checks if all parameters marked for presetting were preset. If not raises a
        DefaultReplacementError.

        Locks all parameters.

        Removal of potential results of previous runs in case the trajectory was expanded to avoid
        mixing up undesired shortcuts in natural naming.

        """
        if len(self._changed_default_parameters):
            raise pex.PresettingError(
                'The following parameters were supposed to replace a '
                'default value, but it was never tried to '
                'add default values with these names: %s' %
                str(self._changed_default_parameters))

        self.f_lock_parameters()
        self.f_lock_derived_parameters()


        # If the trajectory is ought to be expanded we remove the subtrees of previous results
        # since they won't be used during an experiment
        if 'results' in self._children:
            results = self._children['results']
            if 'runs' in results._children:
                runs = results._children['runs']
                for node_name in compat.listkeys(runs._children):
                    if node_name.startswith(pypetconstants.RUN_NAME):
                        runs.f_remove_child(node_name, recursive=True)
        if 'derived_parameters' in self._children:
            dpars = self._children['derived_parameters']
            if 'runs' in dpars._children:
                runs = dpars._children['runs']
                for node_name in compat.listkeys(runs._children):
                    if node_name.startswith(pypetconstants.RUN_NAME):
                        runs.f_remove_child(node_name, recursive=True)

    def f_get_from_runs(self, name, where='results', use_indices=False,
                        fast_access=False, backwards_search=False,
                        shortcuts=True, max_depth=None, auto_load=False):
        """Searches for all occurrences of `name` in each run.

        Generates an ordered dictionary with the run names or indices as keys and
        found items as values.

        Example:

        >>> traj.f_get_from_runs(self, 'deep.universal_answer', use_indices=True, fast_access=True)
        OrderedDict([(0, 42), (1, 42), (2, 'fortytwo), (4, 43)])


        :param name: String description of the item(s) to find

        :param where:

            Either `'results'` (short 'r' works, too) or 'derived_parameters' (short 'd' works,
            too)

        :param use_indices:

            If `True` the keys of the resulting dictionary are the run indices
            (e.g. 0,1,2,3), otherwise the keys are run names (e.g. `run_00000000`,
            `run_000000001`)


        :param fast_access:

            Whether to return parameter or result instances or the values handled by these.

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

            Ordered dictionary with run names or indices as keys and found items as values.
            Will only include runs where an item was actually found.

        """

        if where in ['results', 'r']:
            if not 'results.runs' in self:
                raise TypeError('Trajectory does not contain any results from single runs.')

            search_group = self.results.runs
        elif where in ['derived_parameters', 'd']:
            if not 'derived_parameters.runs' in self:
                raise TypeError('Trajectory does not contain any derived parameters '
                                'from single runs.')

            search_group = self.derived_parameters.runs
        else:
            raise ValueError('Subtree `%s` unknown or not supported, please use '
                             '`where=` `results`, `derived_parameters` or short forms '
                             ' `r` or `d`.' % where)

        result_dict = OrderedDict()

        child_dict = search_group.f_get_children(copy=False)

        for run_name in self.f_get_run_names():
            # Iterate over all runs
            if run_name in child_dict:
                run_group = child_dict[run_name]

                try:
                    value = run_group.f_get(name, fast_access=fast_access,
                                            backwards_search=backwards_search,
                                            shortcuts=shortcuts,
                                            max_depth=max_depth,
                                            auto_load=auto_load)
                except pex.NotUniqueNodeError:
                    raise
                except AttributeError:
                    # In case the item cannot found in a run we do not add the run
                    # to the dictionary
                    continue

                if use_indices:
                    key = self.f_idx_to_run(run_name)
                else:
                    key = run_name

                result_dict[key] = value

        return result_dict


    def f_find_idx(self, name_list, predicate):
        """Finds a single run index given a particular condition on parameters.

        :param name_list:

            A list of parameter names the predicate applies to, if you have only a single
            parameter name you can omit the list brackets.

        :param predicate: A lambda predicate for filtering that evaluates to either true or false

        :return: A generator yielding the matching single run indices

        Example:

        >>> predicate = lambda param1, param2: param1==4 and param2 in [1.0, 2.0]
        >>> iterator = traj.f_find_idx(['groupA.param1', 'groupA.param2'], predicate)
        >>> [x for x in iterator]
        [0, 2, 17, 36]

        """
        if isinstance(name_list, compat.base_type):
            name_list = [name_list]

        # First create a list of iterators, each over the range of the matched parameters
        iter_list = []
        for name in name_list:
            param = self.f_get(name)
            if not param.v_is_parameter:
                raise TypeError('`%s` is not a parameter it is a %s, find idx is not applicable' %
                                (name, str(type(param))))

            if param.f_has_range():
                iter_list.append(iter(param.f_get_range()))
            else:
                iter_list.append(itools.repeat(param.f_get(), len(self)))

        # Create a logical iterator returning `True` or `False`
        # whether the user's predicate matches the parameter data
        logic_iter = map(predicate, *iter_list)

        # Now the run indices are the the indices where `logic_iter` evaluates to `True`
        for idx, item in enumerate(logic_iter):
            if item:
                yield idx

    def __len__(self):
        """Length of trajectory, minimum length is 1"""
        # If `v_full_copy` is False then `run_information` is not pickled, so we
        # need to rely on the helper variable `_length_during_run`.
        if hasattr(self, '_run_information') and len(self._run_information) > 0:
            return len(self._run_information)
        else:
            return self._length_during_run

    def __getstate__(self):
        result = self.__dict__.copy()

        # Do not copy run information in case `v_full_copy` is `False`.
        # Accordingly, we need to store the length in the helper variable
        # `_length_during_run`.
        if not self.v_full_copy:
            result['_run_information'] = {}
            result['_single_run_ids'] = {}
            result['_length_during_run'] = len(self)

        del result['_logger']
        return result

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._set_logger()


    def f_is_completed(self, name_or_id=None):
        """Whether or not a given run is completed.

        If no run is specified it is checked whether all runs were completed.

        :param name_or_id: Nam or id of a run to check

        :return: True or False

        """

        if name_or_id is None:
            return all(
                (runinfo['completed'] for runinfo in compat.itervalues(self._run_information)))
        else:
            return self.f_get_run_information(name_or_id)['completed']

    def f_expand(self, build_dict):
        """Similar to :func:`~pypet.trajectory.Trajectory.f_explore`, but can be used to enlarge
        already completed trajectories.

        :raises:

            TypeError: If not all explored parameters are enlarged

            AttributeError: If keys of dictionary cannot be found in the trajectory

            NotUniqueNodeError:

                If dictionary keys do not unambiguously map to single parameters

            ValueError: If not all explored parameter ranges are of the same length

        """

        enlarge_set = [self.f_get(key).v_full_name
                       for key in build_dict.keys()]


        # Check if all explored parameters will be enlarged, otherwise
        # We cannot enlarge the trajectory
        if not set(self._explored_parameters.keys()) == set(enlarge_set):
            raise TypeError('You have to enlarge dimensions you have explored before! Currently'
                            ' explored parameters are not the ones you specified in your building'
                            ' dictionary, i.e. %s != %s' %
                            (str(set(self._explored_parameters.keys())),
                             str(set(build_dict.keys()))))

        count = 0
        for key, builditerable in build_dict.items():
            act_param = self.f_get(key)

            act_param.f_unlock()
            act_param._expand(builditerable)

            name = act_param.v_full_name

            self._explored_parameters[name] = act_param

            # Compare the length of two consecutive parameters in the `build_dict`
            if count == 0:
                length = len(act_param)
            else:
                if not length == len(act_param):
                    raise ValueError('The parameters to explore have not the same size!')

            count += 1

        original_length = len(self)
        for irun in range(original_length, length):
            self._add_run_info(irun)

        # We need to update the explored parameters:
        if self._stored:
            self._expansion_not_stored = True


    def _store_expansion(self):
        for param in compat.itervalues(self._explored_parameters):
            try:
                self._storage_service.store(pypetconstants.DELETE, param,
                                            trajectory_name=self.v_trajectory_name)
            except Exception:
                pass  # We end up here if the parameter was not stored to disk, yet
            self.f_store_item(param)


    def f_explore(self, build_dict):
        """Prepares the trajectory to explore the parameter space.


        To explore the parameter space you need to provide a dictionary with the names of the
        parameters to explore as keys and iterables specifying the exploration ranges as values.

        All iterables need to have the same length otherwise a ValueError is raised.
        A ValueError is also raised if the names from the dictionary map to groups or results
        and not parameters.

        If your trajectory is already explored but not stored yet and your parameters are
        not locked you can add new explored parameters to the current ones if their
        iterables match the current length of the trajectory.

        Raises an AttributeError if the names from the dictionary are not found at all in
        the trajectory and NotUniqueNodeError if the keys not unambiguously map
        to single parameters.

        Raises a TypeError if the trajectory has been stored already, please use
        :func:`~pypet.trajectory.Trajectory.f_expand` then instead.

        Example usage:

        >>> traj.explore({'groupA.param1' : [1,2,3,4,5], 'groupA.param2':['a','b','c','d','e']})

        NOTE:

        Since parameters are very conservative regarding the data they accept
        (see :ref:`type_conservation`), you sometimes won't be able to use Numpy arrays
        for exploration as iterables.

        For instance, the following code snippet won't work:

        ::

            import numpy a np
            from pypet.trajectory import Trajectory
            traj = Trajectory()
            traj.f_add_parameter('my_float_parameter', 42.4,
                                 comment='My value is a standard python float')

            traj.f_explore( { 'my_float_parameter': np.arange(42.0, 44.876, 0.23) } )


        This will result in a `TypeError` because your exploration iterable
        `np.arange(42.0, 44.876, 0.23)` contains `numpy.float64` values
        whereas you parameter is supposed to use standard python floats.

        Yet, you can use Numpys `tolist()` function to overcome this problem:

        ::

            traj.f_explore( { 'my_float_parameter': np.arange(42.0, 44.876, 0.23).tolist() } )


        Or you could specify your parameter directly as a numpy float:

        ::

            traj.f_add_parameter('my_float_parameter', np.float64(42.4),
                                   comment='My value is a numpy 64 bit float')

        """

        if self._stored:
            raise TypeError('Cannot explore an already stored trajectory, '
                            'please use `f_expand` instead.')

        if len(self._explored_parameters) > 0:
            self._logger.info('Your trajectory is already explored. But if the parameters'
                              ' you want to explore matche the current trajectory length.'
                              ' I will add them to'
                              ' the existing explored parameters.')

        count = 0
        for key, builditerable in build_dict.items():
            act_param = self.f_get(key)
            if not act_param.v_is_leaf or not act_param.v_is_parameter:
                raise ValueError('%s is not an appropriate search string for a parameter.' % key)

            act_param._explore(builditerable)

            name = act_param.v_full_name

            self._explored_parameters[name] = act_param

            # Compare the length of two consecutive parameters in the `build_dict`
            if count == 0 and len(self) == 1:
                length = len(act_param)
            elif len(self) > 1:
                # We end up here if we increase the explored parameters
                length = len(self)

            if not length == len(act_param):
                raise ValueError('The parameters to explore have not the same size!')

            count += 1

        for irun in range(length):
            self._add_run_info(irun)

    def _add_run_info(self, idx):
        """Adds a new run to the `_run_information` dict.

        :param idx: Integer index of the new run

        """
        runname = pypetconstants.FORMATTED_RUN_NAME % idx
        # The `_single_run_ids` dict is bidirectional and maps indices to run names and vice versa
        self._single_run_ids[runname] = idx
        self._single_run_ids[idx] = runname

        info_dict = {}
        info_dict['idx'] = idx
        info_dict['timestamp'] = 42.0
        info_dict['finish_timestamp'] = 1.337
        info_dict['runtime'] = 'forever and ever'
        info_dict['time'] = '~waste ur t1me with a phd'
        info_dict['completed'] = 0
        info_dict['name'] = runname
        info_dict['parameter_summary'] = 'Not yet my friend!'
        info_dict['short_environment_hexsha'] = 'notyet1'

        self._run_information[runname] = info_dict


    def f_lock_parameters(self):
        """Locks all parameters"""
        for par in compat.itervalues(self._parameters):
            par.f_lock()

    def f_lock_derived_parameters(self):
        """Locks all derived parameters"""
        for par in compat.itervalues(self._derived_parameters):
            par.f_lock()

    def _remove_run_data(self):
        for group_name in self._run_parent_groups:
            group = self._run_parent_groups[group_name]
            for child_name in compat.listkeys(group.f_get_children(copy=False)):
                if (child_name.startswith(pypetconstants.RUN_NAME) and
                            child_name != pypetconstants.RUN_NAME_DUMMY):
                    group.f_remove_child(child_name, recursive=True)

    def _finalize(self):
        """Final rollback initiated by the environment

        Restores the trajectory as root of the tree, and loads meta data from disk.
        This updates the trajectory's information about single runs, i.e. if they've been
        completed, when they were started, etc.

        """
        self.f_restore_default()
        self._nn_interface._change_root(self)
        self.f_load(self.v_name, None, False, load_parameters=pypetconstants.LOAD_NOTHING,
                    load_derived_parameters=pypetconstants.LOAD_NOTHING,
                    load_results=pypetconstants.LOAD_NOTHING,
                    load_other_data=pypetconstants.LOAD_NOTHING)

    def f_update_skeleton(self):
        """Loads the full skeleton from the storage service.

        This needs to be done after a successful exploration in order to update the
        trajectory tree with all results and derived parameters from the individual single runs.
        This will only add empty results and derived parameters (i.e. the skeleton)
        and load annotations.

        """
        self.f_load(self.v_name, as_new=False,
                    load_parameters=pypetconstants.LOAD_SKELETON,
                    load_derived_parameters=pypetconstants.LOAD_SKELETON,
                    load_results=pypetconstants.LOAD_SKELETON,
                    load_other_data=pypetconstants.LOAD_SKELETON)


    def f_load(self,
               name=None,
               index=None,
               as_new=False,
               load_parameters=pypetconstants.LOAD_DATA,
               load_derived_parameters=pypetconstants.LOAD_SKELETON,
               load_results=pypetconstants.LOAD_SKELETON,
               load_other_data=pypetconstants.LOAD_SKELETON,
               load_all=None,
               force=False,
               filename=None,
               dynamically_imported_classes=None):
        """Loads a trajectory via the storage service.


        If you want to load individual results or parameters manually, you can take
        a look at :func:`~pypet.trajectory.Trajectory.f_load_items`.
        To only load subtrees check out :func:`~pypet.naturalnaming.NNGroupNode.f_load_child`.


        For `f_load` you can pass the following arguments:

        :param name:

            Name of the trajectory to be loaded. If no name or index is specified
            the current name of the trajectory is used.

        :param index:

            If you don't specify a name you can specify an integer index instead.
            The corresponding trajectory in the hdf5 file at the index
            position is loaded (counting starts with 0). Negative indices are also allowed
            counting in reverse order. For instance, `-1` refers to the last trajectory in
            the file, `-2` to the second last, and so on.

        :param as_new:

            Whether you want to rerun the experiments. So the trajectory is loaded only
            with parameters. The current trajectory name is kept in this case, which should be
            different from the trajectory name specified in the input parameter `name`.
            If you load `as_new=True` all parameters are unlocked.
            If you load `as_new=False` the current trajectory is replaced by the one on disk,
            i.e. name, timestamp, formatted time etc. are all taken from disk.

        :param load_parameters: How parameters and config items are loaded

        :param load_derived_parameters: How derived parameters are loaded

        :param load_results: How results are loaded

            You can specify how to load the parameters, derived parameters and results
            as follows:

                :const:`pypet.pypetconstants.LOAD_NOTHING`: (0)

                    Nothing is loaded

                :const:`pypet.pypetconstants.LOAD_SKELETON`: (1)

                    The skeleton including annotations are loaded, i.e. the items are empty.
                    Note that if the items already exist in your trajectory an AttributeError
                    is thrown. If this is the case use -1 instead.

                :const:`pypet.pypetconstants.LOAD_DATA`: (2)

                    The whole data is loaded.
                    Note that if the items already exist in your trajectory an AttributeError
                    is thrown. If this is the case use -2 instead.

                :const:`pypet.pypetconstants.UPDATE_SKELETON`: (-1)

                    The skeleton is updated, i.e. only items that are not
                    currently part of your trajectory are loaded empty.

                :const:`pypet.pypetconstants.UPDATE_DATA`: (-2) Like (2)

                    Only items that are currently not in your trajectory are loaded with data.


                Note that in all cases except :const:`pypet.pypetconstants.LOAD_NOTHING`,
                annotations will be reloaded if the corresponding instance
                is created or the annotations of an existing instance were emptied before.

        :param load_all:

            As the above, per default set to `None`. If not `None` the setting of `load_all`
            will overwrite the settings of `load_parameters`, `load_derived_parameters`,
            `load_results`, and `load_other_data`. This is more or less or shortcut if all
            types should be loaded the same.

        :param force:

            pypet will refuse to load trajectories that have been created using pypet with a
            different version number. To force the load of a trajectory from a previous version
            simply set `force = True`.

        :param filename:

            If you haven't specified a filename on creation of the trajectory, you can
            specify one here. The trajectory will generate an HDF5StorageService
            automatically.

        :param dynamically_imported_classes:

            If you've written a custom parameter that needs to be loaded dynamically
            during runtime, this needs to be specified here as a list of classes or
            strings naming classes and there module paths. For example:
            `dynamically_imported_classes = ['pypet.parameter.PickleParameter',MyCustomParameter]`

            If you only have a single class to import, you do not need the list brackets:
            `dynamically_imported_classes = 'pypet.parameter.PickleParameter'`

            The classes passed here are added for good and will be kept by the trajectory.
            Please add your dynamically imported classes only once.

        :raises:

            Attribute Error:

                If options 1 and 2 (load skeleton and load data) are applied but the
                objects already exist in your trajectory. This prevents implicitly overriding
                data in RAM. Use -1 and -2 instead to load only items that are currently not
                in your trajectory in RAM. Or remove the items you want to 'reload' first.

        """

        # Do some argument validity checks first
        if name is None and index is None:
            name = self.v_name

        if as_new:
            load_parameters = pypetconstants.LOAD_DATA
            load_derived_parameters = pypetconstants.LOAD_NOTHING
            load_results = pypetconstants.LOAD_NOTHING
            load_other_data = pypetconstants.LOAD_NOTHING

        if filename:
            self._filename = filename
            if self._storage_service is None:
                self._storage_service = storage.HDF5StorageService(filename=filename)
            else:
                self._storage_service.filename = filename

        if not dynamically_imported_classes is None:
            self.f_add_to_dynamic_imports(dynamically_imported_classes)

        if load_all is not None:
            load_parameters = load_all
            load_derived_parameters = load_all
            load_results = load_all
            load_other_data = load_all

        self._storage_service.load(pypetconstants.TRAJECTORY, self, trajectory_name=name,
                                   trajectory_index=index,
                                   as_new=as_new, load_parameters=load_parameters,
                                   load_derived_parameters=load_derived_parameters,
                                   load_results=load_results,
                                   load_other_data=load_other_data,
                                   force=force)

        # If a trajectory is newly loaded, all parameters are unlocked.
        if as_new:
            for param in compat.itervalues(self._parameters):
                param.f_unlock()
        else:
            self.f_lock_parameters()
            self.f_lock_derived_parameters()


    def _check_if_both_have_same_parameters(self, other_trajectory,
                                            ignore_trajectory_derived_parameters):
        """Checks if two trajectories live in the same space and can be merged."""

        if not isinstance(other_trajectory, Trajectory):
            raise TypeError('Can only merge trajectories, the other trajectory'
                            ' is of type `%s`.' % str(type(other_trajectory)))

        if self._stored:
            self.f_update_skeleton()
        if other_trajectory._stored:
            other_trajectory.f_update_skeleton()

        # Load all parameters of the current and the other trajectory
        if self._stored:
            # To suppress warnings if nothing needs to be loaded
            with self._nn_interface._disable_logger:
                self.f_load_items(compat.itervalues(self._parameters), only_empties=True)
        if other_trajectory._stored:
            with self._nn_interface._disable_logger:
                other_trajectory.f_load_items(compat.itervalues(other_trajectory._parameters),
                                              only_empties=True)

        self.f_restore_default()
        other_trajectory.f_restore_default()

        allmyparams = self._parameters.copy()
        allotherparams = other_trajectory._parameters.copy()

        # If not ignored, add also the trajectory derived parameters to check for merging
        if not ignore_trajectory_derived_parameters and 'derived_parameters' in self:
            my_traj_dpars = self._get_traj_dpars_or_results(self, 'derived_parameters')
            if self._stored:
                self.f_load_items(compat.itervalues(my_traj_dpars), only_empties=True)
            allmyparams.update(my_traj_dpars)
            other_traj_dpars = self._get_traj_dpars_or_results(other_trajectory,
                                                               'derived_parameters')
            if other_trajectory._stored:
                other_trajectory.f_load_items(other_traj_dpars.values(),
                                              only_empties=True)
            allotherparams.update(other_traj_dpars)


        # Check if the trajectories have the same parameters:
        my_keyset = set(allmyparams.keys())
        other_keyset = set(allotherparams.keys())
        if not my_keyset == other_keyset:
            diff1 = my_keyset - other_keyset
            diff2 = other_keyset - my_keyset
            raise TypeError('Cannot merge trajectories, they do not live in the same space,the '
                            'f_set of parameters `%s` is only found in the current trajectory '
                            'and `%s` only in the other trajectory.' % (str(diff1), str(diff2)))

        # Check if corresponding parameters in both trajectories are of the same type
        for key, other_param in allotherparams.items():
            my_param = self.f_get(key)
            if not my_param._values_of_same_type(my_param.f_get(), other_param.f_get()):
                raise TypeError('Cannot merge trajectories, values of parameters `%s` are not '
                                'of the same type. Types are %s (current) and %s (other).' %
                                (key, str(type(my_param.f_get())), str(type(other_param.f_get()))))

    def f_backup(self, backup_filename=None):
        """Backs up the trajectory with the given storage service.

        :param backup_filename:

            Name of file where to store the backup.

            In case you use the standard HDF5 storage service and `backup_filename=None`,
            the file will be chosen automatically.
            The backup file will be in the same folder as your hdf5 file and
            named 'backup_XXXXX.hdf5' where 'XXXXX' is the name of your current trajectory.

        """
        self._storage_service.store(pypetconstants.BACKUP, self, trajectory_name=self.v_name,
                                    backup_filename=backup_filename)

    def f_merge(self, other_trajectory, trial_parameter=None, remove_duplicates=False,
                ignore_trajectory_derived_parameters=False,
                ignore_trajectory_results=False,
                backup_filename=None,
                move_nodes=False,
                delete_other_trajectory=False,
                keep_info=True,
                keep_other_trajectory_info=True,
                merge_config=True, ):
        """Merges another trajectory into the current trajectory.

        Both trajectories must live in the same space. This means both need to have the same
        parameters with similar types of values.

        :param other_trajectory: Other trajectory instance to merge into the current one.

        :param trial_parameter:

            If you have a particular parameter that specifies only the trial
            number, i.e. an integer parameter running form 0 to T1 and
            0 to T2, the parameter is modified such that after merging it will
            cover the range 0 to T1+T2+1. T1 is the number of individual trials in the current
            trajectory and T2 number of trials in the other trajectory.

        :param remove_duplicates:

            Whether you want to remove duplicate parameter points.
            Requires N1 * N2 (quadratic complexity in single runs).
            A ValueError is raised if no runs would be merged.

        :param ignore_trajectory_derived_parameters:

            Whether you want to ignore or merge derived parameters
            kept under `.derived_parameters.trajectory`

        :param ignore_trajectory_results:

            As above but with results. If you have trajectory results
            with the same name in both trajectories, the result
            in the current trajectory is kept and the other one is
            not merged into the current trajectory.

        :param backup_filename:

            If specified, backs up both trajectories into the given filename.

            You can also choose `backup_filename = True`, than the trajectories
            are backed up into **two separate** files in your data folder and names are
            automatically chosen as in :func:`~pypet.trajectory.Trajectory.f_backup`.

        :param move_nodes:

           If you use the HDF5 storage service and both trajectories are
           stored in the same file, merging is performed fast directly within
           the file. You can choose if you want to copy nodes ('move_nodes=False`)
           from the other trajectory to the current one, or if you want to move them.
           Accordingly, the stored data is no longer accessible in the other trajectory.

        :param delete_other_trajectory:

            If you want to delete the other trajectory after merging. Only possible if
            you have chosen to `move_nodes`. Why would do you want to expensively copy
            data before and than erase it?

        :param keep_info:

            If `True`, information about the merge is added to the trajectory `config` tree under
            `config.merge`.

        :param merge_config:

            Whether or not to merge all config parameters under `.config.git`,
            `.config.environment`, and `.config.merge` of the other trajectory
            into the current one.

        :param keep_other_trajectory_info:

            Whether to keep information like length, name, etc. of the other trajectory
            in case you want to keep all the information. Setting of `keep_other_trajectory_info`
            is irrelevant in case `keep_info=False`.

        If you cannot directly merge trajectories within one HDF5 file, a slow merging process
        is used. Results are loaded, stored, and emptied again one after the other. Might take
        some time!

        Annotations of parameters and derived parameters under `.derived_parameters.trajectory`
        are NOT merged. If you wish to extract the annotations of these parameters you have to
        do that manually before merging. Note that annotations of results and derived parameters
        of single runs are copied, so you don't have to worry about these.

        """

        # Check for settings with too much overhead
        if not move_nodes and delete_other_trajectory:
            raise ValueError('You want to copy nodes, but delete the old trajectory, this is too '
                             'much overhead, please use `move_nodes = True`.')

        # Check if trajectories can be merged
        self._check_if_both_have_same_parameters(other_trajectory,
                                                 ignore_trajectory_derived_parameters)

        # BACKUP if merge is possible
        if not backup_filename is None:
            if backup_filename == 1 or backup_filename is True:
                backup_filename = None  # We set it to None here to signal the backup function
                # that we want the names to be chosen for us

            other_trajectory.f_backup(backup_filename=backup_filename)
            self.f_backup(backup_filename=backup_filename)

        # Add meta information about the merge to the current trajectory
        self._logger.info('Adding merge information')
        timestamp = time.time()
        formatted_time = datetime.datetime.fromtimestamp(timestamp).strftime('%Y_%m_%d_%Hh%Mm%Ss')
        hexsha = hashlib.sha1(compat.tobytetype(self.v_name +
                                                str(self.v_timestamp) +
                                                other_trajectory.v_name +
                                                str(other_trajectory.v_timestamp) +
                                                VERSION)).hexdigest()

        short_hexsha = hexsha[0:7]

        if keep_info:
            merge_name = 'merge_%s_%s' % (short_hexsha, formatted_time)

            config_name = 'merge.%s.timestamp' % merge_name
            self.f_add_config(config_name, timestamp,
                              comment='Timestamp of merge')

            config_name = 'merge.%s.hexsha' % merge_name
            self.f_add_config(config_name, hexsha,
                              comment='SHA-1 identifier of the merge')

            config_name = 'merge.%s.remove_duplicates' % merge_name
            self.f_add_config(config_name, remove_duplicates,
                              comment='Option to remove duplicate entries')

            config_name = 'merge.%s.ignore_trajectory_derived_parameters' % merge_name
            self.f_add_config(config_name, ignore_trajectory_derived_parameters,
                              comment='Whether or not to ignore trajectory derived'
                                      ' parameters')

            config_name = 'merge.%s.ignore_trajectory_results' % merge_name
            self.f_add_config(config_name, ignore_trajectory_results,
                              comment='Whether or not to ignore trajectory results')

            config_name = 'merge.%s.length_before_merge' % merge_name
            self.f_add_config(config_name, len(self),
                              comment='Length of trajectory before merge')

            self.config.merge.v_comment = 'Settings and information of the different merges'

            if self.v_version != VERSION:
                config_name = 'merge.%s.version' % merge_name
                self.f_add_config(config_name, self.v_version,
                                  comment='Pypet version if it differs from the version'
                                          ' of the trajectory')

            if trial_parameter is not None:
                config_name = 'merge.%s.trial_parameter' % merge_name
                self.f_add_config(config_name, len(other_trajectory),
                                  comment='Name of trial parameter')

            if keep_other_trajectory_info:

                if other_trajectory.v_version != self.v_version:
                    config_name = 'merge.%s.other_trajectory.version' % merge_name
                    self.f_add_config(config_name, other_trajectory.v_version,
                                      comment='The version of pypet you used to manage the other'
                                              ' trajectory. Only added if other trajectory\'s'
                                              ' version differs from current trajectory version.')

                config_name = 'merge.%s.other_trajectory.name' % merge_name
                self.f_add_config(config_name, other_trajectory.v_name,
                                  comment='Name of other trajectory merged into the current one')

                config_name = 'merge.%s.other_trajectory.timestamp' % merge_name
                self.f_add_config(config_name, other_trajectory.v_timestamp,
                                  comment='Timestamp of creation of other trajectory '
                                          'merged into the current one')

                config_name = 'merge.%s.other_trajectory.length' % merge_name
                self.f_add_config(config_name, len(other_trajectory),
                                  comment='Length of other trajectory')

                if other_trajectory.v_comment:
                    config_name = 'merge.%s.other_trajectory.comment' % merge_name
                    self.f_add_config(config_name, other_trajectory.v_comment,
                                      comment='Comment of other trajectory')

        # Merge parameters and keep track which runs where used and which parameters need
        # to be updated
        self._logger.info('Merging the parameters')
        used_runs, changed_parameters = self._merge_parameters(
            other_trajectory,
            remove_duplicates,
            trial_parameter,
            ignore_trajectory_derived_parameters)
        if keep_info:
            config_name = 'merge.%s.merged_runs' % merge_name
            self.f_add_config(config_name, int(np.sum(used_runs)),
                              comment='Number of merged runs')

        if np.all(used_runs == 0):
            raise ValueError('Your merge discards all runs of the other trajectory, maybe you '
                             'try to merge a trajectory with itself?')

        # Dictionary containing the mappings between run names in the other trajectory
        # and their new names in the current trajectory
        rename_dict = {}

        # Keep track of all trajectory results that should be merged and put
        # information into `rename_dict`
        if not ignore_trajectory_results and 'results' in other_trajectory:
            self._logger.info('Merging trajectory results skeletons')
            self._merge_trajectory_results(other_trajectory, rename_dict)

        # Single runs are rather easy to merge, we simply keep track of the changed namings
        # of the results and derived parameters in `rename_dict`
        # and let the storage service do the job in the next step
        self._logger.info('Merging single run skeletons')
        self._merge_single_runs(other_trajectory, used_runs, rename_dict)

        # The storage service needs to prepare the file for merging.
        # This includes updating meta information and already storing the merged parameters
        self._logger.info('Start copying results and single run derived parameters')
        self._logger.info('Updating Trajectory information and changed parameters in storage')
        self._storage_service.store(pypetconstants.PREPARE_MERGE, self,
                                    trajectory_name=self.v_name,
                                    changed_parameters=changed_parameters)

        try:
            # Merge the single run derived parameters and all results
            # within the same hdf5 file based on `renamed_dict`
            self._storage_service.store(pypetconstants.MERGE, None, trajectory_name=self.v_name,
                                        other_trajectory_name=other_trajectory.v_name,
                                        rename_dict=rename_dict, move_nodes=move_nodes,
                                        delete_trajectory=delete_other_trajectory)



        except pex.NoSuchServiceError:
            # If the storage service does not support merge we end up here
            self._logger.warning('My storage service does not support merging of trajectories, '
                                 'I will use the f_load mechanism of the other trajectory and '
                                 'store the results slowly item by item. '
                                 'Note that thereby the other '
                                 'trajectory will be altered (in RAM).')

            self._merge_slowly(other_trajectory, rename_dict)

        except ValueError as e:
            # If both trajectories are stored in separate files we end up here
            self._logger.warning(str(e))

            self._logger.warning('Could not perfom fast merging. '
                                 'I will use the `f_load` method of the other trajectory and '
                                 'store the results slowly item by item. '
                                 'Note that thereby the other '
                                 'trajectory will be altered (in RAM).')

            self._merge_slowly(other_trajectory, rename_dict)


        # Finally we will merge the git commits and other config data
        if merge_config:
            self._merge_config(other_trajectory)

        # Write the meta data about the merge to disk
        merge_group = self.f_get('config.merge')
        self.config.f_store_child('merge')
        merge_group.f_store_child(merge_name, recursive=True)

        self._logger.info('Finished Merging!')

    def _merge_config(self, other_trajectory):
        """Merges meta data about previous merges, git commits, and environment settings
        of the other trajectory into the current one.

        """

        self._logger.info('Merging config!')

        # Merge git commit meta data
        if 'config.git' in other_trajectory:

            self._logger.info('Merging git commits!')
            git_node = other_trajectory.f_get('config.git')
            param_list = []
            for param in git_node.f_iter_leaves():
                if not param.v_full_name in self:
                    param_list.append(self.f_add_config(param))

            if param_list:
                self.f_store_items(param_list)

            self._logger.info('Merging git commits successful!')

        # Merge environment meta data
        if 'config.environment' in other_trajectory:

            self._logger.info('Merging environment config!')
            env_node = other_trajectory.f_get('config.environment')
            param_list = []
            for param in env_node.f_iter_leaves():
                if not param.v_full_name in self:
                    param_list.append(self.f_add_config(param))

            if param_list:
                self.f_store_items(param_list)

            self._logger.info('Merging config successful!')

        # Merge meta data of previous merges
        if 'config.merge' in other_trajectory:

            self._logger.info('Merging merge config!')
            merge_node = other_trajectory.f_get('config.merge')
            param_list = []
            for param in merge_node.f_iter_leaves():
                if not param.v_full_name in self:
                    param_list.append(self.f_add_config(param))

            if param_list:
                self.f_store_items(param_list)

            self._logger.info('Merging config successful!')

    def _merge_slowly(self, other_trajectory, rename_dict):
        """Merges trajectories by loading iteratively items of the other trajectory and
        store it into the current trajectory.

        :param rename_dict:

            Dictionary containing mappings from the old result names in the `other_trajectory`
            to the new names in the current trajectory.

        """
        for other_key in rename_dict:
            new_key = rename_dict[other_key]

            other_instance = other_trajectory.f_get(other_key)

            if other_instance.f_is_empty():
                # To suppress warnings if nothing needs to be loaded
                with self._nn_interface._disable_logger:
                    other_trajectory.f_load_items(other_instance)

            # The empty instances for the new data have already been created before
            my_instance = self.f_get(new_key)

            if not my_instance.f_is_empty():
                raise RuntimeError('You want to slowly merge results, but your target result '
                                   '`%s` is not _empty, this should not happen.' %
                                   my_instance.v_full_name)

            load_dict = other_instance._store()
            my_instance._load(load_dict)
            my_instance.f_set_annotations(**other_instance.v_annotations.f_to_dict(copy=False))

            self.f_store_item(my_instance)

            # We do not want to blow up the RAM Memory
            if other_instance.v_is_parameter:
                other_instance.f_unlock()
                my_instance.f_unlock()
            other_instance.f_empty()
            my_instance.f_empty()


    def _merge_trajectory_results(self, other_trajectory, rename_dict):
        """Checks which results under `.results.trajectory` should be merged.

        If a result is marked for merge an empty instance is created in the current trajectory.

        Emits a warning if a result in the other trajectory already exists in the current one.

        Stores all group nodes with annotations that are not part of the current trajectory
        to disk. Results are only created empty and not stored in order to try to
        conduct faster merging and copying of results in the hdf5 file.

        :param rename_dict:

            Dictionary that is filled with the names of results in the `other_trajectory`
            as keys and the corresponding new names in the current trajectory as values.
            Note for results kept under `.results.trajectory` there is actually no need to
            change the names. So we will simply keep the original name.

        """

        other_result_nodes = self._get_traj_dpars_or_results_node_iterator(other_trajectory,
                                                                           'results')

        to_store_groups_with_annotations = []

        for node in other_result_nodes:
            full_name = node.v_full_name
            if node.v_is_leaf:
                # If the node is a result, check if the result already exists,
                # if not mark it for merge later on
                if full_name in self:
                    self._logger.warning(
                        'You already have a trajectory result called `%s` in your '
                        'trajectory. I will not copy it.' % full_name)
                else:
                    rename_dict[full_name] = full_name
                    comment = node.v_comment
                    result_type = node.f_get_class_name()
                    result_type = self._create_class(result_type)
                    self.f_add_result(result_type, full_name, comment=comment)
            else:
                # If the group is annotated and unknown to the current trajectory we
                # want to copy the annotations into the current trajectory
                if not full_name in self:
                    if not node.v_annotations.f_is_empty():
                        new_group = self.f_add_result_group(full_name)

                        annotationdict = node.v_annotations.f_to_dict()
                        new_group.f_set_annotations(**annotationdict)

                        to_store_groups_with_annotations.append(new_group)

        # If we have annotated groups, store them
        if len(to_store_groups_with_annotations) > 0:
            self.f_store_items(to_store_groups_with_annotations)


    def _merge_single_runs(self, other_trajectory, used_runs, rename_dict):
        """Checks which single run results and derived parameters should be marked for merge.

        If a result or derived parameter is marked for merge
        an empty instance is created in the current trajectory.

        Updates the `run_information` of the current trajectory.

        Stores all group nodes with annotations that are not part of the current trajectory
        to disk. Results are only created empty and not stored in order to try to
        conduct faster merging and copying of results in the hdf5 file.

        :param used_runs:

            Binary vector of length `len(other_trajectory)`,
            `1.0` marks a run that is supposed to be merged, runs flagged with `0.0` are skipped.

        :param rename_dict:

            Dictionary that is filled with the names of groups, results and derived parameters
            in the `other_trajectory` as keys and the corresponding new names
            in the current trajectory as values. We DO need to rename results and derived
            parameters here because the names of the single runs are changed.
            For example, the result `.results.run_0000001.myresult` might be reassigned the
            new full name `.results.run_00000012.myresult` when merged into the current trajectory.

        """
        count = len(self)  # Variable to count the increasing new run indices and create
        # new run names

        run_names = other_trajectory.f_get_run_names()

        to_store_groups_with_annotations = []

        for run_name in run_names:
            # Iterate through all used runs and store annotated groups and mark results and
            # derived parameters for merging
            idx = other_trajectory.f_get_run_information(run_name)['idx']
            if used_runs[idx]:
                iter_list = []
                for parent_group in compat.itervalues(other_trajectory._run_parent_groups):
                    if parent_group.f_contains(run_name):
                        node = parent_group.f_get(run_name)
                        if node.v_is_leaf:
                            nodes_iterator = iter([node])
                        else:
                            nodes_iterator = node.f_iter_nodes(recursive=True)
                        iter_list.append(nodes_iterator)

                nodes_iterator = itools.chain(*iter_list)

                # Update the run information dict of the current trajectory
                other_info_dict = other_trajectory.f_get_run_information(run_name)
                time = other_info_dict['time']
                timestamp = other_info_dict['timestamp']
                completed = other_info_dict['completed']
                short_environment_hexsha = other_info_dict['short_environment_hexsha']
                finish_timestamp = other_info_dict['finish_timestamp']
                runtime = other_info_dict['runtime']

                new_runname = pypetconstants.FORMATTED_RUN_NAME % count

                self._run_information[new_runname] = dict(
                    idx=count,
                    time=time,
                    timestamp=timestamp,
                    completed=completed,
                    short_environment_hexsha=short_environment_hexsha,
                    finish_timestamp=finish_timestamp,
                    runtime=runtime)

                self._single_run_ids[count] = new_runname
                self._single_run_ids[new_runname] = count

                count += 1

                for node in nodes_iterator:
                    full_name = node.v_full_name
                    pos_list = []
                    for idx, split in enumerate(full_name.split('.')):
                        if split.startswith(pypetconstants.RUN_NAME):
                            pos_list.append(idx)
                    new_full_name = self._rename_key(full_name, pos_list, new_runname)

                    if node.v_is_leaf:
                        # Create new empty result/derived param instance
                        # for every result/ derived param
                        # in the other trajectory
                        # that is going to be merged into the current one
                        rename_dict[full_name] = new_full_name
                        comment = node.v_comment
                        leaf_type = node.f_get_class_name()
                        leaf_type = self._create_class(leaf_type)
                        if full_name.startswith('results.'):
                            self.f_add_result(leaf_type, new_full_name, comment=comment)
                        else:
                            self.f_add_derived_parameter(leaf_type, new_full_name,
                                                         comment=comment)
                    else:
                        if not node.v_annotations.f_is_empty() or node.v_comment != '':
                            # Store all group nodes that are annotated
                            if full_name.startswith('results.'):
                                new_group = self.f_add_result_group(new_full_name)
                            else:
                                new_group = self.f_add_derived_parameter_group(new_full_name)

                            if not node.v_annotations.f_is_empty():
                                annotationdict = node.v_annotations.f_to_dict()
                                new_group.f_set_annotations(**annotationdict)

                            if node.v_comment != '':
                                new_group.v_comment = node.v_comment

                            to_store_groups_with_annotations.append(new_group)

        # If we have annotated groups, store them
        if len(to_store_groups_with_annotations) > 0:
            self.f_store_items(to_store_groups_with_annotations)


    @staticmethod
    def _rename_key(key, pos_list, new_name):
        """Rename positions of a key string with colon separation.

        Example usage:

        >>> Trajectory._rename_key('pos0.pos1.pos2', pos_list=[1], new_name='homer')
        'po0.homer.pos2'

        """
        split_key = key.split('.')
        for pos in pos_list:
            split_key[pos] = new_name
        renamed_key = '.'.join(split_key)
        return renamed_key

    @staticmethod
    def _get_traj_dpars_or_results(traj, where):
        """Extracts all parameters or results that are not below any group called run_XXXXXXXX"""
        result_dict = {}
        if where not in ['results', 'derived_parameters']:
            raise RuntimeError('You shall not pass!')

        if traj.f_contains(where):
            group = traj[where]
            for leaf in group.f_iter_leaves():
                if leaf.v_run_branch == 'trajectory':
                    result_dict[leaf.v_full_name] = leaf

        return result_dict

    @staticmethod
    def _get_traj_dpars_or_results_node_iterator(traj, where):
        """Returns an iterator over all nodes not hanging below `run_XXXXXXXX`"""

        if where not in ['results', 'derived_parameters']:
            raise RuntimeError('You shall not pass!')

        if traj.f_contains(where):
            group = traj[where]
            predicate = lambda x: x.v_run_branch == 'trajectory'
            return filter(predicate, group.f_iter_nodes(recursive=True))
        else:
            return iter([])

    def _merge_parameters(self, other_trajectory, remove_duplicates=False,
                          trial_parameter_name=None,
                          ignore_trajectory_derived_parameters=False):
        """Merges parameters from the other trajectory into the current one.

        The explored parameters in the current trajectory are directly enlarged (in RAM),
        no storage service is needed here. Later on in `f_merge` the storage service
        will be requested to store the enlarge parameters to disk.

        Note explored parameters are always enlarged. Unexplored parameters might become
        new explored parameters if they differ in their default values
        in the current and the other trajectory, respectively.

        :return: A tuple with two elements:

            1.

                Binary vector of length `len(other_trajectory)`,
                `1.0` marks a run that is supposed to be merged, runs flagged with `0.0`
                are skipped.

            2.

                List of names of parameters that were altered.

        """

        if trial_parameter_name:
            if remove_duplicates:
                self._logger.warning('You have given a trial parameter and you want to '
                                     'remove_items duplicates. There cannot be any duplicates '
                                     'when adding trials, I will not look for duplicates.')
                remove_duplicates = False


        # Dictionary containing full parameter names as keys
        # and pairs of parameters from both trajectories as values.
        # Parameters kept in this dictionary are marked for merging and will be enlarged
        # with ranges and values of corresponding parameters in the other trajectory
        params_to_change = {}

        if trial_parameter_name:
            # We want to merge a trial parameter
            # First make some sanity checks
            my_trial_parameter = self.f_get(trial_parameter_name)
            other_trial_parameter = other_trajectory.f_get(trial_parameter_name)
            if not isinstance(my_trial_parameter, BaseParameter):
                raise TypeError('Your trial_parameter `%s` does not evaluate to a real parameter'
                                ' in the trajectory' % trial_parameter_name)

            # Extract the ranges of both trial parameters
            if my_trial_parameter.f_has_range():
                my_trial_list = my_trial_parameter.f_get_range()
            else:
                # If we only have a single trial, we need to make a range of length 1
                # This is probably a very exceptional case
                my_trial_list = [my_trial_parameter.f_get()]

            if other_trial_parameter.f_has_range():
                other_trial_list = other_trial_parameter.f_get_range()
            else:
                other_trial_list = [other_trial_parameter.f_get()]

            # Make sanity checks if both ranges contain all numbers from 0 to T1
            # for the current trajectory and 0 to T2 for the other trajectory
            mytrialset = set(my_trial_list)
            mymaxtrial_T1 = max(mytrialset)  # maximum trial index in current trajectory aka T1

            if mytrialset != set(range(mymaxtrial_T1 + 1)):
                raise TypeError('In order to specify a trial parameter, this parameter must '
                                'contain integers from 0 to %d, but it in fact it '
                                'contains `%s`.' % (mymaxtrial_T1, str(mytrialset)))

            othertrialset = set(other_trial_list)
            othermaxtrial_T2 = max(othertrialset)  # maximum trial index in other trajectory aka T2
            if othertrialset != set(range(othermaxtrial_T2 + 1)):
                raise TypeError('In order to specify a trial parameter, this parameter must '
                                'contain integers from 0 to %d, but it infact it contains `%s` '
                                'in the other trajectory.' % (
                                othermaxtrial_T2, str(othertrialset)))

            # If the trial parameter's name was just given in parts we update it here
            # to the full name
            trial_parameter_name = my_trial_parameter.v_full_name

            # If we had the very exceptional case, that our trial parameter was not explored,
            # aka we only had 1 trial, we have to add it to the explored parameters
            if not trial_parameter_name in self._explored_parameters:
                self._explored_parameters[trial_parameter_name] = my_trial_parameter

            # We need to mark the trial parameter for merging
            params_to_change[trial_parameter_name] = (my_trial_parameter, other_trial_parameter)



        # Dictionary containing all parameters of the other trajectory, we will iterate through it
        # to spot parameters that need to be enlarge or become new explored parameters
        params_to_merge = other_trajectory._parameters.copy()

        if not ignore_trajectory_derived_parameters and 'derived_parameters' in self:
            trajectory_derived_parameters = \
                self._get_traj_dpars_or_results(self, 'derived_parameters')
            params_to_merge.update(trajectory_derived_parameters)

        # Iterate through all parameters of the other trajectory
        # and check which differ from the parameters of the current trajectory
        for key in params_to_merge:
            other_param = params_to_merge[key]

            my_param = self.f_get(key)
            if not my_param._values_of_same_type(my_param.f_get(), other_param.f_get()):
                raise TypeError('The parameters with name `%s` are not of the same type, cannot '
                                'merge trajectory.' % key)

            # We have taken care about the trial parameter before, it is already
            # marked for merging
            if my_param.v_full_name == trial_parameter_name:
                continue

            # If a parameter was explored in one of the trajectories or two unexplored
            # parameters differ, we need to mark them for merge
            if (my_param.f_has_range() or
                    other_param.f_has_range() or
                    not my_param._equal_values(my_param.f_get(), other_param.f_get())):

                # If two unexplored parameters differ, that means they differ in every run,
                # accordingly we do not need to check for duplicate runs anymore
                params_to_change[key] = (my_param, other_param)
                if not my_param.f_has_range() and not other_param.f_has_range():
                    remove_duplicates = False

        # Check if we use all runs or remove duplicates:
        use_runs = np.ones(len(other_trajectory))
        if remove_duplicates:

            # We need to compare all parameter combinations in the current trajectory
            # to all parameter combinations in the other trajectory to spot duplicate points.
            # Quadratic Complexity!
            for irun in compat.xrange(len(other_trajectory)):
                for jrun in compat.xrange(len(self)):
                    change = True

                    # Check all marked parameters
                    for my_param, other_param in compat.itervalues(params_to_change):
                        if other_param.f_has_range():
                            other_param._set_parameter_access(irun)

                        if my_param.f_has_range():
                            my_param._set_parameter_access(jrun)

                        val1 = my_param.f_get()
                        val2 = other_param.f_get()

                        # If only one parameter differs, the parameter space point differs
                        # and we can skip the rest of the parameters
                        if not my_param._equal_values(val1, val2):
                            change = False
                            break

                    # If we found one parameter space point in the current trajectory
                    # that matches the ith point in the other, we do not need the ith
                    # point. We can also skip comparing to the rest of the points in the
                    # current trajectory
                    if change:
                        use_runs[irun] = 0.0
                        break

            # Restore changed default values
            for my_param, other_param in compat.itervalues(params_to_change):
                other_param._restore_default()
                my_param._restore_default()


        # Merge parameters into the current trajectory
        adding_length = int(sum(use_runs))
        if adding_length == 0:
            return use_runs, []

        for my_param, other_param in compat.itervalues(params_to_change):
            fullname = my_param.v_full_name

            # We need new ranges to enlarge all parameters marked for merging
            if fullname == trial_parameter_name:
                # The trial parameter now has to cover the range 0 to T1+T2+1
                other_range = [x + mymaxtrial_T1 + 1 for x in other_trial_list]
            else:
                # In case we do not use all runs we need to filter the ranges of the
                # parameters of the other trajectory
                if other_param.f_has_range():
                    other_range = (x for run, x in zip(use_runs, other_param.f_get_range())
                                   if run)
                else:
                    other_range = (other_param.f_get() for _ in compat.xrange(adding_length))

            # If a parameter in the current trajectory was marked for merging but was not
            # explored before, we need to explore it first, simply by creating the range of
            # the current trajectory's length containing only it's default value
            if not my_param.f_has_range():
                my_param.f_unlock()
                my_param._explore((my_param.f_get() for _ in compat.xrange(len(self))))

            # After determining the new range extension `other_range`,
            # expand the parameters
            my_param.f_unlock()
            my_param._expand(other_range)

            if not fullname in self._explored_parameters:
                self._explored_parameters[fullname] = my_param

        return use_runs, compat.listkeys(params_to_change)

    def f_migrate(self, new_name=None, new_filename=None, new_file_tile=None, in_store=False):
        """Can be called to rename and relocate the trajectory.

        Choosing a new filename only works with the original HDF5StorageService.
        In case the trajectory has no storage service, a new HDF5StorageService is created

        :param new_name: New name of the trajectory, None if you do not want to change the name.

        :param new_filename:

            New file_name of the trajectory, None if you do not want to change the filename.

        :param in_store:

            Set this to True if the trajectory has been stored with the new name at the new
            file before  and you just want to "switch back" to the location.
            If you migrate to a store used before and you do not set `in_store=True`,
            the storage service will throw a RuntimeError in case you store the Trajectory
            because it will assume that you try to store a new trajectory that accidentally has
            the very same name as another trajectory. If set to `True` and trajectory is not found
            in the file, the trajectory is simply stored to the file.

        """

        if new_name is not None:
            self._name = new_name
            self._trajectory_name = self._name

        if new_file_tile is None:
            new_file_tile = self.v_name

        if new_filename is not None:
            if self._storage_service is None:
                self._storage_service = storage.HDF5StorageService(filename=new_filename,
                                                           file_title=new_file_tile)
            else:
                self._storage_service.filename = new_filename
            self._filename = new_filename

        self._stored = in_store

    def f_store(self, new_name=None, new_filename=None, only_init=False):
        """Stores the trajectory to disk.

        :param filename:

            You can give another filename here if you want to store the trajectory somewhere
            else than in the filename you have specified on trajectory creation.
            This will change the file for good. Calling `f_store` again will keep the
            new file location.

        :param new_name:

            If you want to store the trajectory under a new name. If name is changed, name
            remains for good and the trajectory keeps the new name.

        :param only_init

            If you just want to initialise the store. If yes, only meta information about
            the trajectory is stored and none of the nodes/leaves within the trajectory.

        If you use the HDF5 Storage Service only novel data is stored to disk.

        If you have results that have been stored to disk before only new data items are added and
        already present data is NOT overwritten.
        Overwriting existing data with the HDF5 storage service is currently not supported.

        If you want to store individual parameters or results, you might want to
        take a look at :func:`~pypet.SingleRun.f_store_items`.
        To store whole subtrees of your trajectory check out
        :func:`~pypet.naturalnaming.NNGroupNode.f_store_child`.
        Note both functions require that your trajectory was stored to disk with `f_store`
        at least once before.

        """

        if new_filename is not None or new_name is not None:
            self.f_migrate(new_name, new_filename)

        if self._stored and self._expansion_not_stored:
            self._store_expansion()
            self._expansion_not_stored = False

        self._storage_service.store(pypetconstants.TRAJECTORY, self, trajectory_name=self.v_name,
                                    only_init=only_init)
        self._stored = True

    def f_is_empty(self):
        """Whether no results nor parameters have been added yet to the trajectory
        (ignores config)."""
        return (len(self._parameters) == 0 and
                len(self._derived_parameters) == 0 and
                len(self._results) == 0)

    def f_restore_default(self):
        """Restores the default value in all explored parameters and sets the
        v_idx property back to -1 and v_as_run to None."""
        self._idx = -1
        self._as_run = pypetconstants.RUN_NAME_DUMMY
        for param in compat.itervalues(self._explored_parameters):
            param._restore_default()

    def _set_explored_parameters_to_idx(self, idx):
        """Notifies the explored parameters what current point in the parameter space
        they should represent.

        """
        for param in compat.itervalues(self._explored_parameters):
            param._set_parameter_access(idx)

    def _make_single_run(self, idx, copy_trajectory=False):
        """Creates a SingleRun object for parameter exploration with run index `idx`.

        If `copy_trajectory=False` the root node of the trajectory tree changes
        to the novel SingleRun instance.
        Accordingly, until switching the root node back to the current trajectory,
        you cannot interact with the tree via the trajectory but only through the SingleRun
        instance.

        If you choose `copy_trajectory=True` the entire current trajectory is copied before
        a new SingleRun object is created. Accordingly the original trajectory is left
        untouched and the root node is not changed.

        """
        if copy_trajectory:
            old_copy_mode = self.v_full_copy
            self.v_full_copy = True
            storage_service = self._storage_service
            self._storage_service = None
            traj = cp.deepcopy(self)
            self._storage_service = storage_service
            traj._storage_service = storage_service
            self.v_full_copy = old_copy_mode
            traj.v_full_copy = old_copy_mode
        else:
            traj = self

        traj._set_explored_parameters_to_idx(idx)
        name = traj.f_idx_to_run(idx)
        return SingleRun(name, idx, traj)

