""" Module containing the storage services.

Contains the standard :class:`~pypet.storageservice.HDF5StorageSerivce`
as well wrapper classes to allow thread safe multiprocess storing.

"""

__author__ = 'Robert Meyer'


import logging
import tables as pt
import os

import numpy as np
from pandas import DataFrame, read_hdf

from pypet import pypetconstants
import pypet.pypetexceptions as pex
from pypet import __version__ as VERSION
from pypet.parameter import ObjectTable


class MultiprocWrapper(object):
    """Abstract class definition of a Wrapper.

    Note that only storing is required, loading is optional.

    ABSTRACT: Needs to be defined in subclass

    """
    def store(self,*args,**kwargs):
        raise NotImplementedError('Implement this!')


class QueueStorageServiceSender(MultiprocWrapper):
    """ For multiprocessing with :const:`~pypet.pypetconstants.WRAP_MODE_QUEUE`, replaces the
        original storage service.

        All storage requests are send over a queue to the process running the
        :class:`~pypet.storageservice.QueueStorageServiceWriter`.

        Does not support loading of data!

    """
    def __init__(self):
        self.queue = None
        self._logger = logging.getLogger('pypet.storageservice.StorageServiceQueueWrapper')
        '''The queue'''

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('pypet.storageservice.StorageServiceQueueWrapper')

    def __getstate__(self):
        result = self.__dict__.copy()
        result['queue'] = None
        del result['_logger']
        return result

    def store(self,*args,**kwargs):
        """Puts data to store on queue."""
        try:
            self.queue.put(('STORE',args,kwargs))
        except IOError:
            ## This is due to a bug in Python, repeating the operation works :-/
            ## See http://bugs.python.org/issue5155
             try:
                self._logger.error('Failed sending task %s to queue, I will try again.' %
                                                str(('STORE',args,kwargs)) )
                self.queue.put(('STORE',args,kwargs))
                self._logger.error('Second queue sending try was successful!')
             except IOError:
                self._logger.error('Failed sending task %s to queue, I will try one last time.' %
                                                str(('STORE',args,kwargs)) )
                self.queue.put(('STORE',args,kwargs))
                self._logger.error('Third queue sending try was successful!')


    def send_done(self):
        """Signals the writer that it can stop listening to the queue"""
        self.queue.put(('DONE',[],{}))

class QueueStorageServiceWriter(object):
    """Wrapper class that listens to the queue and stores queue items via the storage service."""
    def __init__(self, storage_service, queue):
        self._storage_service = storage_service
        self._queue = queue

    def run(self):
        """Starts listening to the queue."""
        while True:
            try:
                msg,args,kwargs = self._queue.get()

                if msg == 'DONE':
                    break
                elif msg == 'STORE':
                    self._storage_service.store(*args, **kwargs)
                else:
                    raise RuntimeError('You queued something that was not intended to be queued!')
            except:
                raise
            finally:
                self._queue.task_done()

class LockWrapper(MultiprocWrapper):
    """For multiprocessing in :const:`~pypet.pypetconstants.WRAP_MODE_LOCK` mode,
    augments a storage service with a lock.

    The lock is acquired before storage or loading and released afterwards.

    """
    def __init__(self,storage_service, lock):
        self._storage_service = storage_service
        self._lock = lock
        self._logger = logging.getLogger('pypet.storageservice.StorageServiceLockWrapper')

    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        return result

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('pypet.storageservice.StorageServiceLockWrapper')

    def store(self,*args, **kwargs):
        """Acquires a lock before storage and releases it afterwards."""
        try:
            self._lock.acquire()
            self._storage_service.store(*args,**kwargs)
        finally:
            if self._lock is not None:
                try:
                    self._lock.release()
                except RuntimeError:
                    self._logger.error('Could not release lock `%s`!' % str(self._lock))

    def load(self,*args,**kwargs):
        """Acquires a lock before loading and releases it afterwards."""
        try:
            self._lock.acquire()
            self._storage_service.load(*args,**kwargs)
        finally:
            if self._lock is not None:
                try:
                    self._lock.release()
                except RuntimeError:
                    self._logger.error('Could not release lock `%s`!' % str(self._lock))


class StorageService(object):
    """Abstract base class defining the storage service interface."""
    def store(self,msg,stuff_to_store,*args,**kwargs):
        """See :class:`pypet.storageservice.HDF5StorageService` for an example of an
        implementation and requirements for the API.

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError('Implement this!')

    def load(self,msg,stuff_to_load,*args,**kwargs):
        """ See :class:`pypet.storageservice.HDF5StorageService` for an example of an
        implementation and requirements for the API.

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError('Implement this!')


class LazyStorageService(StorageService):
    """This lazy guy does nothing! Only for debugging purposes.

    Ignores all storage and loading requests and simply executes `pass` instead.

    """
    def load(self,*args,**kwargs):
        """Nope, I won't care, dude!"""
        pass

    def store(self,*args,**kwargs):
        """Do whatever you want, I won't store anything!"""
        pass

class HDF5StorageService(StorageService):
    """Storage Service to handle the storage of a trajectory/parameters/results into hdf5 files.

    Normally you do not interact with the storage service directly but via the trajectory,
    see :func:`pypet.trajectory.Trajectory.f_store` and :func:`pypet.trajectory.Trajectory.f_load`.

    The service is not thread safe. For multiprocessing the service needs to be wrapped either
    by the :class:`~pypet.storageservice.LockWrapper` or with a combination of
    :class:`~pypet.storageservice.QueueStorageServiceSender` and
    :class:`~pypet.storageservice.QueueStorageServiceWriter`.

    The storage service supports two operations *store* and *load*.

    Requests for these two are always passed as
    `msg, what_to_store_or_load, *args, **kwargs`

    For example:

    >>> HDF5StorageService.load(pypetconstants.LEAF, myresult, load_only=['spikestimes','nspikes'])

    For a list of supported items see :func:`~pypet.storageservice.HDF5StorageService.store`
    and :func:`~pypet.storageservice.HDF5StorageService.load`.

    """

    ADD_ROW = 'ADD'
    ''' Adds a row to an overview table'''
    REMOVE_ROW = 'REMOVE'
    ''' Removes a row from an overview table'''
    MODIFY_ROW = 'MODIFY'
    ''' Changes a row of an overview table'''


    COLL_TYPE ='COLL_TYPE'
    '''Type of a container stored to hdf5, like list,tuple,dict,etc

    Must be stored in order to allow perfect reconstructions.
    '''

    COLL_LIST = 'COLL_LIST'
    ''' Container was a list'''
    COLL_TUPLE = 'COLL_TUPLE'
    ''' Container was a tuple'''
    COLL_NDARRAY = 'COLL_NDARRAY'
    ''' Container was a numpy array'''
    COLL_MATRIX = 'COLL_MATRIX'
    ''' Container was a numpy matrix'''
    COLL_DICT = 'COLL_DICT'
    ''' Container was a dictionary'''
    COLL_SCALAR = 'COLL_SCALAR'
    ''' No container, but the thing to store was a scalar'''

    SCALAR_TYPE = 'SCALAR_TYPE'
    ''' Type of scalars stored into a container'''


    ### Overview Table constants
    CONFIG = 'config'
    PARAMETERS = 'parameters'
    RESULTS = 'results'
    EXPLORED_PARAMETERS = 'explored_parameters'
    DERIVED_PARAMETERS = 'derived_parameters'


    NAME_TABLE_MAPPING ={
           'config.hdf5.overview.config':'config',
           'config.hdf5.overview.parameters':'parameters',
           'config.hdf5.overview.derived_parameters_trajectory':'derived_parameters_trajectory',
           'config.hdf5.overview.derived_parameters_runs':'derived_parameters_runs',
           'config.hdf5.overview.results_trajectory':'results_trajectory',
           'config.hdf5.overview.results_runs':'results_runs',
           'config.hdf5.overview.explored_parameters' : 'explored_parameters',
           'config.hdf5.overview.derived_parameters_runs_summary':'derived_parameters_runs_summary',
           'config.hdf5.overview.results_runs_summary':'results_runs_summary',
    }
    ''' Mapping of trajectory config names to the tables'''


    ### Storing Data Constants
    STORAGE_TYPE= 'SRVC_STORE'
    '''Flag, how data was stored'''

    ARRAY = 'ARRAY'
    '''Stored as array_

    .. _array: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-array-class

    '''
    CARRAY = 'CARRAY'
    '''Stored as carray_

    .. _carray: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-carray-class

    '''
    EARRAY = 'EARRAY' # not supported yet
    ''' Stored as earray_

    Not supported yet, maybe in near future.

    .. _earray: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-earray-class

    '''
    VLARRAY = 'VLARRAY' # not supported yet
    '''Stored as vlarray_

    Not supported yet, maybe in near future.

    .. _vlarray: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-vlarray-class

    '''
    DICT = 'DICT'
    ''' Stored as dict.

    In fact, stored as pytable, but the dictionary wil be reconstructed.
    '''
    TABLE = 'TABLE'
    '''Stored as pytable_

    .. _pytable: http://pytables.github.io/usersguide/libref/structured_storage.html#the-table-class

    '''
    FRAME = 'FRAME'
    ''' Stored as pandas DataFrame_

    .. _DataFrame: http://pandas.pydata.org/pandas-docs/dev/io.html#hdf5-pytables

    '''

    TYPE_FLAG_MAPPING = {

        ObjectTable : TABLE,
        list:ARRAY,
        tuple:ARRAY,
        dict: DICT,
        np.ndarray:CARRAY,
        np.matrix:CARRAY,
        DataFrame : FRAME

    }
    ''' Mapping from object type to storage flag'''

    # Python native data should alwys be stored as an ARRAY
    for item in pypetconstants.PARAMETER_SUPPORTED_DATA:
        TYPE_FLAG_MAPPING[item]=ARRAY


    FORMATTED_COLUMN_PREFIX = 'SRVC_COLUMN_%s_'
    ''' Stores data type of a specific pytables column for perfect reconstruction'''
    DATA_PREFIX = 'SRVC_DATA_'
    ''' Stores data type of a pytables carray or array for perfect reconstruction'''

    # ANNOTATION CONSTANTS
    ANNOTATION_PREFIX = 'SRVC_AN_'
    ''' Prefix to store annotations as node attributes_

    .. _attributes: http://pytables.github.io/usersguide/libref/declarative_classes.html#the-attributeset-class

    '''
    ANNOTATED ='SRVC_ANNOTATED'
    ''' Whether an item was annotated'''


    # Stuff necessary to construct parameters and result
    INIT_PREFIX = 'SRVC_INIT_'
    ''' Hdf5 attribute prefix to store class name of parameter or result'''
    CLASS_NAME = INIT_PREFIX+'CLASS_NAME'
    ''' Name of a parameter or result class, is converted to a constructor'''
    COMMENT = INIT_PREFIX+'COMMENT'
    ''' Comment of parameter or result'''
    LENGTH = INIT_PREFIX+'LENGTH'
    ''' Length of a parameter if it is an array'''


    LEAF = 'SRVC_LEAF'
    ''' Whether an hdf5 node is a leaf node'''


    def __init__(self, filename=None, file_title='Experiment'):
        self._filename = filename
        self._file_title = file_title
        self._trajectory_name = None
        self._trajectory_index = None
        self._hdf5file = None
        self._trajectory_group = None # link to the top group in hdf5 file which is the start
        # node of a trajectory
        self._purge_duplicate_comments = None # remembers whether to purge duplicate comments
        self._logger = logging.getLogger('pypet.storageservice_HDF5StorageService')

    @property
    def _overview_group(self):
        """Direct link to the overview group"""
        return self._all_create_or_get_groups('overview')[0]


    def load(self,msg,stuff_to_load,*args,**kwargs):
        """Loads a particular item from disk.

        The storage service always accepts these parameters:

        :param trajectory_name: Name of current trajectory and name of top node in hdf5 file.

        :param trajectory_index:

            If no `trajectory_name` is provided, you can specify an integer index.
            The trajectory at the index position in the hdf5 file is considered to loaded.
            Negative indices are also possible for reverse indexing.

        :param filename: Name of the hdf5 file


        The following messages (first argument msg) are understood and the following arguments
        can be provided in combination with the message:

            * :const:`pypet.pypetconstants.TRAJECTORY` ('TRAJECTORY')

                Loads a trajectory.

                :param stuff_to_load: The trajectory

                :param as_new: Whether to load trajectory as new

                :param load_parameters: How to load parameters and config

                :param load_derived_parameters: How to load derived parameters

                :param load_results: How to load results

                :param force: Force load in case there is a pypet version mismatch

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

                    The skeleton and annotations are updated, i.e. only items that are not
                    currently part of your trajectory are loaded empty.

                :const:`pypet.pypetconstants.UPDATE_DATA`: (-2) Like (2)

                    Only items that are currently not in your trajectory are loaded with data.

            * :const:`pypet.pypetconstants.LEAF` ('LEAF')

                Loads a parameter or result.

                :param stuff_to_load: The item to be loaded

                :param load_only:

                    If you load a result, you can partially load it and ignore the rest of the data.
                    Just specify the name of the data you want to load. You can also provide a list,
                    for example `load_only='spikes'`, `load_only=['spikes','membrane_potential']`.

                    Throws a ValueError if data cannot be found.

            * :const:`pypet.pypetconstants.TREE` ('TREE')

                Loads a whole subtree

                :param stuff_to_load: The parent node (!) not the one where loading starts!

                :param child_name: Name of child node that should be loaded

                :param recursive: Whether to load recursively the subtree below child

                :param load_data:

                    How to load stuff, accepted values as above for loading the trajectory

                :param trajectory: The trajectory object

            * :const:`pypet.pypetconstants.LIST` ('LIST')

                Analogous to :ref:`storing lists <store-lists>`

        :raises: NoSuchServiceError if message or data is not understood

        """
        try:

            self._srvc_extract_file_information(kwargs)

            args = list(args)

            opened = self._srvc_opening_routine('r')

            if msg == pypetconstants.TRAJECTORY:
                self._trj_load_trajectory(msg,stuff_to_load,*args,**kwargs)

            elif msg == pypetconstants.LEAF:
                self._prm_load_parameter_or_result(stuff_to_load,*args,**kwargs)

            elif msg == pypetconstants.TREE:
                self._tree_load_tree(stuff_to_load,*args,**kwargs)

            elif msg ==pypetconstants.LIST:
                self._srvc_load_several_items(stuff_to_load,*args,**kwargs)

            else:
                raise pex.NoSuchServiceError('I do not know how to handle `%s`' % msg)

            self._srvc_closing_routine(opened)
        except:
            self._srvc_closing_routine(True)
            self._logger.error('Failed loading  `%s`' % str(stuff_to_load))
            raise


    def store(self,msg,stuff_to_store,*args,**kwargs):
        """ Stores a particular item to disk.

        The storage service always accepts these parameters:

        :param trajectory_name: Name or current trajectory and name of top node in hdf5 file

        :param filename: Name of the hdf5 file

        :param file_title: If file needs to be created, assigns a title to the file.


        The following messages (first argument msg) are understood and the following arguments
        can be provided in combination with the message:

            * :const:`pypet.pypetconstants.PREPARE_MERGE` ('PREPARE_MERGE'):

                Called to prepare a trajectory for merging, see also 'MERGE' below.

                Will also be called if merging cannot happen within the same hdf5 file.
                Stores already enlarged parameters and updates meta information.

                :param stuff_to_store: Trajectory that is about to be extended by another one

                :param changed_parameters:

                    List containing all parameters that were enlarged due to merging

            * :const:`pypet.pypetconstants.MERGE` ('MERGE')

                Note that before merging within HDF5 file, the storage service will be called
                with msg='PREPARE_MERGE' before, see above.

                Raises a ValueError if the two trajectories are not stored within the very
                same hdf5 file. Then the current trajectory needs to perform the merge slowly
                item by item.

                Merges two trajectories, parameters are:

                :param stuff_to_store: The trajectory data is merged into

                :param other_trajectory_name: Name of the other trajectory

                :param rename_dict:

                    Dictionary containing the old result and derived parameter names in the
                    other trajectory and their new names in the current trajectory.

                :param move_nodes:

                    Whether to move the nodes from the other to the current trajectory

                :param delete_trajectory:

                    Whether to delete the other trajectory after merging.

            * :const:`pypet.pypetconstants.BACKUP` ('BACKUP')

                :param stuff_to_store: Trajectory to be backed up

                :param backup_filename:

                    Name of file where to store the backup. If None the backup file will be in
                    the same folder as your hdf5 file and named 'backup_XXXXX.hdf5'
                    where 'XXXXX' is the name of your current trajectory.

            * :const:`pypet.pypetconstants.TRAJECTORY` ('TRAJECTORY')

                Stores the whole trajectory

                :param stuff_to_store: The trajectory to be stored

            * :const:`pypet.pypetconstants.SINGLE_RUN` ('SINGLE_RUN')

                :param stuff_to_store: The single run to be stored

            *

                :const:`pypet.pypetconstants.LEAF` or :const:`pypetconstants.UPDATE_LEAF` ('LEAF'
                or 'UPDATE_LEAF')

                Stores a parameter or result. Use `msg = 'UPDATE_LEAF'` if a parameter was expanded
                (due to merging or expanding the trajectory) to modify it's data.

                Modification of results is not supported (yet). Everything stored to disk is
                set in stone!

                Note that everything that is supported by the storage service and that is
                stored to disk will be perfectly recovered.
                For instance, you store a tuple of numpy 32 bit integers, you will get a tuple
                of numpy 32 bit integers after loading independent of the platform!

                :param stuff_to_sore: Result or parameter to store

                    In order to determine what to store, the function '_store' of the parameter or
                    result is called. This function returns a dictionary with name keys and data to
                    store as values. In order to determine how to store the data, the storage flags
                    are considered, see below.

                    The function '_store' has to return a dictionary containing values only from
                    the following objects:

                        * python natives (int, long, str, bool, float, complex),

                        *
                            numpy natives, arrays and matrices of type np.int8-64, np.uint8-64,
                            np.float32-64, np.complex, np.str

                        *

                            python lists and tuples of the previous types
                            (python natives + numpy natives and arrays)
                            Lists and tuples are not allowed to be nested and must be
                            homogeneous, i.e. only contain data of one particular type.
                            Only integers, or only floats, etc.

                        *

                            python dictionaries of the previous types (not nested!), data can be
                            heterogeneous, keys must be strings. For example, one key-value-pair
                            of string and int and one key-value pair of string and float, and so
                            on.

                        * pandas DataFrames_

                        * :class:`~pypet.parameter.ObjectTable`

                    .. _DataFrames: http://pandas.pydata.org/pandas-docs/dev/dsintro.html#dataframe

                    The keys from the '_store' dictionaries determine how the data will be named
                    in the hdf5 file.

                :param store_flags: Flags describing how to store data.

                        :const:`~pypet.HDF5StorageService.ARRAY` ('ARRAY')

                            Store stuff as array

                        :const:`~pypet.HDF5StorageService.CARRAY` ('CARRAY')

                            Store stuff as carray

                        :const:`~pypet.HDF5StorageService.TABLE` ('TABLE')

                            Store stuff as pytable

                        :const:`~pypet.HDF5StorageService.DICT` ('DICT')

                            Store stuff as pytable but reconstructs it later as dictionary
                            on loading

                        :const:`~pypet.HDF%StorageService.FRAME` ('FRAME')

                            Store stuff as pandas data frame

                    Storage flags can also be provided by the parameters and results themselves
                    if they implement a function '_store_flags' that returns a dictionary
                    with the names of the data to store as keys and the flags as values.

                    If no storage flags are provided, they are automatically inferred from the
                    data. See :const:`pypet.HDF5StorageService.TYPE_FLAG_MAPPING` for the mapping
                    from type to flag.

            * :const:`pypet.pypetconstants.REMOVE` ('REMOVE')

                Removes an item from disk. Empty group nodes, results and non-explored
                parameters can be removed.

                :param stuff_to_store: The item to be removed.

                :param remove_empty_groups:

                    Whether to also remove groups that become empty due to removal.
                    default is False.

            * :const:`pypet.pypetconstants.GROUP` ('GROUP')

                :param stuff_to_store: The group to store

            * :const:`pypet.pypetconstants.REMOVE_INCOMPLETE_RUNS` ('REMOVE_INCOMPLETE_RUNS')

                Removes all data from hdf5 file that is from an incomplete run.

                :param stuff_to_store: The trajectory

            * :const:`pypet.pypetconstants.TREE`

                Stores a single node or a full subtree

                :param stuff_to_store: Node to store

                :param recursive: Whether to store recursively the whole sub-tree

            * :const:`pypet.pypetconstants.LIST`

                .. _store-lists:

                Stores several items at once

                :param stuff_to_store:

                    Iterable whose items are to be stored. Iterable must contain tuples,
                    for example `[(msg1,item1,arg1,kwargs1),(msg2,item2,arg2,kwargs2),...]`

        :raises: NoSuchServiceError if message or data is not understood

        """
        try:

            self._srvc_extract_file_information(kwargs)


            args = list(args)


            opened= self._srvc_opening_routine('a',msg)

            if msg == pypetconstants.MERGE:
                self._trj_merge_trajectories(*args,**kwargs)

            elif msg == pypetconstants.BACKUP:
                self._trj_backup_trajectory(stuff_to_store,*args,**kwargs)

            elif msg == pypetconstants.PREPARE_MERGE:
                self._trj_prepare_merge(stuff_to_store,*args,**kwargs)

            elif msg == pypetconstants.TRAJECTORY:
                self._trj_store_trajectory(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.SINGLE_RUN:
                self._srn_store_single_run(stuff_to_store,*args,**kwargs)

            elif msg in (pypetconstants.LEAF, pypetconstants.UPDATE_LEAF):
                self._prm_store_parameter_or_result(msg,stuff_to_store,*args,**kwargs)

            elif msg == pypetconstants.REMOVE:
                self._all_remove_parameter_or_result_or_group(stuff_to_store,*args,**kwargs)

            elif msg == pypetconstants.GROUP:
                self._grp_store_group(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.REMOVE_INCOMPLETE_RUNS:
                self._trj_remove_incomplete_runs(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.TREE:
                self._tree_store_tree(stuff_to_store,*args,**kwargs)

            elif msg == pypetconstants.LIST:
                self._srvc_store_several_items(stuff_to_store,*args,**kwargs)

            else:
                raise pex.NoSuchServiceError('I do not know how to handle `%s`' % msg)

            self._srvc_closing_routine(opened)

        except:
            self._srvc_closing_routine(True)
            self._logger.error('Failed storing `%s`' % str(stuff_to_store))
            raise


    def _srvc_load_several_items(self,iterable,*args,**kwargs):
        """Loads several items from an iterable

        Iterables are supposed to be of a format like `[(msg, item, args, kwarg),...]`
        If `args` and `kwargs` are not part of a tuple, they are taken from the
        current `args` and `kwargs` provided to this function.

        """
        for input_tuple in iterable:
            msg = input_tuple[0]
            item = input_tuple[1]
            if len(input_tuple) > 2:
                args = input_tuple[2]
            if len(input_tuple) > 3:
                kwargs = input_tuple[3]
            if len(input_tuple)> 4:
                raise RuntimeError('You shall not pass!')

            self.load(msg,item,*args,**kwargs)

    def _srvc_store_several_items(self,iterable,*args,**kwargs):
        """Stores several items from an iterable

        Iterables are supposed to be of a format like `[(msg, item, args, kwarg),...]`
        If `args` and `kwargs` are not part of a tuple, they are taken from the
        current `args` and `kwargs` provided to this function.

        """
        for input_tuple in iterable:
            msg = input_tuple[0]
            item = input_tuple[1]
            if len(input_tuple) > 2:
                args = input_tuple[2]
            if len(input_tuple) > 3:
                kwargs = input_tuple[3]
            if len(input_tuple)> 4:
                raise RuntimeError('You shall not pass!')

            self.store(msg,item,*args,**kwargs)

    def _srvc_opening_routine(self,mode,msg=None):
        """Opens an hdf5 file for reading or writing

        The file is only opened if it has not been opened before (i.e. `self._hdf5file is None`).

        :param mode:

            'w' for writing

            'a' for appending

            'r' for reading

                Unfortunately, pandas currently does not work with read-only mode.
                Thus, if mode is chosen to be 'r', the file will still be opened in
                append mode.

        :param msg:

            Message provided to `load` or `store`. Only considered to check if a trajectory
            was stored before.

        :return:

            `True` if file is opened

            `False` if the file was already open before calling this function

        """
        if self._hdf5file is None:

                if 'a' in mode or 'w' in mode:
                    (path, filename)=os.path.split(self._filename)
                    if not os.path.exists(path):
                        os.makedirs(path)

                    # All following try-except blocks of this form are there to allow
                    # compatibility for PyTables 2.3.1 as well as 3.0+
                    try:
                        # PyTables 3 API
                        self._hdf5file = pt.open_file(filename=self._filename, mode=mode,
                                                 title=self._file_title)
                    except AttributeError:
                        #PyTables 2 API
                        self._hdf5file = pt.openFile(filename=self._filename, mode=mode,
                                                 title=self._file_title)


                    if not ('/'+self._trajectory_name) in self._hdf5file:
                        # If we want to store individual items we we have to check if the
                        # trajectory has been stored before
                        if not msg == pypetconstants.TRAJECTORY:
                            raise ValueError('Your trajectory cannot be found in the hdf5file, '
                                             'please use >>traj.store()<< before storing anyhting else.')

                        # If we want to store a trajectory it has not been stored before
                        # create a new trajectory group
                        try:
                            self._hdf5file.create_group(where='/', name= self._trajectory_name,
                                                   title=self._trajectory_name)
                        except AttributeError:
                            self._hdf5file.createGroup(where='/', name= self._trajectory_name,
                                                   title=self._trajectory_name)

                    # Store a reference to the top trajectory node
                    try:
                        self._trajectory_group = self._hdf5file.get_node('/'+self._trajectory_name)
                    except AttributeError:
                        self._trajectory_group = self._hdf5file.getNode('/'+self._trajectory_name)

                elif mode == 'r':

                    if not self._trajectory_name is None and not self._trajectory_index is None:

                        raise ValueError('Please specify either a name of a trajectory or an index, '
                                     'but not both at the same time.')

                    # Bad Pandas, we have to wait until the next release until opening in 'r' is
                    # supported, so we need to open in 'a' mode
                    mode = 'a'
                    if not os.path.isfile(self._filename):
                        raise ValueError('Filename ' + self._filename + ' does not exist.')

                    try:
                        self._hdf5file = pt.open_file(filename=self._filename, mode=mode,
                                                 title=self._file_title)
                    except AttributeError:
                        self._hdf5file = pt.openFile(filename=self._filename, mode=mode,
                                                 title=self._file_title)

                    if not self._trajectory_index is None:
                        # If an index is provided pick the trajectory at the corresponding
                        # position in the trajectory node list
                        try:
                            nodelist = self._hdf5file.list_nodes(where='/')
                        except AttributeError:
                            nodelist = self._hdf5file.listNodes(where='/')

                        if (self._trajectory_index >= len(nodelist) or
                                    self._trajectory_index  < -len(nodelist)):

                            raise ValueError('Trajectory No. %d does not exists, there are only '
                                             '%d trajectories in %s.'
                                        % (self._trajectory_index,len(nodelist),self._filename))

                        self._trajectory_group = nodelist[self._trajectory_index]
                        self._trajectory_name = self._trajectory_group._v_name

                    elif not self._trajectory_name is None:
                        # Otherwise pick the trajectory group by name
                        if not ('/'+self._trajectory_name) in self._hdf5file:
                            raise ValueError('File %s does not contain trajectory %s.'
                                             % (self._filename, self._trajectory_name))

                        try:
                            self._trajectory_group = self._hdf5file.get_node('/'+
                                                                            self._trajectory_name)
                        except AttributeError:
                            self._trajectory_group = self._hdf5file.getNode('/'+
                                                                            self._trajectory_name)
                    else:
                        raise ValueError('Please specify a name of a trajectory to load or its '
                                         'index, otherwise I cannot open one.')

                else:
                    raise RuntimeError('You shall not pass!')

                return True
        else:
            return False

    def _srvc_closing_routine(self, closing):
        """Routine to close an hdf5 file

        The file is closed only when `closing=True`. `closing=True` means that
        the file was opened in the current highest recursion level. This prevents re-opening
        and closing of the file if `store` or `load` are called recursively.

        """
        if closing and self._hdf5file is not None and self._hdf5file.isopen:
            self._hdf5file.flush()
            self._hdf5file.close()
            self._hdf5file = None
            self._trajectory_group = None
            self._trajectory_name = None
            self._trajectory_index=None
            return True
        else:
            return False

    def _srvc_extract_file_information(self,kwargs):
        """Extracts file informmation from kwargs.

        Note that `kwargs` is not passed as `**kwargs` in order to also
        `pop` the elements on the level of the function calling `_srvc_extract_file_information`.

        """
        if 'filename' in kwargs:
            self._filename=kwargs.pop('filename')

        if 'file_title' in kwargs:
            self._file_title = kwargs.pop('file_title')

        if 'trajectory_name' in kwargs:
            self._trajectory_name = kwargs.pop('trajectory_name')

        if 'trajectory_index' in kwargs:
            self._trajectory_index = kwargs.pop('trajectory_index')

    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        return result

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('pypet.storageservice_HDF5StorageService')


    ########################### MERGING ###########################################################

    def _trj_backup_trajectory(self, traj, backup_filename=None):
        """Backs up a trajectory.

        :param traj: Trajectory that should be backed up

        :param backup_filename:

            Path and filename of backup file. If None is specified the storage service
            defaults to `path_to_trajectory_hdf5_file/backup_trajectory_name.hdf`.

        """
        self._logger.info('Storing backup of %s.' % traj.v_name)

        mypath, filename = os.path.split(self._filename)

        if backup_filename is None:
            backup_filename ='%s/backup_%s.hdf5' % (mypath,traj.v_name)

        try:
            backup_hdf5file = pt.open_file(filename=backup_filename, mode='a', title=backup_filename)
        except AttributeError:
            backup_hdf5file = pt.openFile(filename=backup_filename, mode='a', title=backup_filename)

        if ('/'+self._trajectory_name) in backup_hdf5file:

            raise ValueError('I cannot backup  `%s` into file `%s`, there is already a '
                             'trajectory with that name.' % (traj.v_name,backup_filename))

        backup_root = backup_hdf5file.root

        self._trajectory_group._f_copy(newparent=backup_root, recursive=True)

        backup_hdf5file.flush()
        backup_hdf5file.close()

        self._logger.info('Finished backup of %s.' % traj.v_name)

    def _trj_copy_table_entries(self, rename_dict, other_trajectory_name):
        """Copy the overview table entries from another trajectory into the current one.

        :param rename_dict:

            Dictionary with old names (keys) and new names (values).

        :param other_trajectory_name:

            Name of other trajectory

        """
        self._trj_copy_table_entries_from_table_name('derived_parameters_runs',rename_dict,other_trajectory_name)
        self._trj_copy_table_entries_from_table_name('results_trajectory',rename_dict,other_trajectory_name)
        self._trj_copy_table_entries_from_table_name('results_runs',rename_dict,other_trajectory_name)

        self._trj_copy_summary_table_entries_from_table_name('results_runs_summary', rename_dict, other_trajectory_name)
        self._trj_copy_summary_table_entries_from_table_name('derived_parameters_runs_summary', rename_dict, other_trajectory_name)

    def _trj_copy_summary_table_entries_from_table_name(self, tablename, rename_dict, other_trajectory_name):
        """Copy a the summary table entries from another trajectory into the current one

        :param tablename:

            Name of overview table

        :param rename_dict:

            Dictionary with old names (keys) and new names (values).

        :param other_trajectory_name:

            Name of other trajectory

        """
        count_dict = {} # Dictionary containing the number of items that are merged for
                        # a particular result summary

        for old_name in rename_dict:
            # Check for the summary entry in the other trajectory
            # In the overview table location literally contains `run_XXXXXXXX`
            run_mask = pypetconstants.RUN_NAME+'X'*pypetconstants.FORMAT_ZEROS

            old_split_name = old_name.split('.')
            old_split_name[1]=run_mask
            old_mask_name = '.'.join(old_split_name)


            if not old_mask_name in count_dict:
                count_dict[old_mask_name]=0

            count_dict[old_mask_name] += 1


        try:
            # get the other table
            try:
                other_table = self._hdf5file.get_node('/'+other_trajectory_name+'/overview/'+tablename)
            except AttributeError:
                other_table = self._hdf5file.getNode('/'+other_trajectory_name+'/overview/'+tablename)

            new_row_dict={} # Dictionary with full names as keys and summary row dicts as values


            for row in other_table:
                # Iterate through the rows of the overview table
                location = row['location']
                name = row['name']
                full_name = location+'.'+name

                # If we need the overview entry mark it for merging
                if full_name in count_dict:
                    new_row_dict[full_name] = self._trj_read_out_row(other_table.colnames, row)

            # Get the summary table in the current trajectory
            try:
                table= self._hdf5file.get_node('/'+self._trajectory_name+'/overview/'+tablename)
            except AttributeError:
                table= self._hdf5file.getNode('/'+self._trajectory_name+'/overview/'+tablename)

            for row in table:
                # Iterate through the current rows
                location = row['location']
                name = row['name']
                full_name = location+'.'+name

                # Update the number of items according to the number or merged items
                if full_name in new_row_dict:
                    row['number_of_items'] = row['number_of_items'] + count_dict[full_name]
                    # Delete used row dicts
                    del new_row_dict[full_name]
                    row.update()

            table.flush()
            self._hdf5file.flush()

            # Finally we need to create new rows for results that are part of the other
            # trajectory but which could not be found in the current one
            for key in sorted(new_row_dict.keys()):
                not_inserted_row = new_row_dict[key]
                new_row = table.row

                for col_name in table.colnames:

                    # This is to allow backwards compatibility
                    if col_name == 'example_item_run_name' and not col_name in other_table.colnames:
                        continue

                    if col_name == 'example_item_run_name':
                        # The example item run name has changed due to merging
                        old_run_idx = not_inserted_row[col_name]
                        old_run_name = pypetconstants.FORMATTED_RUN_NAME % old_run_idx
                        new_run_name = rename_dict[old_run_name]
                        new_run_idx = int(new_run_name.split(pypetconstants.RUN_NAME)[1])
                        new_row[col_name] = new_run_idx
                    else:
                        new_row[col_name] = not_inserted_row[col_name]

                new_row.append()

            table.flush()
            self._hdf5file.flush()

        except pt.NoSuchNodeError:
            self._logger.warning('Did not find table `%s` in one of the trajectories,'
                              ' skipped copying.' % tablename)

    @staticmethod
    def _trj_read_out_row(colnames,row):
        """Reads out a row and returns a dictionary containing the row content.

        :param colnames: List of column names
        :param row:  A pytables table row
        :return: A dictionary with colnames as keys and content as values

        """
        result_dict= {}
        for colname in colnames:
            result_dict[colname]=row[colname]

        return result_dict

    def _trj_copy_table_entries_from_table_name(self,tablename, rename_dict,other_trajectory_name):
        """Copy overview tables (not summary) from other trajectory into the current one.

        :param tablename:

            Name of overview table

        :param rename_dict:

            Dictionary with old names (keys) and new names (values).

        :param other_trajectory_name:

            Name of other trajectory

        """
        try:
            try:
                other_table = self._hdf5file.get_node('/'+other_trajectory_name+'/overview/'+tablename)
            except AttributeError:
                other_table = self._hdf5file.getNode('/'+other_trajectory_name+'/overview/'+tablename)

            new_row_dict={}

            for row in other_table.iterrows():
                # Iterate through the summary table
                location = row['location']
                name = row['name']
                full_name = location+'.'+name


                if full_name in rename_dict:
                    # If the item is marked for merge we need to copy its overview info
                    read_out_row = self._trj_read_out_row(other_table.colnames,row)
                    new_location = rename_dict[full_name].split('.')
                    new_location = '.'.join(new_location[0:-1])
                    read_out_row['location'] = new_location
                    new_row_dict[rename_dict[full_name]] = read_out_row

            try:
                table= self._hdf5file.get_node('/'+self._trajectory_name+'/overview/'+tablename)
            except AttributeError:
                table= self._hdf5file.getNode('/'+self._trajectory_name+'/overview/'+tablename)

            # Insert data into the current overview table
            for row in table.iterrows():
                location = row['location']
                name = row['name']
                full_name = location+'.'+name

                if full_name in new_row_dict:
                    for col_name in table.colnames:
                        row[col_name] = new_row_dict[full_name][col_name]

                    del new_row_dict[full_name]
                    row.update()

            table.flush()
            self._hdf5file.flush()

            # It may be the case that the we need to insert a new row
            for key in sorted(new_row_dict.keys()):
                not_inserted_row = new_row_dict[key]
                new_row = table.row

                for col_name in table.colnames:
                    new_row[col_name] = not_inserted_row[col_name]

                new_row.append()

            table.flush()
            self._hdf5file.flush()

        except pt.NoSuchNodeError:
            self._logger.warning('Did not find table `%s` in one of the trajectories,'
                              ' skipped copying.' % tablename)

    def _trj_merge_trajectories(self,other_trajectory_name,rename_dict,move_nodes=False,
                                delete_trajectory=False):
        """Merges another trajectory into the current trajectory (as in self._trajectory_name).

        :param other_trajectory_name: Name of other trajectory
        :param rename_dict: Dictionary with old names (keys) and new names (values).
        :param move_nodes: Whether to move hdf5 nodes or copy them
        :param delete_trajectory: Whether to delete the other trajectory

        """
        if not ('/'+other_trajectory_name) in self._hdf5file:
            raise ValueError('Cannot merge `%s` and `%s`, because the second trajectory cannot '
                             'be found in my file.')

        for old_name, new_name in rename_dict.iteritems():
            # Iterate over all items that need to be merged
            split_name = old_name.split('.')
            old_location = '/'+other_trajectory_name+'/'+'/'.join(split_name)


            split_name = new_name.split('.')
            new_location = '/'+self._trajectory_name+'/'+'/'.join(split_name)

            # Get the data from the other trajectory
            try:
                old_group = self._hdf5file.get_node(old_location)
            except AttributeError:
                old_group = self._hdf5file.getNode(old_location)

            for node in old_group:
                # Now move or copy the data
                if move_nodes:
                    try:
                        self._hdf5file.move_node(where=old_location, newparent=new_location,
                                             name=node._v_name, createparents=True )
                    except AttributeError:
                        self._hdf5file.moveNode(where=old_location, newparent=new_location,
                                             name=node._v_name, createparents=True )
                else:
                    try:
                        self._hdf5file.copy_node(where=old_location, newparent=new_location,
                                              name=node._v_name, createparents=True,
                                              recursive=True)
                    except AttributeError:
                        self._hdf5file.copyNode(where=old_location, newparent=new_location,
                                              name=node._v_name, createparents=True,
                                              recursive=True)

            # And finally copy the attributes of leaf nodes
            # Attributes of group nodes are NOT copied, this has to be done
            # by the trajectory
            try:
                old_group._v_attrs._f_copy(where = self._hdf5file.get_node(new_location))
            except AttributeError:
                old_group._v_attrs._f_copy(where = self._hdf5file.getNode(new_location))

        self._trj_copy_table_entries(rename_dict, other_trajectory_name)

        if delete_trajectory:
            try:
                 self._hdf5file.remove_node(where='/', name=other_trajectory_name, recursive = True)
            except AttributeError:
                self._hdf5file.removeNode(where='/', name=other_trajectory_name, recursive = True)


    def _trj_prepare_merge(self, traj, changed_parameters):
        """Prepares a trajectory for merging.

        This function will already store extended parameters.

        :param traj: Target of merge
        :param changed_parameters: List of extended parameters (i.e. their names).

        """

        # Update meta information
        infotable = getattr(self._overview_group,'info')
        insert_dict = self._all_extract_insert_dict(traj,infotable.colnames)
        self._all_add_or_modify_row(traj.v_name,insert_dict,infotable,index=0,
                                    flags=(HDF5StorageService.MODIFY_ROW,))


        # Store extended parameters
        for param_name in changed_parameters:
            param = traj.f_get(param_name)
            self.store(pypetconstants.UPDATE_LEAF,param)

        # Increase the run table by the number of new runs
        run_table = getattr(self._overview_group,'runs')
        actual_rows = run_table.nrows
        self._trj_fill_run_table_with_dummys(traj,actual_rows)


        try:
            add_table = traj.f_get('config.hdf5.overview.explored_parameters_runs').f_get()
        except AttributeError:
            add_table=True

        # Extract parameter summary and if necessary create new explored parameter tables
        # in the result groups
        for run_name in traj.f_get_run_names():
            run_info = traj.f_get_run_information(run_name)
            run_info['name'] = run_name
            idx = run_info['idx']


            traj._set_explored_parameters_to_idx(idx)

            create_run_group = ('results.%s' % run_name) in traj

            run_summary=self._srn_add_explored_params(run_name,traj._explored_parameters.values(),
                                                      add_table, create_run_group=create_run_group)


            run_info['parameter_summary'] = run_summary

            self._all_add_or_modify_row(run_name,run_info,run_table,index=idx,
                                        flags=(HDF5StorageService.MODIFY_ROW,))

        traj.f_restore_default()


    def _trj_remove_incomplete_runs(self,traj):
        """Deletes all data related to incompleted runs."""
        self._logger.info('Removing incomplete runs.')
        count = 0

        dparams_group = self._trajectory_group.derived_parameters
        result_group = self._trajectory_group.results

        for run_name, info_dict in traj._run_information.iteritems():
            completed = info_dict['completed']

            if completed == 0:
                if run_name in dparams_group or run_name in result_group:
                    self._logger.info('Removing run %s.' % run_name)
                    count +=1

                if run_name in dparams_group:
                    try:
                        dparams_group._f_get_child(run_name)._f_remove(recursive=True)
                    except AttributeError:
                        dparams_group._f_getChild(run_name)._f_remove(recursive=True)

                if run_name in result_group:
                    try:
                        result_group._f_get_child(run_name)._f_remove(recursive=True)
                    except AttributeError:
                        result_group._f_getChild(run_name)._f_remove(recursive=True)

        self._logger.info('Finished removal of incomplete runs, removed %d runs.' % count)


    ######################## LOADING A TRAJECTORY #################################################

    def _trj_load_trajectory(self,msg, traj, as_new, load_parameters,load_derived_parameters,
                             load_results, force):
        """Loads a single trajectory from a given file.


        :param stuff_to_load: The trajectory

        :param as_new: Whether to load trajectory as new

        :param load_parameters: How to load parameters and config

        :param load_derived_parameters: How to load derived parameters

        :param load_results: How to load results

        :param force: Force load in case there is a pypet version mismatch

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

            The skeleton and annotations are updated, i.e. only items that are not
            currently part of your trajectory are loaded empty.

        :const:`pypet.pypetconstants.UPDATE_DATA`: (-2) Like (2)

            Only items that are currently not in your trajectory are loaded with data.


        If `as_new=True` the old trajectory is loaded into the new one, only parameters can be
        loaded. If `as_new=False` the current trajectory is completely replaced by the one
        on disk, i.e. the name from disk, the timestamp, etc. are assigned to `traj`.

        """
        # Some validity checks, if `as_new` is used correctly
        if (as_new and (load_derived_parameters != pypetconstants.LOAD_NOTHING or load_results !=
                        pypetconstants.LOAD_NOTHING)):
            raise ValueError('You cannot load a trajectory as new and load the derived '
                                 'parameters and results. Only parameters are allowed.')


        if as_new and load_parameters != pypetconstants.LOAD_DATA:
            raise ValueError('You cannot load the trajectory as new and not load the data of '
                                 'the parameters.')

        if not as_new:
            traj._stored=True

        # Loads meta data like the name, timestamps etc.
        self._trj_load_meta_data(traj,as_new,force)

        # Load the annotations in case they have not been loaded before
        if traj.v_annotations.f_is_empty():
            self._ann_load_annotations(traj, self._trajectory_group)

        for what,loading in ( ('config',load_parameters),
                             ('parameters',load_parameters),
                             ('derived_parameters',load_derived_parameters),
                             ('results',load_results) ):
            # If the trajectory is loaded as new, we don't care about old config stuff
            # and only load the parameters
            if as_new and what == 'config':
                loading=pypetconstants.LOAD_NOTHING

            # Load the subbranches recursively
            if loading != pypetconstants.LOAD_NOTHING:
                self._trj_load_sub_branch(traj,traj,what,self._trajectory_group,loading)

    def _trj_load_meta_data(self,traj, as_new, force):
        """Loads meta information about the trajectory

        Checks if the version number does not differ from current pypet version
        Loads, comment, timestamp, name, version from disk in case trajectory is not loaded
        as new. Updates the run information as well.

        """
        metatable = self._overview_group.info
        metarow = metatable[0]

        version = metarow['version']

        self._trj_check_version(version,force)

        if as_new:
            length = int(metarow['length'])
            for irun in range(length):
                traj._add_run_info(irun)
        else:
            traj._comment = str(metarow['comment'])
            traj._timestamp = float(metarow['timestamp'])
            traj._time = str(metarow['time'])
            traj._name = str(metarow['name'])
            traj._version = str(metarow['version'])

            single_run_table = self._overview_group.runs

            # Load the run information about the single runs
            for row in single_run_table.iterrows():
                name = str(row['name'])
                idx = int(row['idx'])
                timestamp = float(row['timestamp'])
                time = str(row['time'])
                completed = int(row['completed'])
                summary=str(row['parameter_summary'])
                hexsha = str(row['short_environment_hexsha'])


                # To allow backwards compatibility we need this try catch block
                try:
                    runtime = str(row['runtime'])
                    finish_timestamp = float(row['finish_timestamp'])
                except KeyError as ke:
                    runtime=''
                    finish_timestamp=0.0
                    self._logger.warning('Could not load runtime, ' + repr(ke))

                traj._single_run_ids[idx] = name
                traj._single_run_ids[name] = idx

                info_dict = {}
                info_dict['idx'] = idx
                info_dict['timestamp'] = timestamp
                info_dict['time'] = time
                info_dict['completed'] = completed
                info_dict['name'] = name
                info_dict['parameter_summary'] = summary
                info_dict['short_environment_hexsha'] = hexsha
                info_dict['runtime'] = runtime
                info_dict['finish_timestamp'] = finish_timestamp

                traj._run_information[name] = info_dict

    def _trj_load_sub_branch(self, traj, traj_node, branch_name, hdf5_group, load_data):
        """Loads data starting from a node along a branch and starts recursively loading
        all data at end of branch.

        :param traj: The trajectory

        :param traj_node: The node from where loading starts

        :param branch_name:

            A branch along which loading progresses. Colon Notation is used:
            'group1.group2.group3' loads 'group1', then 'group2', then 'group3' and then finally
            recursively all children and children's children below 'group3'

        :param hdf5_group:

            HDF5 node in the file corresponding to `traj_node`.

        :param load_data:

            How to load the data

        """
        split_names = branch_name.split('.')

        final_group_name = split_names.pop()

        for name in split_names:
            # First load along the branch
            hdf5_group = getattr(hdf5_group,name)

            if not name in traj:
                traj_node=traj_node._nn_interface._add_from_group_name(traj_node, name)

            else:
                traj_node=traj_node._children[name]

            # Load annotations if they are empty
            if traj_node.v_annotations.f_is_empty():
                self._ann_load_annotations(traj_node, hdf5_group)

        # Then load recursively all data in the last group and below
        hdf5_group = getattr(hdf5_group,final_group_name)
        self._tree_load_recursively(traj,traj_node,hdf5_group,load_data)

    def _trj_check_version( self, version, force):
        """Checks for version mismatch

        Raises a VersionMismatchError if version of loaded trajectory and current pypet version
        do not match. In case of `force=True` error is not raised only a warning is emitted.

        """
        if version != VERSION and not force:
            raise pex.VersionMismatchError('Current pypet version is %s but your trajectory'
                                            ' was created with version %s.'
                                            ' Use >>force=True<< to perform your load regardless'
                                            ' of version mismatch.' %
                                           (VERSION, version))
        elif version != VERSION :
            self._logger.warning('Current pypet version is %s but your trajectory'
                                            ' was created with version %s.'
                                            ' Yet, you enforced the load, so I will'
                                            ' handle the trajectory despite the'
                                            ' version mismatch.' %
                                           (VERSION , version))


    #################################### Storing a Trajectory ####################################

    def _trj_fill_run_table_with_dummys(self, traj, start=0):
        """Fills the `run` overview table with dummy information.

        The table is later on filled by the single runs with the real information.
        `start` specifies how large the table is when calling this function.

        The table might not be emtpy because a trajectory is enlarged due to expanding.

        """
        runtable = getattr(self._overview_group,'runs')

        for idx in range(start, len(traj)):
            name = traj.f_idx_to_run(idx)
            insert_dict = traj.f_get_run_information(name)

            self._all_add_or_modify_row('Dummy Row', insert_dict, runtable,
                                        flags=(HDF5StorageService.ADD_ROW,))

        runtable.flush()

    def _trj_store_meta_data(self, traj):
        """ Stores general information about the trajectory in the hdf5file.

        The `info` table will contain the name of the trajectory, it's timestamp, a comment,
        the length (aka the number of single runs), and the current version number of pypet.

        Also prepares the desired overview tables and fills the `run` table with dummies.

        """
        # Description of the `info` table
        descriptiondict={'name': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH, pos=0),
                         'time': pt.StringCol(len(traj.v_time), pos=1),
                         'timestamp' : pt.FloatCol(pos=3),
                         'comment':  pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH, pos=4),
                         'length':pt.IntCol(pos=2),
                         'version' : pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH,pos=5)}
                         # 'loaded_from' : pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH)}

        infotable = self._all_get_or_create_table(where=self._overview_group, tablename='info',
                                               description=descriptiondict, expectedrows=len(traj))

        insert_dict = self._all_extract_insert_dict(traj,infotable.colnames)
        self._all_add_or_modify_row(traj.v_name,insert_dict,infotable,index=0,
                                    flags=(HDF5StorageService.ADD_ROW,HDF5StorageService.MODIFY_ROW))

        # Description of the `run` table
        rundescription_dict = {'name': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH,pos=1),
                         'time': pt.StringCol(len(traj.v_time),pos=2),
                         'timestamp' : pt.FloatCol(pos=3),
                         'idx' : pt.IntCol(pos=0),
                         'completed' : pt.IntCol(pos=8),
                         'parameter_summary' : pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH,
                                                            pos=6),
                         'short_environment_hexsha' : pt.StringCol(7,pos=7),
                         'finish_timestamp' : pt.FloatCol(pos=4),
                         'runtime' : pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_RUNTIME_LENGTH,
                                                  pos=5)}

        runtable = self._all_get_or_create_table(where=self._overview_group,
                                                 tablename='runs',
                                                 description=rundescription_dict)

        # Fill table with dummy entries starting from the current table size
        actual_rows = runtable.nrows
        self._trj_fill_run_table_with_dummys(traj, actual_rows)

        # Store the annotations in the trajectory node
        self._ann_store_annotations(traj,self._trajectory_group)

        # Prepare the overview tables
        tostore_tables=[]

        for name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():

            # Check if we want the corresponding overview table
            # If the trajectory does not contain information about the table
            # we assume it should be created.
            try:
                if traj.f_get(name).f_get():
                    tostore_tables.append(table_name)
            except AttributeError:
                tostore_tables.append(table_name)

        for table_name in tostore_tables:
            # Prepare the tables desciptions, depending on which overview table we create
            # we need different columns
            paramdescriptiondict ={}
            expectedrows=0

            # Every overview table has a name and location column
            paramdescriptiondict['location']= pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH,
                                                           pos=1)
            paramdescriptiondict['name']= pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH,
                                                       pos=0)
            if not table_name == 'explored_parameters':
                paramdescriptiondict['value']=pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH)

            if table_name == 'config':
                expectedrows= len(traj._config)

            if table_name == 'parameters':
                expectedrows= len(traj._parameters)

            if table_name == 'explored_parameters':
                paramdescriptiondict['range']= pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_ARRAY_LENGTH)
                expectedrows=len(traj._explored_parameters)

            if table_name == 'results_trajectory':
                expectedrows=len(traj._results)

            if table_name == 'derived_parameters_trajectory':
                expectedrows=len(traj._derived_parameters)

            if table_name in ['derived_parameters_trajectory','results_trajectory',
                                  'derived_parameters_runs_summary', 'results_runs_summary',
                                  'config', 'parameters', 'explored_parameters']:
                if table_name.startswith('derived') or table_name.endswith('parameters'):
                    paramdescriptiondict['length']= pt.IntCol()

                paramdescriptiondict['comment']= pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH)

            if table_name.endswith('summary'):
                paramdescriptiondict['number_of_items']= pt.IntCol(dflt=1)
                paramdescriptiondict['example_item_run_name'] = \
                    pt.StringCol(len(pypetconstants.RUN_NAME)+pypetconstants.FORMAT_ZEROS+3,pos=2)

            # Check if the user provided an estimate of the amount of results per run
            # This can help to speed up storing
            if table_name.startswith('derived_parameters_runs'):

                try:
                    expectedrows = traj.f_get('config.hdf5.derived_parameters_per_run').f_get()
                except AttributeError:
                    expectedrows = 0

                if not expectedrows <= 0:
                    if not table_name.endswith('summary'):
                        expectedrows *= len(traj)

            if table_name.startswith('results_runs'):

                try:
                    expectedrows = traj.f_get('config.hdf5.results_per_run').f_get()
                except AttributeError:
                    expectedrows = 0

                if not expectedrows <=0:
                    if not table_name.endswith('summary'):
                        expectedrows *= len(traj)

            if expectedrows>0:
                paramtable = self._all_get_or_create_table(where=self._overview_group,
                                                           tablename=table_name,
                                                           description=paramdescriptiondict,
                                                           expectedrows=expectedrows)
            else:
                paramtable = self._all_get_or_create_table(where=self._overview_group,
                                                           tablename=table_name,
                                                           description=paramdescriptiondict)

            # Index the summary tables for faster look up
            # They are searched by the individual runs later on
            if table_name.endswith('summary'):
                paramtable.autoIndex=True
                if not paramtable.indexed:
                    try:
                        paramtable.cols.location.create_index()
                        paramtable.cols.name.create_index()
                    except AttributeError:
                        paramtable.cols.location.createIndex()
                        paramtable.cols.name.createIndex()


            paramtable.flush()

    def _trj_store_trajectory(self, traj):
        """ Stores a trajectory to an hdf5 file

        Stores all groups, parameters and results

        """
        self._logger.info('Start storing Trajectory `%s`.' % self._trajectory_name)

        # In case we accidentally chose a trajectory name that already exist
        # We do not want to mess up the stored trajectory but raise an Error
        if not traj._stored and self._trajectory_group._v_nchildren>0:
            raise RuntimeError('You want to store a completely new trajectory with name'
                               ' `%s` but this trajectory is already found in file `%s`' %
                               (traj.v_name,self._filename))

        if 'config.hdf5.purge_duplicate_comments' in traj:
            self._purge_duplicate_comments = traj.f_get('config.hdf5.purge_duplicate_comments').f_get()
        else:
            self._purge_duplicate_comments=True

        # Store meta information
        self._trj_store_meta_data(traj)

        # Store recursively the config subtree
        self._tree_store_recursively(pypetconstants.LEAF,traj.config,self._trajectory_group)

        # If we restore a trajectory it could be the case that it was expanded,
        # so we need to choose the appropriate message to update enlarged parameters
        if traj._stored:
            msg = pypetconstants.UPDATE_LEAF
        else:
            msg = pypetconstants.LEAF

        # Store recursively the parameters subtree
        self._tree_store_recursively(msg,traj.parameters,self._trajectory_group)

        # Store recursively the derived parameters subtree
        self._tree_store_recursively(pypetconstants.LEAF,traj.derived_parameters,
                                     self._trajectory_group)

        # Store recursively the results subtree
        self._tree_store_recursively(pypetconstants.LEAF,traj.results,self._trajectory_group)

        self._logger.info('Finished storing Trajectory `%s`.' % self._trajectory_name)

    def _trj_store_sub_branch(self, msg, traj_node, branch_name, hdf5_group):
        """Stores data starting from a node along a branch and starts recursively loading
        all data at end of branch.

        :param msg: How to store leaf nodes, either 'LEAF' or 'UPDATE_LEAF'

        :param traj_node: The node where storing starts

        :param branch_name:

            A branch along which storing progresses. Colon Notation is used:
            'group1.group2.group3' loads 'group1', then 'group2', then 'group3', and then finally
            recursively all children and children's children below 'group3'.

        :param hdf5_group:

            HDF5 node in the file corresponding to `traj_node`

        """

        split_names = branch_name.split('.')

        leaf_name = split_names.pop()

        for name in split_names:
            # Store along a branch
            traj_node = traj_node._children[name]

            if not hasattr(hdf5_group,name):
                try:
                    hdf5_group=self._hdf5file.create_group(where=hdf5_group,name=name)
                except AttributeError:
                    hdf5_group=self._hdf5file.createGroup(where=hdf5_group,name=name)
            else:
                hdf5_group=getattr(hdf5_group,name)

            self._ann_store_annotations(traj_node,hdf5_group)

        # Store final group and recursively everything below it
        traj_node = traj_node._children[leaf_name]
        self._tree_store_recursively(msg,traj_node,hdf5_group)


    ########################  Storing and Loading Sub Trees #######################################

    def _tree_store_tree(self, traj_node, recursive):
        """Stores a node and potentially recursively all nodes below

        :param traj_node: Node to store

        :param recursive: Whether to store everything below `traj_node`.

        """
        location = traj_node.v_location

        # Get parent hdf5 node
        hdf5_location = location.replace('.','/')
        try:
            try:
                parent_hdf5_node = self._hdf5file.get_node(where=self._trajectory_group,
                                                          name=hdf5_location)
            except AttributeError:
                parent_hdf5_node = self._hdf5file.getNode(where=self._trajectory_group,
                                                          name=hdf5_location)
        except pt.NoSuchNodeError:
            self._logger.error('Cannot store `%s` the parental hdf5 node with path `%s` does '
                               'not exist! Store the parental node first!' %
                               (traj_node.v_name,hdf5_location))
            raise

        # Store node and potentially everything below it
        self._tree_store_recursively(pypetconstants.LEAF, traj_node, parent_hdf5_node, recursive)

    def _tree_load_tree(self, parent_traj_node, child_name, recursive, load_data, trajectory):
        """Loads a specific tree node and potentially all nodes below

        :param parent_traj_node: parent node of node to load in trajectory

        :param child_name: Name (!) of node to be loaded

        :param recursive: Whether to load everything below the child

        :param load_data: How to load the data

        :param trajectory: The trajectory object

        """
        if parent_traj_node.v_is_root:
            full_child_name = child_name
        else:
            full_child_name = parent_traj_node.v_full_name+'.'+child_name

        hdf5_node_name =full_child_name.replace('.','/')

        # Get child node to load
        try:
            try:
                 hdf5_node = self._hdf5file.get_node(where=self._trajectory_group,name = hdf5_node_name)
            except AttributeError:
                hdf5_node = self._hdf5file.getNode(where=self._trajectory_group,name = hdf5_node_name)
        except pt.NoSuchNodeError:
            self._logger.error('Cannot load `%s` the hdf5 node `%s` does not exist!'
                                % (child_name,hdf5_node_name))

            raise

        # Load data of child and potentially everything below it
        self._tree_load_recursively(trajectory,parent_traj_node,hdf5_node,load_data,recursive)

    def _tree_load_recursively(self, traj, parent_traj_node, hdf5group,
                              load_data=pypetconstants.UPDATE_SKELETON, recursive=True):
        """Loads a node from hdf5 file and if desired recursively everything below

        :param traj: The trajectory object
        :param parent_traj_node: The parent node whose child should be loaded
        :param hdf5group: The hdf5 group containing the child to be loaded
        :param load_data: How to load the data
        :param recursive: Whether loading recursively below hdf5group

        """
        path_name = parent_traj_node.v_full_name
        name = hdf5group._v_name
        is_leaf = self._all_get_from_attrs(hdf5group,HDF5StorageService.LEAF)

        if is_leaf:
            # In case we have a leaf node, we need to check if we have to create a new
            # parameter or result
            full_name = '%s.%s' % (path_name,name)

            in_trajectory =  name in parent_traj_node._children

            if in_trajectory:
                instance=parent_traj_node._children[name]

                # Load annotations if they are empty
                if instance.v_annotations.f_is_empty():
                    self._ann_load_annotations(instance, hdf5group)

                # If we want to update the skeleton and the item exists we're good
                if load_data == pypetconstants.UPDATE_SKELETON :
                    return

                # If we want to update data and the item already contains some we're good
                if (not instance.f_is_empty()
                    and load_data == pypetconstants.UPDATE_DATA):
                    return

            # Otherwise we need to create a new instance
            if not in_trajectory or load_data==pypetconstants.LOAD_DATA:

                class_name = self._all_get_from_attrs(hdf5group,HDF5StorageService.CLASS_NAME)
                comment = self._all_get_from_attrs(hdf5group,HDF5StorageService.COMMENT)
                range_length = self._all_get_from_attrs(hdf5group,HDF5StorageService.LENGTH)

                if not range_length is None and range_length >1 and range_length != len(traj):
                        raise RuntimeError('Something is completely odd. You load parameter'
                                               ' `%s` of length %d into a trajectory of length'
                                               ' %d. They should be equally long!'  %
                                               (full_name,range_length,len(traj)))

                # Create the instance with the appropriate constructor
                class_constructor = traj._create_class(class_name)
                instance = class_constructor(name, comment=comment)

                # Add the instance to the trajectory tree
                parent_traj_node._nn_interface._add_from_leaf_instance(parent_traj_node,instance)

                # If it has a range we add it to the explored parameters
                if range_length:
                    traj._explored_parameters[instance.v_full_name]=instance

                self._ann_load_annotations(instance, node=hdf5group)

            if load_data in [pypetconstants.LOAD_DATA, pypetconstants.UPDATE_DATA]:
                # Load data into the instance
                self._prm_load_parameter_or_result(instance, _hdf5_group=hdf5group)

        else:
            # Else we are dealing with a group node
            if not name in parent_traj_node._children:
                # If the group does not exist create it
                new_traj_node = parent_traj_node._nn_interface._add_from_group_name(
                                                                        parent_traj_node, name)
            else:
                new_traj_node = parent_traj_node._children[name]

            # Load annotations if they are empty
            if new_traj_node.v_annotations.f_is_empty():
                self._ann_load_annotations(new_traj_node, hdf5group)

            if recursive:
                # We load recursively everything below it
                try:
                    for new_hdf5group in hdf5group._f_iter_nodes(classname='Group'):
                        self._tree_load_recursively(traj,new_traj_node,new_hdf5group,load_data)
                except AttributeError:
                    for new_hdf5group in hdf5group._f_iterNodes(classname='Group'):
                        self._tree_load_recursively(traj,new_traj_node,new_hdf5group,load_data)

    def _tree_store_recursively(self,msg, traj_node, parent_hdf5_group, recursive = True):
        """Stores a node to hdf5 and if desired stores recursively everything below it.

        :param msg: How to store leaf nodes, either 'LEAF' or 'UPDATE_LEAF'
        :param traj_node: Node to be stored
        :param parent_hdf5_group: Parent hdf5 groug
        :param recursive: Whether to store recursively the subtree

        """

        name = traj_node.v_name

        # If the node does not exist in the hdf5 file create it
        if not hasattr(parent_hdf5_group,name):
            try:
                new_hdf5_group = self._hdf5file.create_group(where=parent_hdf5_group,name=name)
            except AttributeError:
                new_hdf5_group = self._hdf5file.createGroup(where=parent_hdf5_group,name=name)

            msg = pypetconstants.UPDATE_LEAF
        else:
            new_hdf5_group = getattr(parent_hdf5_group,name)

        if traj_node.v_is_leaf:
            # If we have a leaf node, store it as a parameter or result
            self._prm_store_parameter_or_result(msg, traj_node, _hdf5_group=new_hdf5_group)

        else:
            # Else store it as a group node
            self._grp_store_group(traj_node,_hdf5_group=new_hdf5_group)

            if recursive:
                # And if desired store recursively the subtree
                for child in traj_node._children.itervalues():
                    self._tree_store_recursively(msg,child,new_hdf5_group)


    ######################## Storing a Single Run ##########################################

    def _srn_store_single_run(self,single_run):
        """ Stores a single run instance to disk"""

        idx = single_run.v_idx
        self._logger.info('Start storing run %d with name %s.' % (idx,single_run.v_name))

        # Store the two subbranches `results.ru_XXXXXXXXX` and 'derived_parameters.run_XXXXXXXXX`
        # created by the current run
        for branch in ('results','derived_parameters'):
            branch_name = branch +'.'+single_run.v_name
            if branch_name in single_run:
                self._trj_store_sub_branch(pypetconstants.LEAF,single_run,
                                           branch_name,self._trajectory_group)

        # Check if we want explored parameters overview tables.
        # If we do not know whether to build them, just do it
        try:
            add_table = single_run.f_get('config.hdf5.overview.explored_parameters_runs').f_get()
        except AttributeError:
            add_table = True

        # For better readability and if desired add the explored parameters to the results
        # Also collect some summary information about the explored parameters
        # So we can add this to the `run` table
        run_summary = self._srn_add_explored_params(single_run.v_name,
                                                    single_run._explored_parameters.values(),
                                                    add_table)

        # Finally, add the real run information to the `run` table
        table = getattr(self._overview_group,'runs')

        insert_dict = self._all_extract_insert_dict(single_run,table.colnames)
        insert_dict['parameter_summary'] = run_summary
        insert_dict['completed'] = 1

        self._all_add_or_modify_row(single_run, insert_dict, table,
                                    index=idx, flags=(HDF5StorageService.MODIFY_ROW,))


        self._logger.info('Finished storing run %d with name %s' % (idx,single_run.v_name))



    def _srn_add_explored_params(self, run_name, paramlist, add_table, create_run_group=False):
        """If desired adds an explored parameter overview table to the results in each
        single run and summarizes the parameter settings.

        :param run_name: Name of the single run

        :param paramlist: List of explored parameters

        :param add_table: Whether to add the overview table

        :param create_run_group:

            If a group with the particular name should be created if it does not exist.
            Might be necessary when trajectories are merged.

        """

        # Layout of overview table
        paramdescriptiondict={'name': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'value' :pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH)}

        where = 'results.'+run_name

        where = where.replace('.','/')

        if not where in self._trajectory_group:
            if create_run_group:
                try:
                    self._hdf5file.create_group(where =
                                                self._trajectory_group._f_get_child('results'),
                                                name = run_name)
                except AttributeError:
                    self._hdf5file.createGroup(where =
                                                self._trajectory_group._f_getChild('results'),
                                               name = run_name)
            else:
                add_table = False

        if add_table:
            rungroup = getattr(self._trajectory_group,where)

            # Check if the table already exists
            if 'explored_parameters' in rungroup:
                # This can happen if trajectories are merged
                # If the number of explored parameters changed due to merging we
                # need to create the table new in order to show the correct parameters
                paramtable = getattr(rungroup,'explored_parameters')

                # If more parameters became explored we need to create the table new
                if paramtable.nrows != len(paramlist):
                    del paramtable
                    try:
                        self._hdf5file.remove_node(where=rungroup, name='explored_parameters')
                    except AttributeError:
                        self._hdf5file.removeNode(where=rungroup, name='explored_parameters')
                else:
                    add_table=False

            if not 'explored_parameters' in rungroup:
                try:
                    paramtable = self._hdf5file.create_table(where=rungroup,
                                                            name='explored_parameters',
                                                            description=paramdescriptiondict,
                                                            title='explored_parameters')
                except AttributeError:
                    paramtable = self._hdf5file.createTable(where=rungroup,
                                                            name='explored_parameters',
                                                            description=paramdescriptiondict,
                                                            title='explored_parameters')

        runsummary = ''
        paramlist = sorted(paramlist, key= lambda name: name.v_name + name.v_location)
        for idx,expparam in enumerate(paramlist):

            # Create the run summary for the `run` overview
            if idx > 0:
                runsummary += ',   '

            valstr = expparam.f_val_to_str()

            if len(valstr) >= pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH:
                valstr = valstr[0:pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH-3]
                valstr+='...'

            runsummary = runsummary + expparam.v_name + ': ' +valstr

            # If Add the explored parameter overview table if dersired and necessary
            if add_table:
                self._all_store_param_or_result_table_entry(expparam, paramtable,
                                                        (HDF5StorageService.ADD_ROW,))

        return runsummary



    ################# Methods used across Storing and Loading different Items #####################

    def _all_find_param_or_result_entry_and_return_iterator(self, param_or_result, table):
        """Searches for a particular entry in `table` based on the name and location
        of `param_or_result` and returns an iterator over the found rows
        (should contain only a single row).

        """
        location = param_or_result.v_location
        name = param_or_result.v_name

        condvars = {'namecol' : table.cols.name, 'locationcol' : table.cols.location,
                        'name' : name, 'location': location}

        condition = """(namecol == name) & (locationcol == location)"""

        return table.where(condition,condvars=condvars)



    @staticmethod
    def _all_get_table_name(where, creator_name):
        """Returns an overview table name for a given subtree name

        :param where:

            Either `parameters`, `config`, `derived_parameters`, or `results`

        :param creator_name:

            Either `trajectory` or `run_XXXXXXXXX`

        :return: Name of overview table

        """
        if where in ['config','parameters']:
                return where
        else:
            if creator_name == 'trajectory':
                return '%s_trajectory' % where
            else:
                return '%s_runs' % where


    def _all_store_param_or_result_table_entry(self,param_or_result,table, flags,
                                               additional_info=None):
        """Stores a single row into an overview table

        :param param_or_result: A parameter or result instance

        :param table: Table where row will be inserted

        :param flags:

            Flags how to insert into the table. Potential Flags are
            `ADD_ROW`, `REMOVE_ROW`, `MODIFY_ROW`

        :param additional_info:

            Dictionary containing information that cannot be extracted from
            `param_or_result`, but needs to be inserted, too.


        """
        #assert isinstance(table, pt.Table)

        location = param_or_result.v_location
        name = param_or_result.v_name
        fullname = param_or_result.v_full_name


        if flags==(HDF5StorageService.ADD_ROW,):
            # If we are sure we only want to add a row we do not need to search!
            condvars = None
            condition = None
        else:
            # Condition to search for an entry
            condvars = {'namecol' : table.cols.name, 'locationcol' : table.cols.location,
                        'name' : name, 'location': location}

            condition = """(namecol == name) & (locationcol == location)"""


        colnames = set(table.colnames)

        if HDF5StorageService.REMOVE_ROW in flags:
            # If we want to remove a row, we don't need to extract information
            insert_dict={}
        else:
            # Extract information to insert from the instance and the additional info dict
            insert_dict = self._all_extract_insert_dict(param_or_result,colnames,additional_info)

        # Write the table entry
        self._all_add_or_modify_row(fullname,insert_dict,table,condition=condition,
                                    condvars=condvars,flags=flags)


    def _all_get_or_create_table(self,where,tablename,description,expectedrows=None):
        """Creates a new table, or if the table already exists, returns it."""
        where_node = self._hdf5file.getNode(where)

        if not tablename in where_node:
            if not expectedrows is None:
                try:
                    table = self._hdf5file.create_table(where=where_node, name=tablename,
                                                   description=description, title=tablename,
                                                   expectedrows=expectedrows)
                except AttributeError:
                    table = self._hdf5file.createTable(where=where_node, name=tablename,
                                                   description=description, title=tablename,
                                                   expectedrows=expectedrows)
            else:
                try:
                    table = self._hdf5file.create_table(where=where_node, name=tablename,
                                                   description=description, title=tablename)
                except AttributeError:
                    table = self._hdf5file.createTable(where=where_node, name=tablename,
                                                   description=description, title=tablename)
        else:
            try:
                table = where_node._f_get_child(tablename)
            except AttributeError:
                table = where_node._f_getChild(tablename)

        return table

    def _all_get_node_by_name(self,name):
        """Returns an HDF5 node by the path specified in `name`"""
        path_name = name.replace('.','/')
        where = '/%s/%s' %(self._trajectory_name,path_name)

        try:
            return self._hdf5file.get_node(where=where)
        except AttributeError:
            return self._hdf5file.getNode(where=where)

    @staticmethod
    def _all_attr_equals(ptitem, name,value):
        """Checks if a given hdf5 node attribute exists and if so if it matches the `value`."""
        return name in ptitem._v_attrs and ptitem._v_attrs[name] == value

    @staticmethod
    def _all_get_from_attrs(ptitem,name):
        """Gets an attribute `name` from `ptitem`, returns None if attribute does not exist."""
        if name in ptitem._v_attrs:
            return ptitem._v_attrs[name]
        else:
            return None

    def _all_recall_native_type(self,data, ptitem, prefix):
            """Checks if loaded data has the type it was stored in. If not converts it.

            :param data: Data item to be checked and converted
            :param ptitem: HDf5 Node or Leaf from where data was loaded
            :param prefix: Prefix for recalling the data type from the hdf5 node attributes

            :return:

                Tuple, first item is the (converted) `data` item, second boolean whether
                item was converted or not.

            """
            typestr = self._all_get_from_attrs(ptitem,prefix+HDF5StorageService.SCALAR_TYPE)
            type_changed = False

            # Check what the original data type was from the hdf5 node attributes
            if self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                     HDF5StorageService.COLL_SCALAR):
                # Here data item was a scalar

                if isinstance(data, np.ndarray):
                    # If we recall a numpy scalar, pytables loads a 1d array :-/
                    # So we have to change it to a real scalar value
                    data = np.array([data])[0]
                    type_changed = True


                if not typestr is None:
                    # Check if current type and stored type match
                    # if not convert the data
                    if not typestr == repr(type(data)):
                        data = pypetconstants.PARAMETERTYPEDICT[typestr](data)
                        type_changed = True


            elif (self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                         HDF5StorageService.COLL_TUPLE) or
                    self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                           HDF5StorageService.COLL_LIST)):
                # Here data item was originally a tuple or a list

                if not isinstance(data,(list,tuple)):
                    # If the original type cannot be recalled, first convert it to a list
                    type_changed=True
                    data = list(data)

                if len(data)>0:
                    first_item = data[0]
                else:
                    first_item = None

                if not first_item is None:
                    # Check if the type of the first item was conserved
                    if not typestr == repr(type(first_item)):

                        if not isinstance(data, list):
                            data = list(data)

                        # If type was not conserved we need to convert all items
                        # in the list or tuple
                        for idx,item in enumerate(data):
                            data[idx] = pypetconstants.PARAMETERTYPEDICT[typestr](item)
                            type_changed = True

                if self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                          HDF5StorageService.COLL_TUPLE):
                    # If it was originally a tuple we need to convert it back to tuple
                    if not isinstance(data, tuple):
                        data = tuple(data)
                        type_changed = True

            elif self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                          HDF5StorageService.COLL_MATRIX):
                    # Here data item was originally a matrix
                    data = np.matrix(data)
                    type_changed = True

            return data, type_changed

    def _all_add_or_modify_row(self, item_name, insert_dict, table,index=None, condition=None,
                               condvars=None, flags=(ADD_ROW,MODIFY_ROW,)):


        # A row index can be 0 so we have to add this annoying line
        if not index is None and not condition is None:
            raise ValueError('Please give either a condition or an index or none!')
        elif not condition is None:
            row_iterator = table.where(condition,condvars=condvars)
        elif not index is None:
            row_iterator = table.iterrows(index,index+1)
        else:
            row_iterator = None

        try:
            row = row_iterator.next()
        except AttributeError:
            row = None
        except StopIteration:
            row = None


        if ((HDF5StorageService.MODIFY_ROW in flags or HDF5StorageService.ADD_ROW in flags) and
                HDF5StorageService.REMOVE_ROW in flags):
            raise ValueError('You cannot add or modify and remove a row at the same time.')

        if row is None and HDF5StorageService.ADD_ROW in flags:

            row = table.row

            self._all_insert_into_row(row,insert_dict)

            row.append()

        elif row is not None and HDF5StorageService.MODIFY_ROW in flags:

            self._all_insert_into_row(row,insert_dict)

            row.update()

        elif row is not None and HDF5StorageService.REMOVE_ROW in flags:
            rownumber = row.nrow
            multiple_entries = False

            try:
                row_iterator.next()
                multiple_entries = True
            except StopIteration:
                pass

            if  multiple_entries:
                 raise RuntimeError('There is something entirely wrong, `%s` '
                                    'appears more than once in table %s.'
                                    %(item_name,table._v_name))

            try:
                table.remove_rows(rownumber)
            except AttributeError:
                table.removeRows(rownumber)
        else:
            raise ValueError('Something is wrong, you might not have found '
                               'a row, or your flags are not set approprialty')

        ## Check if there are 2 entries which should not happen
        multiple_entries = False
        try:
            row_iterator.next()
            multiple_entries = True
        except StopIteration:
            pass
        except AttributeError:
            pass

        if  multiple_entries:
             raise RuntimeError('There is something entirely wrong, `%s` '
                                'appears more than once in table %s.'
                                %(item_name,table._v_name))

        ## Check if we added something
        if row is None:
            raise RuntimeError('Could not add or modify entries of `%s` in '
                               'table %s' %(item_name,table._v_name))
        table.flush()


    def _all_insert_into_row(self, row, insert_dict):

        for key, val in insert_dict.items():
            try:
                row[key] = val
            except KeyError as ke:
                self._logger.warning('Could not write `%s` into a table, ' % key+ repr(ke))


    def _all_extract_insert_dict(self,item, colnames, additional_info=None):
        insert_dict={}

        if 'length' in colnames:
            insert_dict['length'] = len(item)

        if 'comment' in colnames:
            comment = self._all_cut_string(item.v_comment,
                                           pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH,
                                           self._logger)

            insert_dict['comment'] = comment

        if 'location' in colnames:
            insert_dict['location'] = item.v_location

        if 'name' in colnames:
            insert_dict['name'] = item.v_name

        if 'class_name' in colnames:
            insert_dict['class_name'] = item.f_get_class_name()

        if 'value' in colnames:
            insert_dict['value'] = self._all_cut_string(item.f_val_to_str(),
                                    pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH, self._logger)

        if 'example_item_run_name' in colnames:
            insert_dict['example_item_run_name'] = additional_info['example_item_run_name']

        if 'idx' in colnames:
            insert_dict['idx'] = item.v_idx

        if 'time' in colnames:
            insert_dict['time'] = item.v_time

        if 'timestamp' in colnames:
            insert_dict['timestamp'] = item.v_timestamp

        if 'range' in colnames:
            insert_dict['range'] = self._all_cut_string(str(item.f_get_range()),
                                    pypetconstants.HDF5_STRCOL_MAX_ARRAY_LENGTH, self._logger)

        # To allow backwards compatibility
        if 'array' in colnames:
            insert_dict['array'] = self._all_cut_string(str(item.f_get_range()),
                                    pypetconstants.HDF5_STRCOL_MAX_ARRAY_LENGTH, self._logger)

        if 'version' in colnames:
            insert_dict['version'] = item.v_version

        if 'finish_timestamp' in colnames:
            insert_dict['finish_timestamp'] = item._finish_timestamp

        if 'runtime' in colnames:
            runtime = item._runtime
            if len(runtime) > pypetconstants.HDF5_STRCOL_MAX_RUNTIME_LENGTH:
                #If string is too long we cut the microseconds
                runtime = runtime.split('.')[0]

            insert_dict['runtime'] = runtime

        if 'short_environment_hexsha' in colnames:
            insert_dict['short_environment_hexsha'] = item.v_environment_hexsha[0:7]



        return insert_dict

    @staticmethod
    def _all_cut_string(string, max_length, logger):
        if len(string) > max_length:
            logger.debug('The string `%s` was too long I truncated it to'
                                 ' %d characters' %
                                 (string,max_length))
            string = string[0:max_length-3] + '...'

        return string

    def _all_create_or_get_groups(self, key):
        newhdf5group = self._trajectory_group
        split_key = key.split('.')
        created = False
        for name in split_key:
            if not name in newhdf5group:
                try:
                    newhdf5group=self._hdf5file.create_group(where=newhdf5group, name=name, title=name)
                except AttributeError:
                    newhdf5group=self._hdf5file.createGroup(where=newhdf5group, name=name, title=name)
                created = True
            else:
                try:
                    newhdf5group=newhdf5group._f_get_child(name)
                except AttributeError:
                    newhdf5group=newhdf5group._f_getChild(name)


        return newhdf5group, created

    ################# Storing and loading Annotations ###########################################

    def _ann_store_annotations(self,item_with_annotations,node):
        if not item_with_annotations.v_annotations.f_is_empty():

            anno_dict = item_with_annotations.v_annotations.__dict__

            # if node is None:
            #     node = self._all_get_node_by_name(item_with_annotations.v_full_name)

            current_attrs = node._v_attrs

            changed = False

            for field_name, val in anno_dict.iteritems():
                field_name_with_prefix = HDF5StorageService.ANNOTATION_PREFIX+field_name
                if not field_name_with_prefix in current_attrs:
                    setattr(current_attrs,field_name_with_prefix,val)
                    changed = True

            if changed:
                setattr(current_attrs,HDF5StorageService.ANNOTATED,True)
                self._hdf5file.flush()


    def _ann_load_annotations(self,item_with_annotations,node):

        # if node is None:
        #     node = self._all_get_node_by_name(item_with_annotations.v_full_name)

        annotated = self._all_get_from_attrs(node,HDF5StorageService.ANNOTATED)

        if annotated:

            annotations =item_with_annotations.v_annotations

            if not annotations.f_is_empty():
                raise TypeError('Loading into non-empty annotations!')

            current_attrs = node._v_attrs

            for attr_name in current_attrs._v_attrnames:

                if attr_name.startswith(HDF5StorageService.ANNOTATION_PREFIX):
                    key = attr_name
                    key=key.replace(HDF5StorageService.ANNOTATION_PREFIX,'')

                    data = getattr(current_attrs,attr_name)
                    setattr(annotations,key,data)



    ############################################## Storing Groups ################################

    def _grp_store_group(self,node_in_traj, _hdf5_group = None):


        if _hdf5_group is None:
            _hdf5_group,_ = self._all_create_or_get_groups(node_in_traj.v_full_name)

        self._ann_store_annotations(node_in_traj,_hdf5_group)


    ################# Storing and Loading Parameters ############################################

    def _prm_extract_missing_flags(self,data_dict, flags_dict):
        for key,data in data_dict.items():
            if not key in flags_dict:
                dtype = type(data)
                if dtype in HDF5StorageService.TYPE_FLAG_MAPPING:
                    flags_dict[key]=HDF5StorageService.TYPE_FLAG_MAPPING[dtype]
                else:
                    raise pex.NoSuchServiceError('I cannot store `%s`, I do not understand the'
                                                 'type `%s`.' %(key,str(dtype)))


    def _prm_meta_remove_summary(self, instance):

        split_name = instance.v_full_name.split('.')
        where = split_name[0]

        if where in['derived_parameters','results']:
            creator_name = instance.v_creator_name
            if creator_name.startswith(pypetconstants.RUN_NAME):
                run_mask = pypetconstants.RUN_NAME+'X'*pypetconstants.FORMAT_ZEROS
                split_name[1]=run_mask
                new_full_name = '.'.join(split_name)
                old_full_name = instance.v_full_name
                instance._rename(new_full_name)
                try:
                    table_name = where+'_runs_summary'
                    table = getattr(self._overview_group,table_name)

                    row_iterator= self._all_find_param_or_result_entry_and_return_iterator(instance, table)


                    row = row_iterator.next()

                    nitems = row['number_of_items']-1
                    row['number_of_items'] = nitems
                    row.update()

                    try:
                        row_iterator.next()
                        raise RuntimeError('There is something completely wrong, found '
                                           '`%s` twice in a table!' %
                                        instance.v_full_name)
                    except StopIteration:
                        pass


                    table.flush()

                    if nitems == 0:
                        self._all_store_param_or_result_table_entry(instance,table,
                                                    flags=(HDF5StorageService.REMOVE_ROW,))


                except  pt.NoSuchNodeError:
                    pass
                finally:
                    # Get the old name back
                    instance._rename(old_full_name)

    def _prm_meta_add_summary(self,instance):
        """Add data to the summary tables and returns if comment has to be stored.

        Also moves comments upwards in the hierarchy if purge all comments and a lower index
        run has completed, only necessary for multiprocessing.

        """
        definitely_store_comment=True

        split_name = instance.v_full_name.split('.')
        where = split_name[0]

        # Check if we are in the subtree that has runs overview tables
        if where in['derived_parameters','results']:
            creator_name = instance.v_creator_name

            # Check sub-subtree
            if creator_name.startswith(pypetconstants.RUN_NAME):
                # Create the dummy name `result.run_XXXXXXXX` as a general mask and example item
                run_mask = pypetconstants.RUN_NAME+'X'*pypetconstants.FORMAT_ZEROS
                split_name[1]=run_mask
                new_full_name = '.'.join(split_name)
                old_full_name = instance.v_full_name
                # Rename the item for easier storage
                instance._rename(new_full_name)
                try:
                    # Get the overview table
                    table_name = where+'_runs_summary'
                    table = getattr(self._overview_group,table_name)

                    # True if comment must be moved upwards to lower index
                    erase_old_comment=False

                    # Find the overview table entry
                    row_iterator = \
                        self._all_find_param_or_result_entry_and_return_iterator(instance, table)

                    row = None
                    try:
                        row = row_iterator.next()
                    except StopIteration:
                        pass

                    if row is not None:
                        # If row found we need to increase the number of items
                        nitems = row['number_of_items']+1

                        # Get the run name of the example
                        example_item_run_name = row['example_item_run_name']

                        # Get the old comment:
                        location_string = row['location']
                        other_parent_node_name = location_string.replace(run_mask,example_item_run_name)
                        other_parent_node_name = '/' + self._trajectory_name + '/' + \
                                                 other_parent_node_name.replace('.','/')
                        try:
                            example_item_node = self._hdf5file.get_node(where=other_parent_node_name,
                                                                                   name=instance.v_name)
                        except AttributeError:
                            example_item_node = self._hdf5file.getNode(where=other_parent_node_name,
                                                                                  name = instance.v_name)

                        # Check if comment is obsolete
                        example_comment = str(example_item_node._v_attrs[HDF5StorageService.COMMENT])
                        definitely_store_comment=instance.v_comment != example_comment

                        # We can rely on lexicographic comparisons with run indices
                        if creator_name < example_item_run_name:
                            # In case the statement is true and the comments are equal, we need
                            # to move the comment to a result or derived parameter with a lower
                            # run name:
                            if not definitely_store_comment:

                                # We need to purge the comment in the other result or derived parameter
                                erase_old_comment=True
                                definitely_store_comment=True

                                row['example_item_run_name']=creator_name
                                row['value'] = self._all_cut_string(instance.f_val_to_str(),
                                                    pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH,
                                                    self._logger)
                            else:
                                self._logger.warning('Your example value and comment in the overview'
                                         ' table cannot be set to the lowest index'
                                         ' item because results or derived parameters'
                                         ' with lower indices have '
                                         ' a different comment! The comment of `%s` '
                                         ' in run `%s'
                                         ' differs from the current result or'
                                         ' derived parameter in run `%s`.' %
                                           (instance.v_name, creator_name, example_item_run_name))


                        row['number_of_items'] = nitems
                        row.update()

                        try:
                            row_iterator.next()
                            raise RuntimeError('There is something completely wrong, '
                                               'found `%s` twice in a table!' %
                                            instance.v_full_name)
                        except StopIteration:
                            pass


                        table.flush()

                        if self._purge_duplicate_comments and erase_old_comment:
                            del example_item_node._v_attrs[HDF5StorageService.COMMENT]

                        self._hdf5file.flush()

                    else:
                        self._all_store_param_or_result_table_entry(instance,table,
                                            flags=(HDF5StorageService.ADD_ROW,),
                                            additional_info={'example_item_run_name':creator_name})

                        definitely_store_comment=True

                #There are 2 cases of exceptions, either the table is switched off, or
                #the entry already exists, in both cases we won't have to store the comments
                except  pt.NoSuchNodeError:
                    definitely_store_comment=True
                finally:
                    # Get the old name back
                    instance._rename(old_full_name)

        return where, definitely_store_comment

    def _prm_add_meta_info(self,instance,group,msg):

        if msg == pypetconstants.UPDATE_LEAF:
            flags=(HDF5StorageService.ADD_ROW,HDF5StorageService.MODIFY_ROW)
        else:
            flags=(HDF5StorageService.ADD_ROW,)


        where, definitely_store_comment = self._prm_meta_add_summary(instance)


        try:
            table_name = self._all_get_table_name(where,instance.v_creator_name)

            table = getattr(self._overview_group,table_name)


            self._all_store_param_or_result_table_entry(instance,table,
                                                        flags=flags)
        except pt.NoSuchNodeError:
                pass


        if not self._purge_duplicate_comments or definitely_store_comment:
            setattr(group._v_attrs, HDF5StorageService.COMMENT, instance.v_comment)

        setattr(group._v_attrs, HDF5StorageService.CLASS_NAME, instance.f_get_class_name())
        setattr(group._v_attrs,HDF5StorageService.LEAF,1)


        if instance.v_is_parameter and instance.f_has_range():
            setattr(group._v_attrs, HDF5StorageService.LENGTH,len(instance))
            try:
                tablename = 'explored_parameters'
                table = getattr(self._overview_group,tablename)
                self._all_store_param_or_result_table_entry(instance,table,
                                                        flags=flags)
            except pt.NoSuchNodeError:
                pass

    def _prm_store_parameter_or_result(self, msg, instance,store_flags=None,_hdf5_group=None):

        fullname = instance.v_full_name
        self._logger.debug('Storing %s.' % fullname)


        if _hdf5_group is None:
            _hdf5_group, newly_created = self._all_create_or_get_groups(fullname)
        else:
            newly_created = False

        if msg == pypetconstants.UPDATE_LEAF or newly_created:
            self._prm_add_meta_info(instance,_hdf5_group,msg)

        ## Store annotations
        self._ann_store_annotations(instance,_hdf5_group)


        store_dict = instance._store()


        if store_flags is None:
            try:
                store_flags = instance._store_flags()
            except AttributeError:
                store_flags = {}


        self._prm_extract_missing_flags(store_dict,store_flags)


        for key, data_to_store in store_dict.items():
            if (not instance.v_is_parameter or msg == pypetconstants.LEAF) and  key in _hdf5_group:
                self._logger.debug('Found %s already in hdf5 node of %s, so I will ignore it.' %
                                   (key, fullname))

                continue
            if store_flags[key] == HDF5StorageService.TABLE:
                self._prm_store_into_pytable(msg,key, data_to_store, _hdf5_group, fullname)
            elif key in _hdf5_group:
                self._logger.debug('Found %s already in hdf5 node of %s, so I will ignore it.' %
                                   (key, fullname))
                continue
            elif store_flags[key] == HDF5StorageService.DICT:
                self._prm_store_dict_as_table(msg,key, data_to_store, _hdf5_group, fullname)
            elif store_flags[key] == HDF5StorageService.ARRAY:
                self._prm_store_into_array(msg,key, data_to_store, _hdf5_group, fullname)
            elif store_flags[key] == HDF5StorageService.CARRAY:
                self._prm_store_into_carray(msg,key, data_to_store, _hdf5_group, fullname)
            elif store_flags[key] == HDF5StorageService.FRAME:
                self._prm_store_data_frame(msg,key, data_to_store, _hdf5_group, fullname)
            else:
                raise RuntimeError('You shall not pass!')

    def _prm_store_dict_as_table(self, msg, key, data_to_store, group, fullname):

        if key in group:
            raise ValueError('Dictionary `%s` already exists in `%s`. Appending is not supported (yet).')


        #assert isinstance(data_to_store,dict)

        if key in group:
            raise ValueError('Dict `%s` already exists in `%s`. Appending is not supported (yet).')

        temp_dict={}
        for innerkey, val in data_to_store.iteritems():
            temp_dict[innerkey] =[val]

        objtable = ObjectTable(data=temp_dict)

        self._prm_store_into_pytable(msg,key,objtable,group,fullname)

        try:
            new_table = group._f_get_child(key)
        except AttributeError:
            new_table = group._f_getChild(key)

        self._all_set_attributes_to_recall_natives(temp_dict,new_table,
                                                   HDF5StorageService.DATA_PREFIX)

        setattr(new_table._v_attrs,HDF5StorageService.STORAGE_TYPE,
                HDF5StorageService.DICT)

        self._hdf5file.flush()



    def _prm_store_data_frame(self, msg,  key, data_to_store, group, fullname):

        try:

            if key in group:
                raise ValueError('DataFrame `%s` already exists in `%s`. Appending is not supported (yet).')


            name = group._v_pathname+'/' +key
            data_to_store.to_hdf(self._filename, name, append=True,data_columns=True)

            try:
                frame_group = group._f_get_child(key)
            except AttributeError:
                frame_group = group._f_getChild(key)

            setattr(frame_group._v_attrs,HDF5StorageService.STORAGE_TYPE, HDF5StorageService.FRAME)
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing DataFrame `%s` of `%s`.' %(key,fullname))
            raise




    def _prm_store_into_carray(self, msg, key, data, group, fullname):

        try:
            if key in group:
                raise ValueError('CArray `%s` already exists in `%s`. Appending is not supported (yet).')


            # if isinstance(data, np.ndarray):
            #     size = data.size
            if hasattr(data,'__len__'):
                size = len(data)
            else:
                size = 1

            if size == 0:
                self._logger.warning('`%s` of `%s` is _empty, I will skip storing.' %(key,fullname))
                return

            #try using pytables 3.0.0 API
            try:
                carray=self._hdf5file.create_carray(where=group, name=key,obj=data)
            except AttributeError:
                #if it does not work, create carray with old api
                atom = pt.Atom.from_dtype(data.dtype)
                carray=self._hdf5file.createCArray(where=group, name=key, atom=atom,
                                                   shape=data.shape)
                carray[:]=data[:]

            self._all_set_attributes_to_recall_natives(data,carray,HDF5StorageService.DATA_PREFIX)
            setattr(carray._v_attrs,HDF5StorageService.STORAGE_TYPE, HDF5StorageService.CARRAY)
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing array `%s` of `%s`.' % (key, fullname))
            raise


    def _prm_store_into_array(self, msg, key, data, group, fullname):

        #append_mode = kwargs.f_get('append_mode',None)

        try:
            if key in group:
                raise ValueError('Array `%s` already exists in `%s`. Appending is not supported (yet).')

            if hasattr(data,'__len__'):
                size = len(data)
            else:
                size = 1

            if size == 0:
                self._logger.warning('`%s` of `%s` is _empty, I will skip storing.' %(key,fullname))
                return

            try:
                array=self._hdf5file.create_array(where=group, name=key,obj=data)
            except AttributeError:
                array=self._hdf5file.createArray(where=group, name=key,object=data)

            self._all_set_attributes_to_recall_natives(data,array,HDF5StorageService.DATA_PREFIX)
            setattr(array._v_attrs,HDF5StorageService.STORAGE_TYPE, HDF5StorageService.ARRAY)
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing array `%s` of `%s`.' % (key, fullname))
            raise



    def _all_set_attributes_to_recall_natives(self, data, ptitem_or_dict, prefix):

            def _set_attribute_to_item_or_dict(item_or_dict, name,val):
                try:
                    try:
                        item_or_dict._f_setattr(name,val)
                    except AttributeError:
                        item_or_dict._f_setAttr(name,val)
                except AttributeError:
                    item_or_dict[name]=val

            if type(data) is tuple:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_TUPLE)

            elif type(data) is list:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_LIST)

            elif type(data) is np.ndarray:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_NDARRAY)

            elif type(data) is np.matrix:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                               HDF5StorageService.COLL_MATRIX)

            elif type(data) in pypetconstants.PARAMETER_SUPPORTED_DATA:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_SCALAR)

                strtype = repr(type(data))

                if not strtype in pypetconstants.PARAMETERTYPEDICT:
                    raise TypeError('I do not know how to handel `%s` its type is `%s`.' %
                                   (str(data),repr(type(data))))

                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.SCALAR_TYPE,strtype)

            elif type(data) is dict:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_DICT)

            else:
                raise TypeError('I do not know how to handel `%s` its type is `%s`.' %
                                   (str(data),repr(type(data))))

            if type(data) in (list,tuple):
                if len(data) > 0:
                    strtype = repr(type(data[0]))

                    if not strtype in pypetconstants.PARAMETERTYPEDICT:
                        raise TypeError('I do not know how to handel `%s` its type is '
                                           '`%s`.' % (str(data),strtype))

                    _set_attribute_to_item_or_dict(ptitem_or_dict,prefix +
                                                        HDF5StorageService.SCALAR_TYPE,strtype)



    def _all_remove_parameter_or_result_or_group(self, instance,remove_empty_groups=False):

        split_name = instance.v_full_name.split('.')

        if instance.v_is_leaf:
            base_group = split_name[0]

            tablename = self._all_get_table_name(base_group,instance.v_creator_name)
            table = getattr(self._overview_group,tablename)

            self._all_store_param_or_result_table_entry(instance,table,
                                                        flags=(HDF5StorageService.REMOVE_ROW,))


            self._prm_meta_remove_summary(instance)


        node_name = split_name.pop()

        where = '/'+self._trajectory_name+'/' + '/'.join(split_name)

        try:
            the_node = self._hdf5file.get_node(where=where, name=node_name)
        except AttributeError:
            the_node = self._hdf5file.getNode(where=where, name=node_name)

        if not instance.v_is_leaf:
            if len(the_node._v_groups) != 0:
                raise TypeError('You cannot remove a group that is not empty!')

        the_node._f_remove(recursive=True)
        #self._hdf5file.remove_node(where=where,name=node_name,recursive=True)





        if remove_empty_groups:
            for irun in reversed(range(len(split_name))):
                where = '/'+self._trajectory_name+'/' + '/'.join(split_name[0:irun])
                node_name = split_name[irun]
                try:
                    act_group = self._hdf5file.get_node(where=where,name=node_name)
                except AttributeError:
                    act_group = self._hdf5file.getNode(where=where,name=node_name)
                if len(act_group._v_groups) == 0:
                    try:
                        self._hdf5file.remove_node(where=where,name=node_name,recursive=True)
                    except AttributeError:
                        self._hdf5file.removeNode(where=where,name=node_name,recursive=True)
                else:
                    break



    def _prm_store_into_pytable(self,msg, tablename,data,hdf5group,fullname):


        try:
            if hasattr(hdf5group,tablename):
                table = getattr(hdf5group,tablename)

                if msg == pypetconstants.UPDATE_LEAF:
                    nstart= table.nrows
                    datasize = data.shape[0]
                    if nstart==datasize:
                        self._logger.debug('There is no new data to the parameter `%s`. I will'
                                           ' skip storage of table `%s`' % (fullname,tablename))
                        return
                    else:
                        self._logger.debug('There is new data to the parameter `%s`. I will'
                                           ' add data to table `%s`' % (fullname,tablename))

                else:
                    raise ValueError('Table %s already exists, appending is only supported for '
                                     'parameter merging and appending, please use >>msg= %s<<.' %
                                     (tablename,pypetconstants.UPDATE_LEAF))

                self._logger.debug('Found table %s in file %s, will append new entries in %s to the table.' %
                                   (tablename,self._filename, fullname))

                ## If the table exists, it already knows what the original data of the input was:
                data_type_dict = {}
            else:
                # if msg == pypetconstants.UPDATE_LEAF:
                    # self._logger.debug('Table `%s` of `%s` does not exist, '
                    #                    'I will create it!' % (tablename,fullname))

                description_dict, data_type_dict = self._prm_make_description(data,fullname)

                try:
                    table = self._hdf5file.create_table(where=hdf5group, name=tablename,
                                                       description=description_dict,
                                                       title=tablename)
                except AttributeError:
                    table = self._hdf5file.createTable(where=hdf5group, name=tablename,
                                                       description=description_dict,
                                                       title=tablename)
                nstart = 0

            #assert isinstance(table,pt.Table)
            #assert isinstance(data, ObjectTable)


            row = table.row

            datasize = data.shape[0]


            cols = data.columns.tolist()
            for n in range(nstart, datasize):

                for key in cols:

                    row[key] = data[key][n]

                row.append()

            for field_name, type_description in data_type_dict.iteritems():
                table._f_setAttr(field_name,type_description)


            setattr(table._v_attrs,HDF5StorageService.STORAGE_TYPE, HDF5StorageService.TABLE)
            table.flush()
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing table `%s` of `%s`.' %(tablename,fullname))
            raise



    def _prm_make_description(self, data, fullname):
        """ Returns a dictionary that describes a pytbales row.
        """
        def _convert_lists_and_tuples(series_of_data):
            ## If the first data item is a list, the rest must be as well, since
            # data has to be homogeneous

            if not isinstance(series_of_data[0],np.ndarray):
                for idx,item in enumerate(series_of_data):
                    series_of_data[idx] = np.array(item)



        descriptiondict={}
        original_data_type_dict={}

        for key, val in data.iteritems():

            self._all_set_attributes_to_recall_natives(val[0],original_data_type_dict,
                            HDF5StorageService.FORMATTED_COLUMN_PREFIX % key)


            _convert_lists_and_tuples(val)

            col = self._prm_get_table_col(key, val, fullname)

            # if col is None:
            #     raise TypeError('Entry %s of %s cannot be translated into pytables column' % (table_name,fullname))

            descriptiondict[key]=col

        return descriptiondict, original_data_type_dict


    def _prm_get_table_col(self, key, column, fullname):
        """ Creates a pytables column instance.

        The type of column depends on the type of parameter entry.
        """
        val = column[0]

        try:

            ## We do not want to loose int_
            if type(val) is int:
                return pt.IntCol()

            if isinstance(val,str):
                itemsize = int(self._prm_get_longest_stringsize(column))
                return pt.StringCol(itemsize)

            if isinstance(val, np.ndarray):
                if np.issubdtype(val.dtype,np.str):
                    itemsize = int(self._prm_get_longest_stringsize(column))
                    return pt.StringCol(itemsize,shape=val.shape)
                else:
                    return pt.Col.from_dtype(np.dtype((val.dtype,val.shape)))
            else:
                return pt.Col.from_dtype(np.dtype(type(val)))
        except Exception:
            self._logger.error('Failure in storing `%s` of Parameter/Result `%s`.'
                               ' Its type was `%s`.' % (key,fullname,repr(type(val))))
            raise



    @staticmethod
    def _prm_get_longest_stringsize( string_list):
        """ Returns the longest stringsize for a string entry across data.
        """
        maxlength = 1

        for stringar in string_list:
            if not isinstance(stringar,np.ndarray) or stringar.ndim==0:
                stringar = np.array([stringar])

            for string in stringar:
                maxlength = max(len(string),maxlength)

        # Make the string Col longer than needed in order to allow later on slightly large strings
        return maxlength*1.5



    def _prm_load_parameter_or_result(self, param, load_only=None,_hdf5_group=None):


        if isinstance(load_only,basestring):
            load_only=[load_only]


        if load_only is not None:
            self._logger.debug('I am in load only mode, I will only lode %s.' %
                                   str(load_only))
            loaded=[]


        if _hdf5_group is None:
            _hdf5_group = self._all_get_node_by_name(param.v_full_name)

        #self._ann_load_annotations(param,_hdf5_group)


        full_name = param.v_full_name

        self._logger.debug('Loading %s' % full_name)


        load_dict = {}
        for node in _hdf5_group:
            if not load_only is None:

                if not node._v_name in load_only:
                    continue
                else:
                    loaded.append(node._v_name)



            load_type = self._all_get_from_attrs(node,HDF5StorageService.STORAGE_TYPE)

            if load_type == HDF5StorageService.DICT:
                self._prm_read_dictionary(node, load_dict, full_name)
            elif load_type == HDF5StorageService.TABLE:
                self._prm_read_table(node, load_dict, full_name)
            elif load_type in [HDF5StorageService.ARRAY,HDF5StorageService.CARRAY]:
                self._prm_read_array(node, load_dict, full_name)
            elif load_type == HDF5StorageService.FRAME:
                self._prm_read_frame(node, load_dict,full_name)
            else:
                raise pex.NoSuchServiceError('Cannot load %s, do not understand the hdf5 file '
                                             'structure of %s [%s].' %
                                             (full_name, str(node),str(load_type)) )

        if load_only is not None:
            if not set(loaded) == set(load_only):
                raise ValueError('You marked %s for load only, but I cannot find these for `%s`' %
                                 (str(set(load_only)-set(loaded)),full_name))

        param._load(load_dict)


    def _prm_read_dictionary(self, leaf, load_dict, full_name):
        try:
            temp_dict={}
            self._prm_read_table(leaf,temp_dict,full_name)
            key =leaf._v_name
            temp_table = temp_dict[key]
            temp_dict = temp_table.to_dict('list')

            innder_dict = {}
            load_dict[key] = innder_dict
            for innerkey, vallist in temp_dict.items():
                innder_dict[innerkey] = vallist[0]
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (leaf._v_name,full_name))
            raise


    def _prm_read_frame(self,pd_node,load_dict, full_name):
        try:
            name = pd_node._v_name
            pathname = pd_node._v_pathname
            dataframe = read_hdf(self._filename,pathname,mode='r')
            load_dict[name] = dataframe
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (pd_node._v_name,full_name))
            raise

    def _prm_read_table(self,table,load_dict, full_name):
        """ Reads a non-nested Pytables table column by column.

        :type table: pt.Table
        :type load_dict:
        :return:
        """
        try:
            table_name = table._v_name

            for colname in table.colnames:
                col = table.col(colname)
                data_list=list(col)

                prefix = HDF5StorageService.FORMATTED_COLUMN_PREFIX % colname
                for idx,data in enumerate(data_list):
                    data,type_changed = self._all_recall_native_type(data,table,prefix)
                    if type_changed:
                        data_list[idx] = data
                    else:
                        break

                if table_name in load_dict:
                    load_dict[table_name][colname] = data_list
                else:
                    load_dict[table_name] = ObjectTable(data={colname:data_list})
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (table._v_name,full_name))
            raise


    def _prm_read_array(self, array, load_dict, full_name):

        try:
            result = array.read()
            result, dummy = self._all_recall_native_type(result,array,HDF5StorageService.DATA_PREFIX)

            load_dict[array._v_name]=result
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (array._v_name,full_name))
            raise









