""" Module containing the storage services.

Contains the standard :class:`~pypet.storageservice.HDF5StorageSerivce`
as well wrapper classes to allow thread safe multiprocess storing.

"""

__author__ = 'Robert Meyer'

import tables as pt
import tables.parameters as ptpa
import os
import warnings
import time

try:
    import queue
except ImportError:
    import Queue as queue
import numpy as np
from pandas import DataFrame, Series, Panel, Panel4D, HDFStore

import pypet.compat as compat
import pypet.utils.ptcompat as ptcompat
import pypet.pypetconstants as pypetconstants
import pypet.pypetexceptions as pex
from pypet._version import __version__ as VERSION
from pypet.parameter import ObjectTable, Parameter
import pypet.naturalnaming as nn
from pypet.pypetlogging import HasLogger, DisableLogger
from pypet.utils.decorators import deprecated


class MultiprocWrapper(object):
    """Abstract class definition of a Wrapper.

    Note that only storing is required, loading is optional.

    ABSTRACT: Needs to be defined in subclass

    """
    @property
    def is_open(self):
        """ Normally the file is opened and closed after each insertion.

        However, the storage service may provide to keep the store open and signals
        this via this property.

        """
        return False

    @property
    def multiproc_safe(self):
        """This wrapper guarantees multiprocessing safety"""
        return True

    def store(self, *args, **kwargs):
        raise NotImplementedError('Implement this!')


class QueueStorageServiceSender(MultiprocWrapper, HasLogger):
    """ For multiprocessing with :const:`~pypet.pypetconstants.WRAP_MODE_QUEUE`, replaces the
        original storage service.

        All storage requests are send over a queue to the process running the
        :class:`~pypet.storageservice.QueueStorageServiceWriter`.

        Does not support loading of data!

    """

    def __init__(self, storage_queue):
        self._queue = storage_queue
        self._set_logger()
        self._pickle_queue = True
        self._max_tries = 99
        self._sleep_time = 0.1

    @property
    def queue(self):
        """One can access the queue"""
        return self._queue

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._set_logger()

    def __getstate__(self):
        result = self.__dict__.copy()
        if not self._pickle_queue:
            result['_queue'] = None
        del result['_logger']
        return result

    def load(self, *args, **kwargs):
        raise NotImplementedError('Queue wrapping does not support loading. If you want to '
                                  'load data in a multiprocessing environment, use the Lock '
                                  'wrapping.')

    def store(self, *args, **kwargs):
        """Puts data to store on queue."""
        old_pickle = self._pickle_queue
        try:
            self._pickle_queue = False
            self._queue.put(('STORE', args, kwargs))
        except IOError as e:
            # # This is due to a bug in Python, repeating the operation works :-/
            # # See http://bugs.python.org/issue5155
            self._logger.error('Failed putting data to queue due to error: `%s`' % str(e))
            for trying in range(self._max_tries):
                try:
                    self._logger.error('Failed sending task %s to queue, I will try again.' %
                                       str(('STORE', args, kwargs)))
                    self._queue.put(('STORE', args, kwargs))
                    self._logger.error('Queue sending try #%d  was successful!' % trying)
                    break
                except IOError as e2:
                    self._logger.error('Failed putting data to queue due to error: `%s`' % str(e2))
                    time.sleep(self._sleep_time)
        except TypeError as e:
            # This handles a weird bug under python 3.4 (not 3.3) that sometimes
            # a NoneType is put on the queue instead of real data which needs to be ignored
            self._logger.error('Could not put %s because of: %s, '
                               'I will try again.' %
                               (str(('STORE', args, kwargs)), str(e)))
            try:
                self._logger.error(
                    'Failed sending task `%s` to queue due to: %s. I will try again.' %
                    (str(('STORE', args, kwargs)), str(e)))
                self._queue.put(('STORE', args, kwargs))
                self._logger.error('Second queue sending try was successful!')
            except TypeError as e2:
                self._logger.error(
                    'Failed sending task %s to queue due to: %s. I will try one last '
                    'time again.' %
                    (str(('STORE', args, kwargs)), str(e2)))
                self._queue.put(('STORE', args, kwargs))
                self._logger.error('Third queue sending try was successful!')
        except Exception as e:
            self._logger.error('Could not put %s because of: %s' %
                               (str(('STORE', args, kwargs)), str(e)))
            raise
        finally:
            self._pickle_queue = old_pickle

    def send_done(self):
        """Signals the writer that it can stop listening to the queue"""
        try:
            self._queue.put(('DONE', [], {}))
        except IOError as e:
            # # This is due to a bug in Python, repeating the operation works :-/
            # # See http://bugs.python.org/issue5155
            self._logger.error('Failed putting data to queue due to error: `%s`' % str(e))
            for trying in range(self._max_tries):
                try:
                    self._logger.error('Failed sending task `DONE` to queue, I will try again.')
                    self._queue.put(('DONE', [], {}))
                    self._logger.error('Queue sending try #%d  was successful!' % trying)
                    break
                except IOError as e2:
                    self._logger.error('Failed putting data to queue due to error: `%s`' % str(e2))
                    time.sleep(self._sleep_time)


class QueueStorageServiceWriter(HasLogger):
    """Wrapper class that listens to the queue and stores queue items via the storage service."""

    def __init__(self, storage_service, storage_queue):
        self._storage_service = storage_service
        self._queue = storage_queue
        self._trajectory_name = None
        self._set_logger()

    def __repr__(self):
        return '<%s wrapping Storage Service %s>' % (self.__class__.__name__,
                                                     repr(self._storage_service))

    def run(self):
        """Starts listening to the queue."""
        while True:
            args, kwargs = None, None
            try:
                to_store_list = []
                stop_listening = False
                while True:
                    # We try to grap more data from the queue to avoid reopneing the
                    # hdf5 file all the time
                    try:
                        msg, args, kwargs = self._queue.get(False)
                        if msg == 'DONE':
                            stop_listening = True
                        elif msg == 'STORE':
                            if 'msg' in kwargs:
                                store_msg = kwargs.pop('msg')
                            else:
                                store_msg = args[0]
                                args = args[1:]
                            if 'stuff_to_store' in kwargs:
                                stuff_to_store = kwargs.pop('stuff_to_store')
                            else:
                                stuff_to_store = args[0]
                                args = args[1:]
                            trajectory_name = kwargs.pop('trajectory_name')
                            if self._trajectory_name is None:
                                self._trajectory_name = trajectory_name
                            elif self._trajectory_name != trajectory_name:
                                raise RuntimeError('Cannot store into two different trajectories. '
                                                   'I am supposed to store into %s, '
                                                   'but I should also '
                                                   'store into %s.' %
                                                   (self._trajectory_name, trajectory_name))

                            to_store_list.append((store_msg, stuff_to_store, args, kwargs))
                        else:
                            raise RuntimeError(
                                'You queued something that was not intended to be queued!')
                        self._queue.task_done()
                    except queue.Empty:
                        break
                    except TypeError as e:
                        self._logger.error('Could not get %s because of: %s, '
                                           'I will ignore the error and wait for another '
                                           'try.' %
                                           (str(('STORE', args, kwargs)), str(e)))
                        # Under python 3.4 sometimes NoneTypes are put on the queue
                        # causing a TypeError. Apart form this sketchy handling, I have
                        # so far no solution
                    except Exception as e:
                        self._logger.error('Could not get %s because of: %s' %
                                           (str(('STORE', args, kwargs)), str(e)))
                        raise

                if to_store_list:
                    self._storage_service.store(pypetconstants.LIST, to_store_list,
                                                trajectory_name=self._trajectory_name)
                if stop_listening:
                    break

            except Exception as e2:
                self._logger.error('Encountered error: `%s`' % str(e2))
                raise

class LockWrapper(MultiprocWrapper, HasLogger):
    """For multiprocessing in :const:`~pypet.pypetconstants.WRAP_MODE_LOCK` mode,
    augments a storage service with a lock.

    The lock is acquired before storage or loading and released afterwards.

    """

    def __init__(self, storage_service, lock):
        self._storage_service = storage_service
        self._lock = lock
        self._set_logger()
        self._is_locked = False

    def __repr__(self):
        return '<%s wrapping Storage Service %s>' % (self.__class__.__name__,
                                                     repr(self._storage_service))

    @property
    def is_open(self):
        """ Normally the file is opened and closed after each insertion.

        However, the storage service may provide the option to keep the store open and signals
        this via this property.

        """
        return self._storage_service.is_open

    @property
    def multiproc_safe(self):
        """Usually storage services are not supposed to be multiprocessing safe"""
        return True

    @property
    def lock(self):
        """One can access the lock"""
        return self._lock

    def acquire_lock(self):
        if not self._is_locked:
            self._lock.acquire()
            self._is_locked = True

    def release_lock(self):
        if self._is_locked and not self._storage_service.is_open:
            self._lock.release()
            self._is_locked = False

    def store(self, *args, **kwargs):
        """Acquires a lock before storage and releases it afterwards."""
        try:
            self.acquire_lock()
            return self._storage_service.store(*args, **kwargs)
        finally:
            if self._lock is not None:
                try:
                    self.release_lock()
                except RuntimeError:
                    self._logger.error('Could not release lock `%s`!' % str(self._lock))

    def __del__(self):
        """In order to prevent a dead-lock in case of error,
         we close the storage on deletion and release the lock"""
        if self._storage_service.is_open:
            self._storage_service.store(pypetconstants.CLOSE_FILE, None)
        self.release_lock()

    def load(self, *args, **kwargs):
        """Acquires a lock before loading and releases it afterwards."""
        try:
            self._lock.acquire()
            return self._storage_service.load(*args, **kwargs)
        finally:
            if self._lock is not None:
                try:
                    self._lock.release()
                except RuntimeError:
                    self._logger.error('Could not release lock `%s`!' % str(self._lock))


class StorageService(object):
    """Abstract base class defining the storage service interface."""

    @property
    def is_open(self):
        """ Normally the file is opened and closed after each insertion.

        However, the storage service may provide the option to keep the store open and signals
        this via this property.

        """
        return False

    @property
    def multiproc_safe(self):
        """Usually storage services are not supposed to be multiprocessing safe"""
        return False

    def store(self, msg, stuff_to_store, *args, **kwargs):
        """See :class:`pypet.storageservice.HDF5StorageService` for an example of an
        implementation and requirements for the API.

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError('Implement this!')

    def load(self, msg, stuff_to_load, *args, **kwargs):
        """ See :class:`pypet.storageservice.HDF5StorageService` for an example of an
        implementation and requirements for the API.

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError('Implement this!')


class LazyStorageService(StorageService):
    """This lazy guy does nothing! Only for debugging purposes.

    Ignores all storage and loading requests and simply executes `pass` instead.

    """
    def load(self, *args, **kwargs):
        """Nope, I won't care, dude!"""
        pass

    def store(self, msg, stuff_to_store, *args, **kwargs):
        """Do whatever you want, I won't store anything!"""


class NodeProcessingTimer(HasLogger):
    """Simple Class to display the processing of nodes"""

    def __init__(self, display_time=15, logger_name=None):
        self._start_time = time.time()
        self._last_time = self._start_time
        self._display_time = display_time
        self._set_logger(logger_name)
        self._updates = 0
        self._last_updates = 0
        self.active = True

    def signal_update(self):
        """Signals the process timer.

        If more time than the display time has passed a message is emitted.

        """
        if not self.active:
            return

        self._updates += 1
        current_time = time.time()
        dt = current_time - self._last_time
        if dt > self._display_time:
            dfullt = current_time - self._start_time
            seconds = int(dfullt) % 60
            minutes = int(dfullt) / 60
            if minutes == 0:
                formatted_time = '%ds' % seconds
            else:
                formatted_time = '%dm%02ds' % (minutes, seconds)
            nodespersecond = self._updates / dfullt
            message = 'Processed %d nodes in %s (%.2f nodes/s).' % \
                      (self._updates, formatted_time, nodespersecond)
            self._logger.info(message)
            self._last_time = current_time


class PTItemMock(object):
    """Class that mocks a PyTables item and wraps around a dictionary"""

    def __init__(self, dictionary):
        self._v_attrs = dictionary

    def _f_setattr(self, name, val):
        self._v_attrs[name] = val

    def _f_setAttr(self, name, val):
        self._v_attrs[name] = val


class HDF5StorageService(StorageService, HasLogger):
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

    The service accepts the following parameters

    :param filename:

        The name of the hdf5 file. If none is specified the default
        `./hdf5/the_name_of_your_trajectory.hdf5` is chosen. If `filename` contains only a path
        like `filename='./myfolder/', it is changed to
        `filename='./myfolder/the_name_of_your_trajectory.hdf5'`.

    :param file_title: Title of the hdf5 file (only important if file is created new)

    :param overwrite_file:

        If the file already exists it will be overwritten. Otherwise
        the trajectory will simply be added to the file and already
        existing trajectories are not deleted.

    :param encoding:

        Format to encode and decode unicode strings stored to disk.
        The default ``'utf8'`` is highly recommended.

    :param complevel:

        If you use HDF5, you can specify your compression level. 0 means no compression
        and 9 is the highest compression level. See `PyTables Compression`_ for a detailed
        description.

        .. _`PyTables Compression`: http://pytables.github.io/usersguide/optimization.html#compression-issues

    :param complib:

        The library used for compression. Choose between *zlib*, *blosc*, and *lzo*.
        Note that 'blosc' and 'lzo' are usually faster than 'zlib' but it may be the case that
        you can no longer open your hdf5 files with third-party applications that do not rely
        on PyTables.

    :param shuffle:

        Whether or not to use the shuffle filters in the HDF5 library.
        This normally improves the compression ratio.

    :param fletcher32:

        Whether or not to use the *Fletcher32* filter in the HDF5 library.
        This is used to add a checksum on hdf5 data.

    :param pandas_format:

        How to store pandas data frames. Either in 'fixed' ('f') or 'table' ('t') format.
        Fixed format allows fast reading and writing but disables querying the hdf5 data and
        appending to the store (with other 3rd party software other than *pypet*).

    :param purge_duplicate_comments:

        If you add a result via :func:`~pypet.naturalnaming.ResultGroup.f_add_result` or a derived
        parameter :func:`~pypet.naturalnaming.DerivedParameterGroup.f_add_derived_parameter` and
        you set a comment, normally that comment would be attached to each and every instance.
        This can produce a lot of unnecessary overhead if the comment is the same for every
        instance over all runs. If `purge_duplicate_comments=1` than only the comment of the
        first result or derived parameter instance created in a run is stored or comments
        that differ from this first comment.

        For instance, during a single run you call
        `traj.f_add_result('my_result`,42, comment='Mostly harmless!')`
        and the result will be renamed to `results.run_00000000.my_result`. After storage
        in the node associated with this result in your hdf5 file, you will find the comment
        `'Mostly harmless!'` there. If you call
        `traj.f_add_result('my_result',-43, comment='Mostly harmless!')`
        in another run again, let's say run 00000001, the name will be mapped to
        `results.run_00000001.my_result`. But this time the comment will not be saved to disk
        since `'Mostly harmless!'` is already part of the very first result with the name
        'results.run_00000000.my_result'.
        Note that the comments will be compared and storage will only be discarded if the strings
        are exactly the same.

        If you use multiprocessing, the storage service will take care that the comment for
        the result or derived parameter with the lowest run index will be considered regardless
        of the order of the finishing of your runs. Note that this only works properly if all
        comments are the same. Otherwise the comment in the overview table might not be the one
        with the lowest run index.

        You need summary tables (see below) to be able to purge duplicate comments.

        This feature only works for comments in *leaf* nodes (aka Results and Parameters).
        So try to avoid to add comments in *group* nodes within single runs.

    :param summary_tables:

        Whether the summary tables should be created, i.e. the 'derived_parameters_runs_summary',
        and the `results_runs_summary`.

        The 'XXXXXX_summary' tables give a summary about all results or derived parameters.
        It is assumed that results and derived parameters with equal names in individual runs
        are similar and only the first result or derived parameter that was created
        is shown as an example.

        The summary table can be used in combination with `purge_duplicate_comments` to only store
        a single comment for every result with the same name in each run, see above.

    :param small_overview_tables:

        Whether the small overview tables should be created.
        Small tables are giving overview about 'config','parameters',
        'derived_parameters_trajectory', ,
        'results_trajectory','results_runs_summary'.

        Note that these tables create some overhead. If you want very small hdf5 files set
        `small_overview_tables` to False.

    :param large_overview_tables:

        Whether to add large overview tables. This encompasses information about every derived
        parameter, result, and the explored parameter in every single run.
        If you want small hdf5 files, this is the first option to set to false.

    :param results_per_run:

        Expected results you store per run. If you give a good/correct estimate
        storage to hdf5 file is much faster in case you store LARGE overview tables.

        Default is 0, i.e. the number of results is not estimated!

    :param derived_parameters_per_run:

        Analogous to the above.

    :param display_time:

        How often status messages about loading and storing time should be displayed.
        Interval in seconds.

    :param trajectory:

        A trajectory container, the storage service will add the used parameter to
        the trajectory container.

    """

    ADD_ROW = 'ADD'
    ''' Adds a row to an overview table'''
    REMOVE_ROW = 'REMOVE'
    ''' Removes a row from an overview table'''
    MODIFY_ROW = 'MODIFY'
    ''' Changes a row of an overview table'''

    COLL_TYPE = 'COLL_TYPE'
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

    NAME_TABLE_MAPPING = {
        '_overview_config': 'config',
        '_overview_parameters': 'parameters',
        '_overview_derived_parameters_trajectory': 'derived_parameters_trajectory',
        '_overview_derived_parameters_runs': 'derived_parameters_runs',
        '_overview_results_trajectory': 'results_trajectory',
        '_overview_results_runs': 'results_runs',
        '_overview_explored_parameters': 'explored_parameters',
        '_overview_derived_parameters_runs_summary': 'derived_parameters_runs_summary',
        '_overview_results_runs_summary': 'results_runs_summary'
    }
    ''' Mapping of trajectory config names to the tables'''

    PR_ATTR_NAME_MAPPING = {
        '_derived_parameters_per_run': 'derived_parameters_per_run',
        '_results_per_run': 'results_per_run',
        '_purge_duplicate_comments': 'purge_duplicate_comments',
        '_overview_explored_parameters_runs': 'explored_parameters_runs'
    }
    '''Mapping of Attribute names for hdf5_settings table'''

    ATTR_LIST = [
        'complevel',
        'complib',
        'shuffle',
        'fletcher32',
        'pandas_format',
        'encoding'
    ]
    '''List of HDF5StorageService Attributes that have to be stored into the hdf5_settings table'''



    ### Storing Data Constants
    STORAGE_TYPE = 'SRVC_STORE'
    '''Flag, how data was stored'''

    SHARED_DATA_TYPE = 'SRVC_SHARED_TYPE'

    ARRAY = pypetconstants.ARRAY
    '''Stored as array_

    .. _array: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-array-class

    '''
    CARRAY = pypetconstants.CARRAY
    '''Stored as carray_

    .. _carray: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-carray-class

    '''
    EARRAY = pypetconstants.EARRAY
    ''' Stored as earray_e.

    .. _earray: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-earray-class

    '''

    VLARRAY = pypetconstants.VLARRAY
    '''Stored as vlarray_

    .. _vlarray: http://pytables.github.io/usersguide/libref/homogenous_storage.html#the-vlarray-class

    '''

    TABLE = pypetconstants.TABLE
    '''Stored as pytable_

    .. _pytable: http://pytables.github.io/usersguide/libref/structured_storage.html#the-table-class

    '''

    DICT = pypetconstants.DICT
    ''' Stored as dict.

    In fact, stored as pytable, but the dictionary wil be reconstructed.
    '''

    FRAME = pypetconstants.FRAME
    ''' Stored as pandas DataFrame_

    .. _DataFrame: http://pandas.pydata.org/pandas-docs/dev/io.html#hdf5-pytables

    '''

    SERIES = pypetconstants.SERIES
    ''' Store data as pandas Series '''

    PANEL = pypetconstants.PANEL
    ''' Store data as pandas Panel(4D) '''

    SPLIT_TABLE = pypetconstants.SPLIT_TABLE
    ''' If a table was split due to too many columns'''

    DATATYPE_TABLE = pypetconstants.DATATYPE_TABLE
    '''If a table contains the data types instead of the attrs'''

    SHARED_DATA = pypetconstants.SHARED_DATA
    ''' An HDF5 data object for direct interaction '''

    TYPE_FLAG_MAPPING = {

        ObjectTable: TABLE,
        list: ARRAY,
        tuple: ARRAY,
        dict: DICT,
        np.ndarray: CARRAY,
        np.matrix: CARRAY,
        DataFrame: FRAME,
        Series: SERIES,
        Panel: PANEL,
        Panel4D: PANEL
    }
    ''' Mapping from object type to storage flag'''

    # Python native data should alwys be stored as an ARRAY
    for item in pypetconstants.PARAMETER_SUPPORTED_DATA:
        TYPE_FLAG_MAPPING[item] = ARRAY

    FORMATTED_COLUMN_PREFIX = 'SRVC_COLUMN_%s_'
    ''' Stores data type of a specific pytables column for perfect reconstruction'''
    DATA_PREFIX = 'SRVC_DATA_'
    ''' Stores data type of a pytables carray or array for perfect reconstruction'''


    # ANNOTATION CONSTANTS
    ANNOTATION_PREFIX = 'SRVC_AN_'
    ''' Prefix to store annotations as node attributes_

    .. _attributes: http://pytables.github.io/usersguide/libref/declarative_classes.html#the-attributeset-class

    '''
    ANNOTATED = 'SRVC_ANNOTATED'
    ''' Whether an item was annotated'''


    # Stuff necessary to construct parameters and result
    INIT_PREFIX = 'SRVC_INIT_'
    ''' Hdf5 attribute prefix to store class name of parameter or result'''
    CLASS_NAME = INIT_PREFIX + 'CLASS_NAME'
    ''' Name of a parameter or result class, is converted to a constructor'''
    COMMENT = INIT_PREFIX + 'COMMENT'
    ''' Comment of parameter or result'''
    LENGTH = INIT_PREFIX + 'LENGTH'
    ''' Length of a parameter if it is explored'''
    LEAF = 'SRVC_LEAF'
    ''' Whether an hdf5 node is a leaf node'''

    def __init__(self, filename=None,
                 file_title=None,
                 overwrite_file=False,
                 encoding='utf8',
                 complevel=9,
                 complib='zlib',
                 shuffle=True,
                 fletcher32=False,
                 pandas_format='fixed',
                 purge_duplicate_comments=True,
                 summary_tables=True,
                 small_overview_tables=True,
                 large_overview_tables=False,
                 results_per_run=0,
                 derived_parameters_per_run=0,
                 display_time=20,
                 trajectory=None):

        self._set_logger()

        if purge_duplicate_comments and not summary_tables:
            raise ValueError('You cannot purge duplicate comments without having the'
                             ' small overview tables.')

        # Prepare file names and log folder
        if file_title is None and trajectory is not None:
            file_title = trajectory.v_name
        elif file_title is None:
            file_title = 'Experiments'
        else:
            file_title = file_title

        if filename is None and trajectory is not None:
            # If no filename is supplied and the filename cannot be extracted from the
            # trajectory, create the default filename
            filename = os.path.join(os.getcwd(), 'hdf5', trajectory.v_name + '.hdf5')
        elif filename is None:
            filename = 'Experiments.hdf5'

        head, tail = os.path.split(filename)
        if not head:
            # If the filename contains no path information,
            # we put it into the current working directory
            filename = os.path.join(os.getcwd(), filename)
        if not tail and trajectory is not None:
            filename = os.path.join(filename, trajectory.v_name + '.hdf5')
        elif not tail and trajectory is None:
            filename = os.path.join(filename, 'Experiments.hdf5')

        # Print which file we use for storage
        self._logger.info('I will use the hdf5 file `%s`.' % filename)

        self._filename = filename
        self._file_title = file_title
        self._trajectory_name = None if trajectory is None else trajectory.v_name
        self._trajectory_index = None
        self._hdf5file = None
        self._hdf5store = None
        self._trajectory_group = None  # link to the top group in hdf5 file which is the start
        # node of a trajectory

        self._filters = None
        self._complevel = complevel
        self._complib = complib
        self._fletcher32 = fletcher32
        self._shuffle = shuffle
        self._encoding = encoding

        self._node_processing_timer = None

        self._display_time = display_time

        self._pandas_format = pandas_format

        self._purge_duplicate_comments = purge_duplicate_comments
        self._results_per_run = results_per_run
        self._derived_parameters_per_run = derived_parameters_per_run

        self._overview_parameters = small_overview_tables
        self._overview_config = small_overview_tables
        self._overview_explored_parameters = small_overview_tables
        self._overview_explored_parameters_runs = large_overview_tables
        self._overview_derived_parameters_trajectory = small_overview_tables
        self._overview_derived_parameters_runs = large_overview_tables
        self._overview_derived_parameters_runs_summary = summary_tables
        self._overview_results_trajectory = small_overview_tables
        self._overview_results_runs = large_overview_tables
        self._overview_results_runs_summary = summary_tables

        self._disable_logger = DisableLogger()


        self._mode = None
        self._keep_open = False

        if trajectory is not None and not trajectory.v_stored:
            self._srvc_set_config(trajectory=trajectory)

        if overwrite_file:
            try:
                os.remove(filename)
                self._logger.info('You specified ``overwrite_file=True``, so I deleted file `%s`.' %
                                  filename)
            except OSError:
                pass

        # We don't want the NN warnings of Pytables to display because they can be
        # annoying as hell
        warnings.simplefilter('ignore', pt.NaturalNameWarning)

    def __repr__(self):
        return '<%s (filename:`%s`)>' % (self.__class__.__name__, str(self._filename))

    @property
    def is_open(self):
        """ Normally the file is opened and closed after each insertion.

        However, the storage service may provide the option to keep the store open and signals
        this via this property.

        """
        return self._hdf5file is not None and self._hdf5file.isopen

    @property
    def encoding(self):
        """ How unicode strings are encoded"""
        return self._encoding

    @encoding.setter
    def encoding(self, encoding):
        self._encoding = encoding


    @property
    def display_time(self):
        """Time interval in seconds, when to display the storage or loading of nodes"""
        return self._display_time

    @display_time.setter
    def display_time(self, display_time):
        self._display_time = display_time

    @property
    def complib(self):
        """Compression library used"""
        return self._complib

    @complib.setter
    def complib(self, complib):
        self._complib = complib
        self._filters = None

    @property
    def complevel(self):
        """Compression level used"""
        return self._complevel

    @complevel.setter
    def complevel(self, complevel):
        self._complevel = complevel
        self._filters = None

    @property
    def fletcher32(self):
        """ Whether fletcher 32 should be used """
        return self._fletcher32

    @fletcher32.setter
    def fletcher32(self, fletcher32):
        self._fletcher32 = bool(fletcher32)
        self._filters = None

    @property
    def shuffle(self):
        """ Whether shuffle filtering should be used"""
        return self._shuffle

    @shuffle.setter
    def shuffle(self, shuffle):
        self._shuffle = bool(shuffle)
        self._filters = None

    @property
    @deprecated('No longer supported, please use shared data instead')
    def pandas_append(self):
        """ If pandas should create storage in append mode.

        DEPRECATED. No longer used, please use shared data instead!

        """
        return False

    @pandas_append.setter
    @deprecated('No longer supported, please use shared data instead')
    def pandas_append(self, pandas_append):
        pass

    @property
    def pandas_format(self):
        """Format of pandas data. Applicable formats are 'table' (or 't') and 'fixed' (or 'f')"""
        return self._pandas_format

    @pandas_format.setter
    def pandas_format(self, pandas_format):
        if pandas_format not in ('f', 'fixed', 'table', 't'):
            raise ValueError('''Pandas format can only be 'table' (or 't') and 'fixed' (or 'f')
                            not `%s`.''' % pandas_format)
        self._pandas_format = pandas_format

    @property
    def filename(self):
        """The name and path of the underlying hdf5 file."""
        return self._filename

    @filename.setter
    def filename(self, filename):
        self._filename = filename

    @property
    def _overview_group(self):
        """Direct link to the overview group"""
        return self._all_create_or_get_groups('overview')[0]

    def _all_get_filters(self, kwargs=None):
        """Makes filters

        Pops filter arguments from `kwargs` such that they are not passed
        on to other functions also using kwargs.

        """
        if kwargs is None:
            kwargs = {}
        complib = kwargs.pop('complib', None)
        complevel = kwargs.pop('complevel', None)
        shuffle = kwargs.pop('shuffle', None)
        fletcher32 = kwargs.pop('fletcher32', None)
        if complib is not None:
            self._filters = None
        else:
            complib = self._complib
        if complevel is not None:
            self._filters = None
        else:
            complevel = self._complevel
        if shuffle is not None:
            self._filters = None
        else:
            shuffle = self._shuffle
        if fletcher32 is not None:
            self._filters = None
        else:
            fletcher32 = self._fletcher32

        if self._filters is None:
            # Recreate the filters if something was changed
            self._filters = pt.Filters(complib=complib, complevel=complevel,
                                       shuffle=shuffle, fletcher32=fletcher32)
            self._hdf5file.filters = self._filters
            self._hdf5store._filters = self._filters
            self._hdf5store._complevel = complevel
            self._hdf5store._complib = complib
            self._hdf5store._fletcher32 = fletcher32

        return self._filters

    def _srvc_set_config(self, trajectory):
        """Sets a config value to the Trajectory or changes it if the trajectory was loaded
        a the settings no longer match"""
        def _set_config(name, value, comment):
            if not trajectory.f_contains('config.'+name, shortcuts=False):
                trajectory.f_add_config(Parameter, name, value, comment=comment)

        for attr_name in HDF5StorageService.NAME_TABLE_MAPPING:
            table_name = HDF5StorageService.NAME_TABLE_MAPPING[attr_name]
            value = getattr(self, attr_name)
            if table_name in ('parameters', 'config'):
                table_name += '_overview'
            _set_config('hdf5.overview.' + table_name,
                                    value,
                                    comment='Whether or not to have an overview '
                                            'table with that name')

        _set_config('hdf5.overview.explored_parameters_runs',
                                self._overview_explored_parameters_runs,
                                comment='Whether there are overview tables about the '
                                        'explored parameters in each run')

        _set_config('hdf5.purge_duplicate_comments',
                                self._purge_duplicate_comments,
                                comment='Whether comments of results and'
                                        ' derived parameters should only'
                                        ' be stored for the very first instance.'
                                        ' Works only if the summary tables are'
                                        ' active.')

        _set_config('hdf5.results_per_run', self._results_per_run,
                                comment='Expected number of results per run,'
                                        ' a good guess can increase storage performance')

        _set_config('hdf5.derived_parameters_per_run',
                                self._derived_parameters_per_run,
                                comment='Expected number of derived parameters per run,'
                                        ' a good guess can increase storage performance')

        _set_config('hdf5.complevel', self._complevel,
                                comment='Compression Level (0 no compression '
                                        'to 9 highest compression)')

        _set_config('hdf5.complib', self._complib,
                                comment='Compression Algorithm')

        _set_config('hdf5.encoding', self._encoding,
                                comment='Encoding for unicode characters')

        _set_config('hdf5.fletcher32', self._fletcher32,
                                comment='Whether to use fletcher 32 checksum')

        _set_config('hdf5.shuffle', self._shuffle,
                                comment='Whether to use shuffle filtering.')

        _set_config('hdf5.pandas_format', self._pandas_format,
                                comment='''How to store pandas data frames, either'''
                                        ''' 'fixed' ('f') or 'table' ('t').''')

        if trajectory.f_contains('config.hdf5', shortcuts=False):
            if trajectory.config.hdf5.v_comment == '':
                # If this has not happened yet, add a description of the hdf5 config group
                trajectory.config.hdf5.v_comment = 'Settings for the standard HDF5 storage service'

        trajectory.v_storage_service = self # And add the storage service

    def load(self, msg, stuff_to_load, *args, **kwargs):
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
                    Non-empty items in RAM are left untouched.

                :const:`pypet.pypetconstants.LOAD_DATA`: (2)

                    The whole data is loaded.
                    Only empty or in RAM non-existing instance are filled with the
                    data found on disk.

                :const:`pypet.pypetconstants.OVERWRITE_DATA`: (3)

                    The whole data is loaded.
                    If items that are to be loaded are already in RAM and not empty,
                    they are emptied and new data is loaded from disk.

            * :const:`pypet.pypetconstants.LEAF` ('LEAF')

                Loads a parameter or result.

                :param stuff_to_load: The item to be loaded

                :param load_data: How to load data

                :param load_only:

                    If you load a result, you can partially load it and ignore the
                    rest of the data. Just specify the name of the data you want to load.
                    You can also provide a list,
                    for example `load_only='spikes'`, `load_only=['spikes','membrane_potential']`.

                    Issues a warning if items cannot be found.

                :param load_except:

                    If you load a result you can partially load in and specify items
                    that should NOT be loaded here. You cannot use `load_except` and
                    `load_only` at the same time.

            * :const:`pypet.pyetconstants.GROUP`

                Loads a group a node (comment and annotations)

                :param recursive:

                    Recursively loads everything below

                :param load_data:

                    How to load stuff if ``recursive=True``
                    accepted values as above for loading the trajectory

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

        :raises:

            NoSuchServiceError if message or data is not understood

            DataNotInStorageError if data to be loaded cannot be found on disk

        """
        opened = True
        try:

            self._srvc_extract_file_information(kwargs)

            args = list(args)

            opened = self._srvc_opening_routine('r')

            if msg == pypetconstants.TRAJECTORY:
                self._trj_load_trajectory(stuff_to_load, *args, **kwargs)

            elif msg == pypetconstants.LEAF:
                self._prm_load_parameter_or_result(stuff_to_load, *args, **kwargs)

            elif msg == pypetconstants.GROUP:
                self._grp_load_group(stuff_to_load, *args, **kwargs)

            elif msg == pypetconstants.TREE:
                self._tree_load_tree(stuff_to_load, *args, **kwargs)

            elif msg == pypetconstants.LIST:
                self._srvc_load_several_items(stuff_to_load, *args, **kwargs)

            else:
                raise pex.NoSuchServiceError('I do not know how to handle `%s`' % msg)

        except pt.NoSuchNodeError as e:
            self._logger.error('Failed loading  `%s`' % str(stuff_to_load))
            raise pex.DataNotInStorageError(str(e))
        except:
            self._logger.error('Failed loading  `%s`' % str(stuff_to_load))
            raise
        finally:
            self._srvc_closing_routine(opened)

    def store(self, msg, stuff_to_store, *args, **kwargs):
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

                :param only_init:

                    If you just want to initialise the store. If yes, only meta information about
                    the trajectory is stored and none of the nodes/leaves within the trajectory.

                :param store_data:

                    How to store data, the following settings are understood:

                     :const:`pypet.pypetconstants.STORE_NOTHING`: (0)

                        Nothing is stored

                    :const:`pypet.pypetconstants.STORE_DATA_SKIPPING`: (1)

                        Data of not already stored nodes is stored

                    :const:`pypet.pypetconstants.STORE_DATA`: (2)

                        Data of all nodes is stored. However, existing data on disk is left
                        untouched.

                    :const:`pypet.pypetconstants.OVERWRITE_DATA`: (3)

                        Data of all nodes is stored and data on disk is overwritten.
                        May lead to fragmentation of the HDF5 file. The user is adviced
                        to recompress the file manually later on.

            * :const:`pypet.pypetconstants.SINGLE_RUN` ('SINGLE_RUN')

                :param stuff_to_store: The trajectory

                :param store_data: How to store data see above

                :param store_final: If final meta info should be stored

                :param store_full_in_run:

                    If the whole trajectory should be stored and not only data below
                    run groups of the current run.

            * :const:`pypet.pypetconstants.LEAF`

                Stores a parameter or result

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

                :param store_data:

                    How to store the data, see above for a descitpion.

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

                :param overwrite:

                    Can be used if parts of a leaf should be replaced. Either a list of
                    HDF5 names or `True` if this should account for all.

            * :const:`pypet.pypetconstants.DELETE` ('DELETE')

                Removes an item from disk. Empty group nodes, results and non-explored
                parameters can be removed.

                :param stuff_to_store: The item to be removed.

                :param delete_only:

                    Potential list of parts of a leaf node that should be deleted.

                :param remove_from_item:

                    If `delete_only` is used, whether deleted nodes should also be erased
                    from the leaf nodes themseleves.

                :param recursive:

                    If you want to delete a group node you can recursively delete all its
                    children.

            * :const:`pypet.pypetconstants.GROUP` ('GROUP')

                :param stuff_to_store: The group to store

                :param store_data: How to store data

                :param recursive: To recursively load everything below.

            * :const:`pypet.pypetconstants.TREE`

                Stores a single node or a full subtree

                :param stuff_to_store: Node to store

                :param store_data: How to store data

                :param recursive: Whether to store recursively the whole sub-tree

            * :const:`pypet.pypetconstants.DELETE_LINK`

                Deletes a link from hard drive

                :param name: The full colon separated name of the link

            * :const:`pypet.pypetconstants.LIST`

                .. _store-lists:

                Stores several items at once

                :param stuff_to_store:

                    Iterable whose items are to be stored. Iterable must contain tuples,
                    for example `[(msg1,item1,arg1,kwargs1),(msg2,item2,arg2,kwargs2),...]`

            * :const:`pypet.pypetconstants.ACCESS_DATA`

                Requests and manipulates data within the storage.
                Storage must be open.

                :param stuff_to_store:

                    A colon separated name to the data path

                :param item_name:

                    The name of the data item to interact with

                :param request:

                    A functional request in form of a string

                :param args:

                    Positional arguments passed to the reques

                :param kwargs:

                    Keyword arguments passed to the request

            * :const:`pypet.pypetconstants.OPEN_FILE`

                Opens the HDF5 file and keeps it open

                :param stuff_to_store: ``None``

            * :const:`pypet.pypetconstants.CLOSE_FILE`

                Closes an HDF5 file that was kept open, must be open before.

                :param stuff_to_store: ``None``

            * :const:`pypet.pypetconstants.FLUSH`

                Flushes an open file, must be open before.

                :param stuff_to_store: ``None``

        :raises: NoSuchServiceError if message or data is not understood

        """
        opened = True
        try:

            self._srvc_extract_file_information(kwargs)

            args = list(args)

            opened = self._srvc_opening_routine('a', msg)

            if msg == pypetconstants.MERGE:
                self._trj_merge_trajectories(*args, **kwargs)

            elif msg == pypetconstants.BACKUP:
                self._trj_backup_trajectory(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.PREPARE_MERGE:
                self._trj_prepare_merge(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.TRAJECTORY:
                self._trj_store_trajectory(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.SINGLE_RUN:
                self._srn_store_single_run(stuff_to_store, *args, **kwargs)

            elif msg in pypetconstants.LEAF:
                self._prm_store_parameter_or_result(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.DELETE:
                self._all_delete_parameter_or_result_or_group(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.GROUP:
                self._grp_store_group(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.TREE:
                self._tree_store_tree(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.DELETE_LINK:
                self._lnk_delete_link(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.LIST:
                self._srvc_store_several_items(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.ACCESS_DATA:
                return self._hdf5_interact_with_data(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.OPEN_FILE:
                opened = False # Wee need to keep the file open to allow later interaction
                self._keep_open = True
                self._node_processing_timer.active = False # This might be open quite long
                # so we don't want to display horribly long opening times

            elif msg == pypetconstants.CLOSE_FILE:
                opened = True # Simply conduct the closing routine afterwards
                self._keep_open = False

            elif msg == pypetconstants.FLUSH:
                self._hdf5file.flush()

            else:
                raise pex.NoSuchServiceError('I do not know how to handle `%s`' % msg)

        except:
            self._logger.error('Failed storing `%s`' % str(stuff_to_store))
            raise
        finally:
            self._srvc_closing_routine(opened)

    def _srvc_load_several_items(self, iterable, *args, **kwargs):
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
            if len(input_tuple) > 4:
                raise RuntimeError('You shall not pass!')

            self.load(msg, item, *args, **kwargs)

    def _srvc_check_hdf_properties(self, traj):
        """Reads out the properties for storing new data into the hdf5file

        :param traj:

            The trajectory

        """

        for attr_name in HDF5StorageService.ATTR_LIST:
            try:
                config = traj.f_get('config.hdf5.' + attr_name).f_get()
                setattr(self, attr_name, config)
            except AttributeError:
                self._logger.warning('Could not find `%s` in traj config, '
                                     'using default value `%s`.' %
                                     (attr_name, str(getattr(self, attr_name))))

        for attr_name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():
            try:
                if table_name in ('parameters', 'config'):
                    table_name += '_overview'
                config = traj.f_get('config.hdf5.overview.' + table_name).f_get()
                setattr(self, attr_name, config)
            except AttributeError:
                self._logger.warning('Could not find `%s` in traj config, '
                                     'using default value `%s`.' %
                                     (table_name, str(getattr(self, attr_name))))

        for attr_name, name in HDF5StorageService.PR_ATTR_NAME_MAPPING.items():
            try:
                config = traj.f_get('config.hdf5.' + name).f_get()
                setattr(self, attr_name, config)
            except AttributeError:
                self._logger.warning('Could not find `%s` in traj config, '
                                     'using default value `%s`.' %
                                     (name, str(getattr(self, attr_name))))

        if ((not self._overview_results_runs_summary or
                    not self._overview_derived_parameters_runs_summary) and
                    self._purge_duplicate_comments):
            raise RuntimeError('You chose to purge duplicate comments but disabled a summary '
                                   'table. You can only use the purging if you enable '
                                   'the summary tables.')

        self._filters = None

    def _srvc_store_several_items(self, iterable, *args, **kwargs):
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
            if len(input_tuple) > 4:
                raise RuntimeError('You shall not pass!')

            self.store(msg, item, *args, **kwargs)

    def _srvc_opening_routine(self, mode, msg=None):
        """Opens an hdf5 file for reading or writing

        The file is only opened if it has not been opened before (i.e. `self._hdf5file is None`).

        :param mode:

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
        self._mode = mode
        if not self.is_open:

            if 'a' in mode:
                (path, filename) = os.path.split(self._filename)
                if not os.path.exists(path):
                    os.makedirs(path)

                self._hdf5store = HDFStore(self._filename, mode=self._mode, complib=self._complib,
                                           complevel=self._complevel, fletcher32=self._fletcher32)
                self._hdf5file = self._hdf5store._handle
                self._hdf5file.title = self._file_title

                if self._trajectory_name is not None:
                    if not ('/' + self._trajectory_name) in self._hdf5file:
                        # If we want to store individual items we we have to check if the
                        # trajectory has been stored before
                        if not msg == pypetconstants.TRAJECTORY:
                            raise ValueError('Your trajectory cannot be found in the hdf5file, '
                                             'please use >>traj.f_store()<< '
                                             'before storing anything else.')

                    else:
                        # Keep a reference to the top trajectory node
                        self._trajectory_group = ptcompat.get_node(self._hdf5file,
                                                                   '/' + self._trajectory_name)
                else:
                    raise ValueError('I don`t know which trajectory to load')

            elif mode == 'r':

                if not self._trajectory_name is None and not self._trajectory_index is None:
                    raise ValueError('Please specify either a name of a trajectory or an index, '
                                     'but not both at the same time.')

                if not os.path.isfile(self._filename):
                    raise ValueError('File `' + self._filename + '` does not exist.')

                self._hdf5store = HDFStore(self._filename, mode=self._mode, complib=self._complib,
                                           complevel=self._complevel, fletcher32=self._fletcher32)
                self._hdf5file = self._hdf5store._handle

                if not self._trajectory_index is None:
                    # If an index is provided pick the trajectory at the corresponding
                    # position in the trajectory node list
                    nodelist = ptcompat.list_nodes(self._hdf5file, where='/')

                    if (self._trajectory_index >= len(nodelist) or
                                self._trajectory_index < -len(nodelist)):
                        raise ValueError('Trajectory No. %d does not exists, there are only '
                                         '%d trajectories in %s.'
                                         % (self._trajectory_index, len(nodelist), self._filename))

                    self._trajectory_group = nodelist[self._trajectory_index]
                    self._trajectory_name = self._trajectory_group._v_name

                elif not self._trajectory_name is None:
                    # Otherwise pick the trajectory group by name
                    if not ('/' + self._trajectory_name) in self._hdf5file:
                        raise ValueError('File %s does not contain trajectory %s.'
                                         % (self._filename, self._trajectory_name))

                    self._trajectory_group = ptcompat.get_node(self._hdf5file,
                                                               '/' + self._trajectory_name)
                else:
                    raise ValueError('Please specify a name of a trajectory to load or its '
                                     'index, otherwise I cannot open one.')

            else:
                raise RuntimeError('You shall not pass!')

            self._node_processing_timer = NodeProcessingTimer(display_time=self._display_time,
                                                              logger_name=self._logger.name)

            return True
        else:
            return False

    def _srvc_closing_routine(self, closing):
        """Routine to close an hdf5 file

        The file is closed only when `closing=True`. `closing=True` means that
        the file was opened in the current highest recursion level. This prevents re-opening
        and closing of the file if `store` or `load` are called recursively.

        """
        if (not self._keep_open and
            closing and
            self.is_open):

            f_fd = self._hdf5file.fileno()
            self._hdf5file.flush()
            try:
                os.fsync(f_fd)
                try:
                    self._hdf5store.flush(fsync=True)
                except TypeError:
                    f_fd = self._hdf5store._handle.fileno()
                    self._hdf5store.flush()
                    os.fsync(f_fd)
            except OSError as e:
                # This seems to be the only way to avoid an OSError under Windows
                errmsg = ('Encountered OSError while flushing file.'
                                   'If you are using Windows, don`t worry! '
                                   'I will ignore the error and try to close the file. '
                                   'Original error: %s' % str(e))
                self._logger.debug(errmsg)

            self._hdf5store.close()
            if self._hdf5file.isopen:
                self._logger.error('Could not close HDF5 file!')
            self._hdf5file = None
            self._hdf5store = None
            self._trajectory_group = None
            self._trajectory_name = None
            self._trajectory_index = None
            return True
        else:
            return False

    def _srvc_extract_file_information(self, kwargs):
        """Extracts file information from kwargs.

        Note that `kwargs` is not passed as `**kwargs` in order to also
        `pop` the elements on the level of the function calling `_srvc_extract_file_information`.

        """
        if 'filename' in kwargs:
            self._filename = kwargs.pop('filename')

        if 'file_title' in kwargs:
            self._file_title = kwargs.pop('file_title')

        if 'trajectory_name' in kwargs:
            self._trajectory_name = kwargs.pop('trajectory_name')

        if 'trajectory_index' in kwargs:
            self._trajectory_index = kwargs.pop('trajectory_index')


    ########################### Merging ###########################################################

    def _trj_backup_trajectory(self, traj, backup_filename=None):
        """Backs up a trajectory.

        :param traj: Trajectory that should be backed up

        :param backup_filename:

            Path and filename of backup file. If None is specified the storage service
            defaults to `path_to_trajectory_hdf5_file/backup_trajectory_name.hdf`.

        """
        self._logger.info('Storing backup of %s.' % traj.v_name)

        mypath, _ = os.path.split(self._filename)

        if backup_filename is None:
            backup_filename = os.path.join('%s' % mypath, 'backup_%s.hdf5' % traj.v_name)

        backup_hdf5file = ptcompat.open_file(filename=backup_filename,
                                             mode='a', title=backup_filename)

        if ('/' + self._trajectory_name) in backup_hdf5file:
            raise ValueError('I cannot backup  `%s` into file `%s`, there is already a '
                             'trajectory with that name.' % (traj.v_name, backup_filename))

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
        self._trj_copy_table_entries_from_table_name('derived_parameters_runs', rename_dict,
                                                     other_trajectory_name)
        self._trj_copy_table_entries_from_table_name('results_trajectory', rename_dict,
                                                     other_trajectory_name)
        self._trj_copy_table_entries_from_table_name('results_runs', rename_dict,
                                                     other_trajectory_name)

        self._trj_copy_summary_table_entries_from_table_name('results_runs_summary', rename_dict,
                                                             other_trajectory_name)
        self._trj_copy_summary_table_entries_from_table_name('derived_parameters_runs_summary',
                                                             rename_dict, other_trajectory_name)

    def _trj_copy_summary_table_entries_from_table_name(self, tablename, rename_dict,
                                                        other_trajectory_name):
        """Copy a the summary table entries from another trajectory into the current one

        :param tablename:

            Name of overview table

        :param rename_dict:

            Dictionary with old names (keys) and new names (values).

        :param other_trajectory_name:

            Name of other trajectory

        """
        count_dict = {}  # Dictionary containing the number of items that are merged for
        # a particular result summary

        # In the overview table location literally contains `run_XXXXXXXX`
        run_mask = pypetconstants.RUN_NAME + 'X' * pypetconstants.FORMAT_ZEROS

        for old_name in rename_dict:
            # Check for the summary entry in the other trajectory
            old_split_name = old_name.split('.')
            for idx, name in enumerate(old_split_name):
                add_to_count = False
                if (name.startswith(pypetconstants.RUN_NAME) and
                            name != pypetconstants.RUN_NAME_DUMMY):
                    old_split_name[idx] = run_mask
                    add_to_count = True
                    break

            if add_to_count:
                old_mask_name = '.'.join(old_split_name)

                if not old_mask_name in count_dict:
                    count_dict[old_mask_name] = 0

                count_dict[old_mask_name] += 1

        try:
            # get the other table
            other_table = ptcompat.get_node(self._hdf5file,
                                            '/' + other_trajectory_name + '/overview/' + tablename)

            new_row_dict = {}  # Dictionary with full names as keys and summary row dicts as values

            for row in other_table:
                # Iterate through the rows of the overview table
                location = compat.tostr(row['location'])
                name = compat.tostr(row['name'])
                full_name = location + '.' + name

                # If we need the overview entry mark it for merging
                if full_name in count_dict:
                    new_row_dict[full_name] = self._trj_read_out_row(other_table.colnames, row)

            # Get the summary table in the current trajectory
            table = ptcompat.get_node(self._hdf5file,
                                      '/' + self._trajectory_name + '/overview/' + tablename)

            for row in table:
                # Iterate through the current rows
                location = compat.tostr(row['location'])
                name = compat.tostr(row['name'])
                full_name = location + '.' + name

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
                    if (col_name == 'example_item_run_name' and
                            not col_name in other_table.colnames):
                        continue

                    if col_name == 'example_item_run_name':
                        # The example item run name has changed due to merging
                        old_run_name = compat.tostr(not_inserted_row[col_name])
                        # Get the old name
                        old_full_name = key.replace(run_mask, old_run_name)
                        # Find the new name
                        new_full_name = rename_dict[old_full_name]
                        # Extract the new run name
                        split_name = new_full_name.split('.')
                        new_run_name=''
                        for split in split_name:
                            if split.startswith(pypetconstants.RUN_NAME):
                                new_run_name = split
                                break
                        new_row[col_name] = new_run_name
                    else:
                        new_row[col_name] = not_inserted_row[col_name]

                new_row.append()

            table.flush()
            self._hdf5file.flush()

        except pt.NoSuchNodeError:
            self._logger.info('Did not find table `%s` in one of the trajectories,'
                              ' skipped copying.' % tablename)

    @staticmethod
    def _trj_read_out_row(colnames, row):
        """Reads out a row and returns a dictionary containing the row content.

        :param colnames: List of column names
        :param row:  A pytables table row
        :return: A dictionary with colnames as keys and content as values

        """
        result_dict = {}
        for colname in colnames:
            result_dict[colname] = row[colname]

        return result_dict

    def _trj_copy_table_entries_from_table_name(self, tablename, rename_dict,
                                                other_trajectory_name):
        """Copy overview tables (not summary) from other trajectory into the current one.

        :param tablename:

            Name of overview table

        :param rename_dict:

            Dictionary with old names (keys) and new names (values).

        :param other_trajectory_name:

            Name of other trajectory

        """
        try:
            other_table = ptcompat.get_node(self._hdf5file,
                                            '/' + other_trajectory_name + '/overview/' + tablename)
            new_row_dict = {}

            for row in other_table.iterrows():
                # Iterate through the summary table
                location = compat.tostr(row['location'])
                name = compat.tostr(row['name'])
                full_name = location + '.' + name

                if full_name in rename_dict:
                    # If the item is marked for merge we need to copy its overview info
                    read_out_row = self._trj_read_out_row(other_table.colnames, row)
                    new_location = rename_dict[full_name].split('.')
                    new_location = '.'.join(new_location[0:-1])
                    read_out_row['location'] = new_location
                    new_row_dict[rename_dict[full_name]] = read_out_row

            table = ptcompat.get_node(self._hdf5file,
                                      '/' + self._trajectory_name + '/overview/' + tablename)

            # I am pretty sure this is no longer necessary
            # # Insert data into the current overview table
            # for row in table.iterrows():
            #     location = compat.tostr(row['location'])
            #     name = compat.tostr(row['name'])
            #     full_name = location + '.' + name
            #
            #     if full_name in new_row_dict:
            #         for col_name in table.colnames:
            #             row[col_name] = new_row_dict[full_name][col_name]
            #
            #         del new_row_dict[full_name]
            #         row.update()
            #
            # table.flush()
            # self._hdf5file.flush()

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
            self._logger.info('Did not find table `%s` in one of the trajectories,'
                              ' skipped copying.' % tablename)

    def _trj_merge_trajectories(self, other_trajectory_name, rename_dict, move_nodes=False,
                                delete_trajectory=False):
        """Merges another trajectory into the current trajectory (as in self._trajectory_name).

        :param other_trajectory_name: Name of other trajectory
        :param rename_dict: Dictionary with old names (keys) and new names (values).
        :param move_nodes: Whether to move hdf5 nodes or copy them
        :param delete_trajectory: Whether to delete the other trajectory

        """
        if not ('/' + other_trajectory_name) in self._hdf5file:
            raise ValueError('Cannot merge `%s` and `%s`, because the second trajectory cannot '
                             'be found in my file.')

        for old_name in rename_dict:
            new_name = rename_dict[old_name]

            # Iterate over all items that need to be merged
            split_name = old_name.split('.')
            old_location = '/' + other_trajectory_name + '/' + '/'.join(split_name)

            split_name = new_name.split('.')
            new_location = '/' + self._trajectory_name + '/' + '/'.join(split_name)

            # Get the data from the other trajectory
            old_group = ptcompat.get_node(self._hdf5file, old_location)

            for node in old_group:
                # Now move or copy the data
                if move_nodes:
                    ptcompat.move_node(self._hdf5file,
                                       where=old_location, newparent=new_location,
                                       name=node._v_name, createparents=True)
                else:
                    ptcompat.copy_node(self._hdf5file,
                                       where=old_location, newparent=new_location,
                                       name=node._v_name, createparents=True,
                                       recursive=True)

            # And finally copy the attributes of leaf nodes
            # Attributes of group nodes are NOT copied, this has to be done
            # by the trajectory
            old_group._v_attrs._f_copy(where=ptcompat.get_node(self._hdf5file, new_location))

        self._trj_copy_table_entries(rename_dict, other_trajectory_name)

        if delete_trajectory:
            ptcompat.remove_node(self._hdf5file,
                                 where='/', name=other_trajectory_name, recursive=True)

    def _trj_prepare_merge(self, traj, changed_parameters):
        """Prepares a trajectory for merging.

        This function will already store extended parameters.

        :param traj: Target of merge
        :param changed_parameters: List of extended parameters (i.e. their names).

        """

        if not traj._stored:
            traj.f_store()

        # Update meta information
        infotable = getattr(self._overview_group, 'info')
        insert_dict = self._all_extract_insert_dict(traj, infotable.colnames)
        self._all_add_or_modify_row(traj.v_name, insert_dict, infotable, index=0,
                                    flags=(HDF5StorageService.MODIFY_ROW,))


        # Store extended parameters
        for param_name in changed_parameters:
            param = traj.f_get(param_name)
            # First we delete the parameter
            try:
                self.store(pypetconstants.DELETE, param)
            except pt.NoSuchNodeError:
                pass  # We can end up here if the parameter was never stored

            # And then we add it again
            self.store(pypetconstants.LEAF, param)

        # Increase the run table by the number of new runs
        run_table = getattr(self._overview_group, 'runs')
        actual_rows = run_table.nrows
        self._all_fill_run_table_with_dummys(actual_rows, len(traj))

        add_table = self._overview_explored_parameters_runs


        # Extract parameter summary and if necessary create new explored parameter tables
        # in the result groups
        for run_name in traj.f_get_run_names():
            run_info = traj.f_get_run_information(run_name)
            run_info['name'] = run_name
            idx = run_info['idx']

            traj._set_explored_parameters_to_idx(idx)

            create_run_group = ('results.runs.%s' % run_name) in traj

            run_summary = self._srn_add_explored_params(run_name,
                                                        compat.listvalues(
                                                            traj._explored_parameters),
                                                        add_table,
                                                        create_run_group=create_run_group)

            run_info['parameter_summary'] = run_summary

            self._all_add_or_modify_row(run_name, run_info, run_table, index=idx,
                                        flags=(HDF5StorageService.MODIFY_ROW,))

        traj.f_restore_default()


    ######################## Loading a Trajectory #################################################

    def _trj_load_trajectory(self, traj, as_new, load_parameters, load_derived_parameters,
                             load_results, load_other_data, force):
        """Loads a single trajectory from a given file.


        :param traj: The trajectory

        :param as_new: Whether to load trajectory as new

        :param load_parameters: How to load parameters and config

        :param load_derived_parameters: How to load derived parameters

        :param load_results: How to load results

        :param load_other_data: How to load anything not within the four subbranches

        :param force: Force load in case there is a pypet version mismatch

        You can specify how to load the parameters, derived parameters and results
        as follows:

        :const:`pypet.pypetconstants.LOAD_NOTHING`: (0)

            Nothing is loaded

        :const:`pypet.pypetconstants.LOAD_SKELETON`: (1)

            The skeleton including annotations are loaded, i.e. the items are empty.
            Non-empty items in RAM are left untouched.

        :const:`pypet.pypetconstants.LOAD_DATA`: (2)

            The whole data is loaded.
            Only empty or in RAM non-existing instance are filled with the
            data found on disk.

        :const:`pypet.pypetconstants.OVERWRITE_DATA`: (3)

            The whole data is loaded.
            If items that are to be loaded are already in RAM and not empty,
            they are emptied and new data is loaded from disk.


        If `as_new=True` the old trajectory is loaded into the new one, only parameters can be
        loaded. If `as_new=False` the current trajectory is completely replaced by the one
        on disk, i.e. the name from disk, the timestamp, etc. are assigned to `traj`.

        """
        # Some validity checks, if `as_new` is used correctly
        if (as_new and (load_derived_parameters != pypetconstants.LOAD_NOTHING or load_results !=
            pypetconstants.LOAD_NOTHING or
                                load_other_data != pypetconstants.LOAD_NOTHING)):
            raise ValueError('You cannot load a trajectory as new and load the derived '
                             'parameters and results. Only parameters are allowed.')

        if as_new and load_parameters != pypetconstants.LOAD_DATA:
            raise ValueError('You cannot load the trajectory as new and not load the data of '
                             'the parameters.')

        loadconstants = (pypetconstants.LOAD_NOTHING, pypetconstants.LOAD_SKELETON,
                         pypetconstants.LOAD_DATA, pypetconstants.OVERWRITE_DATA)

        if not (load_parameters in loadconstants and load_derived_parameters in loadconstants and
                        load_results in loadconstants and load_other_data in loadconstants):
            raise ValueError('Please give a valid option on how to load data. Options for '
                             '`load_parameter`, `load_derived_parameters`, `load_results`, '
                             'and `load_other_data` are %s. See function documentation for '
                             'the semantics of the values.' % str(loadconstants))

        traj._stored = not as_new

        # Loads meta data like the name, timestamps etc.
        # load_data is only used here to determine how to load the annotations
        load_data = max(load_parameters, load_derived_parameters, load_results, load_other_data)
        self._trj_load_meta_data(traj, load_data, as_new,  force)

        if (load_parameters != pypetconstants.LOAD_NOTHING or
                    load_derived_parameters != pypetconstants.LOAD_NOTHING or
                    load_results != pypetconstants.LOAD_NOTHING or
                    load_other_data != pypetconstants.LOAD_NOTHING):
            self._logger.info('Loading trajectory `%s`.' % traj.v_name)
        else:
            self._logger.info('Checked meta data of trajectory `%s`.' % traj.v_name)
            return

        maximum_display_other = 10
        counter = 0
        for children in [self._trajectory_group._v_groups, self._trajectory_group._v_links]:
            for hdf5_group_name in children:
                hdf5_group = children[hdf5_group_name]
                child_name = hdf5_group._v_name

                load_subbranch = True
                if child_name == 'config':
                    if as_new:
                        loading = pypetconstants.LOAD_NOTHING
                    else:
                        # If the trajectory is loaded as new, we don't care about old config stuff
                        # and only load the parameters
                        loading = load_parameters
                elif child_name == 'parameters':
                    loading = load_parameters
                elif child_name == 'results':
                    loading = load_results
                elif child_name == 'derived_parameters':
                    loading = load_derived_parameters
                elif child_name == 'overview':
                    continue
                else:
                    loading = load_other_data
                    load_subbranch = False

                if loading == pypetconstants.LOAD_NOTHING:
                    continue

                if load_subbranch:
                    # Load the subbranches recursively
                    self._logger.info('Loading branch `%s` in mode `%s`.' %
                                          (child_name, str(loading)))
                else:
                    if counter < maximum_display_other:
                        self._logger.info(
                            'Loading branch/node `%s` in mode `%s`.' % (child_name, str(loading)))
                    elif counter == maximum_display_other:
                        self._logger.info('To many branchs or nodes at root for display. '
                                          'I will not inform you about loading anymore. '
                                          'Branches are loaded silently '
                                          'in the background. Do not worry, '
                                          'I will not freeze! Pinky promise!!!')
                    counter += 1

                self._tree_load_tree(traj, child_name, load_data=loading, with_links=True,
                                     recursive=True, _trajectory=traj, _as_new=as_new,
                                     _hdf5_group=self._trajectory_group)

    def _trj_load_meta_data(self, traj,  load_data, as_new, force):
        """Loads meta information about the trajectory

        Checks if the version number does not differ from current pypet version
        Loads, comment, timestamp, name, version from disk in case trajectory is not loaded
        as new. Updates the run information as well.

        """

        metatable = self._overview_group.info
        metarow = metatable[0]

        try:
            version = compat.tostr(metarow['version'])
        except IndexError as ke:
            self._logger.error('Could not check version due to: %s' % str(ke))
            version = '`COULD NOT BE LOADED`'

        try:
            python = compat.tostr(metarow['python'])
        except IndexError as ke:
            self._logger.error('Could not check version due to: %s' % str(ke))
            python = '`COULD NOT BE LOADED`'

        self._trj_check_version(version, python, force)

        # Load the skeleton information
        self._grp_load_group(traj, load_data=load_data,
                             with_links=False, recursive=False, _traj=traj,
                             _as_new=as_new, _hdf5_group=self._trajectory_group)

        if as_new:
            length = int(metarow['length'])
            for irun in range(length):
                traj._add_run_info(irun)
        else:
            traj._comment = compat.tostr(metarow['comment'])
            traj._timestamp = float(metarow['timestamp'])
            traj._trajectory_timestamp = traj._timestamp
            traj._time = compat.tostr(metarow['time'])
            traj._trajectory_time = traj._time
            traj._name = compat.tostr(metarow['name'])
            traj._trajectory_name = traj._name
            traj._version = version
            traj._python = python

            single_run_table = self._overview_group.runs

            # Load the run information about the single runs
            for row in single_run_table.iterrows():
                name = compat.tostr(row['name'])
                idx = int(row['idx'])
                timestamp = float(row['timestamp'])
                time_ = compat.tostr(row['time'])
                completed = int(row['completed'])
                summary = compat.tostr(row['parameter_summary'])
                hexsha = compat.tostr(row['short_environment_hexsha'])


                # To allow backwards compatibility we need this try catch block
                try:
                    runtime = compat.tostr(row['runtime'])
                    finish_timestamp = float(row['finish_timestamp'])
                except IndexError as ke:
                    runtime = ''
                    finish_timestamp = 0.0
                    self._logger.warning('Could not load runtime, ' + repr(ke))

                info_dict = {}
                info_dict['idx'] = idx
                info_dict['timestamp'] = timestamp
                info_dict['time'] = time_
                info_dict['completed'] = completed
                info_dict['name'] = name
                info_dict['parameter_summary'] = summary
                info_dict['short_environment_hexsha'] = hexsha
                info_dict['runtime'] = runtime
                info_dict['finish_timestamp'] = finish_timestamp

                traj._add_run_info(**info_dict)

            # Load the hdf5 config data:
            self._srvc_load_hdf5_settings()

    def _srvc_load_hdf5_settings(self):

        def _extract_meta_data(attr_name, row, name_in_row, conversion_function):
            try:
                setattr(self, attr_name, conversion_function(row[name_in_row]))
            except IndexError as e:
                self._logger.error('Using default hdf5 setting, '
                                       'could not extract `%s` hdf5 setting because of: %s' %
                                        (name_in_row, str(e)))

        if 'hdf5_settings' in self._overview_group:
            hdf5_table = self._overview_group.hdf5_settings
            hdf5_row = hdf5_table[0]

            _extract_meta_data('complib', hdf5_row, 'complib', compat.tostr)
            _extract_meta_data('complevel', hdf5_row, 'complevel', int)
            _extract_meta_data('shuffle', hdf5_row, 'shuffle', bool)
            _extract_meta_data('fletcher32', hdf5_row, 'fletcher32', bool)
            _extract_meta_data('pandas_format', hdf5_row, 'pandas_format', compat.tostr)
            _extract_meta_data('encoding', hdf5_row, 'encoding', compat.tostr)

            _extract_meta_data('_results_per_run', hdf5_row,
                               'results_per_run', int)
            _extract_meta_data('_derived_parameters_per_run', hdf5_row,
                               'derived_parameters_per_run', int)
            _extract_meta_data('_purge_duplicate_comments', hdf5_row,
                               'purge_duplicate_comments', bool)
            _extract_meta_data('_overview_explored_parameters_runs', hdf5_row,
                               'explored_parameters_runs', bool)

            for attr_name, table_name in self.NAME_TABLE_MAPPING.items():
                attr_value = bool(hdf5_row[table_name])
                setattr(self, attr_name, attr_value)
        else:
            self._logger.warning(
                    'Could not find `hdf5_settings` overview table. I will use the '
                    'standard settings (for `complib`, `complevel` etc.) instead.')

    def _tree_load_sub_branch(self, traj_node, branch_name, load_data, with_links, recursive,
                              trajectory, as_new, hdf5_group):
        """Loads data starting from a node along a branch and starts recursively loading
        all data at end of branch.

        :param trajectory: The trajectory

        :param traj_node: The node from where loading starts

        :param branch_name:

            A branch along which loading progresses. Colon Notation is used:
            'group1.group2.group3' loads 'group1', then 'group2', then 'group3' and then finally
            recursively all children and children's children below 'group3'

        :param load_data:

            How to load the data


        :param with_links:

            If links should be loaded

        :param recursive:

            If loading recursively

        :param traj:

            The trajectory

        :param as_new:

            If trajectory is loaded as new

        :param hdf5_group:

            HDF5 node in the file corresponding to `traj_node`.

        """
        split_names = branch_name.split('.')

        final_group_name = split_names.pop()

        for name in split_names:
            # First load along the branch
            hdf5_group = getattr(hdf5_group, name)

            self._tree_load_nodes(traj_node, load_data=load_data, with_links=with_links,
                                  recursive=False, trajectory=trajectory, as_new=as_new,
                                  hdf5_group=hdf5_group)

            traj_node = traj_node._children[name]

        # Then load recursively all data in the last group and below
        hdf5_group = getattr(hdf5_group, final_group_name)
        self._tree_load_nodes(traj_node, load_data=load_data, with_links=with_links,
                              recursive=recursive, trajectory=trajectory,
                              as_new=as_new, hdf5_group=hdf5_group)

    def _trj_check_version(self, version, python, force):
        """Checks for version mismatch

        Raises a VersionMismatchError if version of loaded trajectory and current pypet version
        do not match. In case of `force=True` error is not raised only a warning is emitted.

        """
        curr_python = compat.python_version_string

        if (version != VERSION or curr_python != python) and not force:
            raise pex.VersionMismatchError('Current pypet version is %s used under python %s '
                                           '  but your trajectory'
                                           ' was created with version %s and python %s.'
                                           ' Use >>force=True<< to perform your load regardless'
                                           ' of version mismatch.' %
                                           (VERSION, curr_python, version, python))
        elif version != VERSION or curr_python != python:
            self._logger.warning('Current pypet version is %s with python %s but your trajectory'
                                 ' was created with version %s under python %s.'
                                 ' Yet, you enforced the load, so I will'
                                 ' handle the trajectory despite the'
                                 ' version mismatch.' %
                                 (VERSION, curr_python, version, python))


    #################################### Storing a Trajectory ####################################

    def _all_fill_run_table_with_dummys(self, start, stop):
        """Fills the `run` overview table with dummy information.

        The table is later on filled by the single runs with the real information.
        `start` specifies how large the table is when calling this function.

        The table might not be emtpy because a trajectory is enlarged due to expanding.

        """
        runtable = getattr(self._overview_group, 'runs')

        for idx in range(start, stop):
            insert_dict = {}
            insert_dict['idx'] = idx
            insert_dict['name'] = pypetconstants.FORMATTED_RUN_NAME % idx

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
        descriptiondict = {'name': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH,
                                                pos=0),
                           'time': pt.StringCol(len(traj.v_time), pos=1),
                           'timestamp': pt.FloatCol(pos=3),
                           'comment': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH,
                                                   pos=4),
                           'length': pt.IntCol(pos=2),
                           'version': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH,
                                                   pos=5),
                           'python': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH,
                                                  pos=5)}
        # 'loaded_from' : pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH)}

        infotable = self._all_get_or_create_table(where=self._overview_group, tablename='info',
                                                  description=descriptiondict,
                                                  expectedrows=len(traj))

        insert_dict = self._all_extract_insert_dict(traj, infotable.colnames)
        self._all_add_or_modify_row(traj.v_name, insert_dict, infotable, index=0,
                                    flags=(HDF5StorageService.ADD_ROW,
                                           HDF5StorageService.MODIFY_ROW))

        # Description of the `run` table
        rundescription_dict = {'name': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH,
                                                    pos=1),
                               'time': pt.StringCol(len(traj.v_time), pos=2),
                               'timestamp': pt.FloatCol(pos=3),
                               'idx': pt.IntCol(pos=0),
                               'completed': pt.IntCol(pos=8),
                               'parameter_summary': pt.StringCol(
                                   pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH,
                                   pos=6),
                               'short_environment_hexsha': pt.StringCol(7, pos=7),
                               'finish_timestamp': pt.FloatCol(pos=4),
                               'runtime': pt.StringCol(
                                   pypetconstants.HDF5_STRCOL_MAX_RUNTIME_LENGTH,
                                   pos=5)}

        runtable = self._all_get_or_create_table(where=self._overview_group,
                                                 tablename='runs',
                                                 description=rundescription_dict)

        hdf5_description_dict = {'complib': pt.StringCol(7, pos=0),
                                 'complevel': pt.IntCol(pos=1),
                                 'shuffle': pt.BoolCol(pos=2),
                                 'fletcher32': pt.BoolCol(pos=3),
                                 'pandas_format': pt.StringCol(7, pos=4),
                                 'encoding': pt.StringCol(11, pos=5)}

        pos = 7
        for name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():
            hdf5_description_dict[table_name] = pt.BoolCol(pos=pos)
            pos += 1

        # Store the hdf5 properties in an overview table
        hdf5_description_dict.update({'purge_duplicate_comments': pt.BoolCol(pos=pos + 2),
                                      'results_per_run': pt.IntCol(pos=pos + 3),
                                      'derived_parameters_per_run': pt.IntCol(pos=pos + 4),
                                      'explored_parameters_runs': pt.BoolCol(pos=pos + 1)})

        hdf5table = self._all_get_or_create_table(where=self._overview_group,
                                                  tablename='hdf5_settings',
                                                  description=hdf5_description_dict)

        insert_dict = {}
        for attr_name in self.ATTR_LIST:
            insert_dict[attr_name] = getattr(self, attr_name)

        for attr_name, table_name in self.NAME_TABLE_MAPPING.items():
            insert_dict[table_name] = getattr(self, attr_name)

        for attr_name, name in self.PR_ATTR_NAME_MAPPING.items():
            insert_dict[name] = getattr(self, attr_name)

        self._all_add_or_modify_row(traj.v_name, insert_dict, hdf5table, index=0,
                                    flags=(
                                        HDF5StorageService.ADD_ROW, HDF5StorageService.MODIFY_ROW))


        # Fill table with dummy entries starting from the current table size
        actual_rows = runtable.nrows
        self._all_fill_run_table_with_dummys(actual_rows, len(traj))

        # Store the annotations and comment of the trajectory node
        self._grp_store_group(traj, store_data=pypetconstants.STORE_DATA,
                                  with_links=False,
                                  recursive=False,
                                  _hdf5_group=self._trajectory_group)

        # Prepare the overview tables
        tostore_tables = []

        for name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():

            # Check if we want the corresponding overview table
            # If the trajectory does not contain information about the table
            # we assume it should be created.

            if getattr(self, name):
                tostore_tables.append(table_name)

        self._srvc_make_overview_tables(tostore_tables, traj)


    def _srvc_make_overview_tables(self, tables_to_make, traj=None):
        """Creates the overview tables in overview group"""
        for table_name in tables_to_make:
            # Prepare the tables desciptions, depending on which overview table we create
            # we need different columns
            paramdescriptiondict = {}
            expectedrows = 0

            # Every overview table has a name and location column
            paramdescriptiondict['location'] = pt.StringCol(
                pypetconstants.HDF5_STRCOL_MAX_LOCATION_LENGTH,
                pos=0)
            paramdescriptiondict['name'] = pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH,
                                                        pos=1)
            if not table_name == 'explored_parameters' and not 'groups' in table_name:
                paramdescriptiondict['value'] = pt.StringCol(
                    pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH)

            if table_name == 'config':
                if traj is not None:
                    expectedrows = len(traj._config)

            if table_name == 'parameters':
                if traj is not None:
                    expectedrows = len(traj._parameters)

            if table_name == 'explored_parameters':
                paramdescriptiondict['range'] = pt.StringCol(
                    pypetconstants.HDF5_STRCOL_MAX_ARRAY_LENGTH)
                if traj is not None:
                    expectedrows = len(traj._explored_parameters)

            if table_name == 'results_trajectory':
                if traj is not None:
                    expectedrows = len(traj._results)

            if table_name == 'derived_parameters_trajectory':
                if traj is not None:
                    expectedrows = len(traj._derived_parameters)

            if table_name in ['derived_parameters_trajectory', 'results_trajectory',
                              'derived_parameters_runs_summary', 'results_runs_summary',
                              'config', 'parameters', 'explored_parameters']:

                if table_name.startswith('derived') or table_name in ('parameters', 'config'):
                    paramdescriptiondict['length'] = pt.IntCol()

                paramdescriptiondict['comment'] = pt.StringCol(
                    pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH)

            if table_name.endswith('summary'):
                paramdescriptiondict['number_of_items'] = pt.IntCol(dflt=1)
                paramdescriptiondict['example_item_run_name'] = \
                    pt.StringCol(len(pypetconstants.RUN_NAME) + pypetconstants.FORMAT_ZEROS + 3,
                                 pos=2)

            # Check if the user provided an estimate of the amount of results per run
            # This can help to speed up storing
            if table_name.startswith('derived_parameters_runs'):

                expectedrows = self._derived_parameters_per_run

                if not table_name.endswith('summary') and traj is not None:
                    expectedrows *= len(traj)

            if table_name.startswith('results_runs'):
                expectedrows = self._results_per_run

                if not expectedrows <= 0:
                    if not table_name.endswith('summary') and traj is not None:
                        expectedrows *= len(traj)

            if expectedrows > 0:
                paramtable = self._all_get_or_create_table(where=self._overview_group,
                                                           tablename=table_name,
                                                           description=paramdescriptiondict,
                                                           expectedrows=expectedrows)
            else:
                paramtable = self._all_get_or_create_table(where=self._overview_group,
                                                           tablename=table_name,
                                                           description=paramdescriptiondict)

            paramtable.flush()

    def _trj_store_trajectory(self, traj, only_init=False, store_data=pypetconstants.STORE_DATA):
        """ Stores a trajectory to an hdf5 file

        Stores all groups, parameters and results

        """
        if not only_init:
            self._logger.info('Start storing Trajectory `%s`.' % self._trajectory_name)
        else:
            self._logger.info('Initialising storage or updating meta data of Trajectory `%s`.' %
                              self._trajectory_name)
            store_data = pypetconstants.STORE_NOTHING

        # In case we accidentally chose a trajectory name that already exist
        # We do not want to mess up the stored trajectory but raise an Error
        if not traj._stored and self._trajectory_group is not None:
            raise RuntimeError('You want to store a completely new trajectory with name'
                               ' `%s` but this trajectory is already found in file `%s`' %
                               (traj.v_name, self._filename))

        # Extract HDF5 settings from the trajectory
        self._srvc_check_hdf_properties(traj)

        # Store the trajectory for the first time if necessary:
        if self._trajectory_group is None:
            self._trajectory_group = ptcompat.create_group(self._hdf5file,
                                                          where='/',
                                                          name=self._trajectory_name,
                                                          title=self._trajectory_name,
                                                          filters = self._all_get_filters())
        traj._stored = True

        # Store meta information
        self._trj_store_meta_data(traj)

        # # Store recursively the config subtree
        # self._tree_store_recursively(pypetconstants.LEAF,traj.config,self._trajectory_group)

        if store_data in (pypetconstants.STORE_DATA_SKIPPING,
                          pypetconstants.STORE_DATA,
                          pypetconstants.OVERWRITE_DATA):

            counter = 0
            maximum_display_other = 10
            name_set = set(['parameters', 'config', 'derived_parameters', 'results'])

            for child_name in traj._children:

                if child_name in name_set:
                    self._logger.info('Storing branch `%s`.' % child_name)
                else:
                    if counter < maximum_display_other:
                        self._logger.info('Storing branch/node `%s`.' % child_name)
                    elif counter == maximum_display_other:
                        self._logger.info('To many branches or nodes at root for display. '
                                          'I will not inform you about storing anymore. '
                                          'Branches are stored silently in the background. '
                                          'Do not worry, I will not freeze! Pinky promise!!!')
                    counter += 1

                # Store recursively the elements
                self._tree_store_tree(traj, child_name, store_data=store_data, with_links=True,
                         recursive=True,
                         _parent_hdf5_group=self._trajectory_group)

            self._logger.info('Finished storing Trajectory `%s`.' % self._trajectory_name)
        else:
            self._logger.info('Finished init or meta data update for `%s`.' %
                              self._trajectory_name)
        traj._stored = True

    def _tree_store_sub_branch(self, traj_node, branch_name, store_data, with_links, recursive,
                               hdf5_group):
        """Stores data starting from a node along a branch and starts recursively loading
        all data at end of branch.

        :param traj_node: The node where storing starts

        :param branch_name:

            A branch along which storing progresses. Colon Notation is used:
            'group1.group2.group3' loads 'group1', then 'group2', then 'group3', and then finally
            recursively all children and children's children below 'group3'.

        :param store_data: How data should be stored
        
        :param with_links: If links should be stored
        
        :param recursive:

            If the rest of the tree should be recursively stored
            
        :param hdf5_group:

            HDF5 node in the file corresponding to `traj_node`

        """
        split_names = branch_name.split('.')

        leaf_name = split_names.pop()

        for name in split_names:
            # Store along a branch
            self._tree_store_nodes(traj_node, name, store_data=store_data, with_links=with_links,
                                   recursive=False,
                                   parent_hdf5_group=hdf5_group)

            traj_node = traj_node._children[name]

            hdf5_group = getattr(hdf5_group, name)

        # Store final group and recursively everything below it
        self._tree_store_nodes(traj_node, leaf_name, store_data=store_data,
                               with_links=with_links, recursive=recursive,
                               parent_hdf5_group=hdf5_group)


    ########################  Storing and Loading Sub Trees #######################################

    def _tree_store_tree(self, traj_node, child_name, store_data=pypetconstants.STORE_DATA,
                         with_links=True,
                         recursive=False, _parent_hdf5_group=None):
        """Stores a node and potentially recursively all nodes below

        :param traj_node: Parent node where storing starts

        :param child_name: Name of child node

        :param store_data:  How to store data

        :param with_links: If links should be stored

        :param recursive: Whether to store everything below `traj_node`.

        :param _parent_hdf5_group: The hdf5 node pointing containing the parent

        """
        if store_data == pypetconstants.STORE_NOTHING:
            return

        location = traj_node.v_full_name

        if _parent_hdf5_group is not None:
            # Store node and potentially everything below it
            self._tree_store_sub_branch(traj_node, child_name, store_data=store_data,
                                        with_links=with_links, recursive=recursive,
                                        hdf5_group=_parent_hdf5_group)
        else:
            # Get parent hdf5 node
            hdf5_location = location.replace('.', '/')
            try:
                if location == '':
                    _parent_hdf5_group = self._trajectory_group
                else:
                    _parent_hdf5_group = ptcompat.get_node(self._hdf5file,
                                                         where=self._trajectory_group,
                                                         name=hdf5_location)

                # Store node and potentially everything below it
                self._tree_store_sub_branch(traj_node, child_name, store_data=store_data,
                                            with_links=with_links, recursive=recursive,
                                            hdf5_group=_parent_hdf5_group)

            except pt.NoSuchNodeError:
                self._logger.debug('Cannot store `%s` the parental hdf5 node with path `%s` does '
                                     'not exist on disk.' %
                                     (traj_node.v_name, hdf5_location))

                if traj_node.v_is_leaf:
                    self._logger.error('Cannot store `%s` the parental hdf5 node with path `%s` does '
                                       'not exist on disk! The child you want to store is a leaf node,'
                                       'that cannot be stored without the parental node existing on '
                                       'disk.' %
                                       (traj_node.v_name, hdf5_location))
                    raise
                else:
                    self._logger.debug('I will try to store the path from trajectory root to '
                                         'the child now.')
                    self._tree_store_sub_branch(traj_node._nn_interface._root_instance,
                                                traj_node.v_full_name + '.' + child_name,
                                                store_data=store_data, with_links=with_links,
                                                recursive=recursive,
                                                hdf5_group=self._trajectory_group)

    def _tree_load_tree(self, parent_traj_node, child_name, load_data=pypetconstants.LOAD_DATA,
                        with_links=True, recursive=False, _trajectory=None, _as_new=False,
                        _hdf5_group=None):
        """Loads a specific tree node and potentially all nodes below

        :param _trajectory: The trajectory object

        :param parent_traj_node: parent node of node to load in trajectory

        :param child_name: Name (!) of node to be loaded

        :param recursive: Whether to load everything below the child

        :param load_data: How to load the data

        :param _as_new:

            If trajectory is loaded as new

        """
        if load_data == pypetconstants.LOAD_NOTHING:
            return

        if _trajectory is None:
            _trajectory = parent_traj_node.v_root

        if _hdf5_group is None:
            hdf5_group_name = parent_traj_node.v_full_name.replace('.', '/')

            # Get child node to load
            if hdf5_group_name == '':
                _hdf5_group = self._trajectory_group
            else:
                try:
                    _hdf5_group = ptcompat.get_node(self._hdf5file,
                                                  where=self._trajectory_group,
                                                  name=hdf5_group_name)
                except pt.NoSuchNodeError:
                    self._logger.error('Cannot load `%s` the hdf5 node `%s` does not exist!'
                                       % (child_name, hdf5_group_name))
                    raise

        self._tree_load_sub_branch(parent_traj_node, child_name, load_data=load_data,
                                   with_links=with_links, recursive=recursive,
                                   trajectory=_trajectory, as_new=_as_new, hdf5_group=_hdf5_group)

    def _tree_create_leaf(self, name, trajectory, hdf5_group):
        """ Creates a new pypet leaf instance.

        Returns the leaf and if it is an explored parameter the length of the range.

        """
        class_name = self._all_get_from_attrs(hdf5_group, HDF5StorageService.CLASS_NAME)
        range_length = self._all_get_from_attrs(hdf5_group, HDF5StorageService.LENGTH)

        # Create the instance with the appropriate constructor
        class_constructor = trajectory._create_class(class_name)

        instance = trajectory._construct_instance(class_constructor, name)

        if instance.v_is_parameter:
            instance._explored = range_length is not None

        return instance, range_length

    def _tree_load_nodes(self, parent_traj_node, load_data, with_links, recursive, trajectory,
                         as_new, hdf5_group):
        """Loads a node from hdf5 file and if desired recursively everything below

        :param parent_traj_node: The parent node whose child should be loaded
        :param load_data: How to load the data
        :param with_links: If links should be loaded
        :param recursive: Whether loading recursively below hdf5_group
        :param trajectory: The trajectory object
        :param as_new: If trajectory is loaded as new
        :param hdf5_group: The hdf5 group containing the child to be loaded

        """
        if isinstance(hdf5_group, pt.link.SoftLink):
            if with_links:
                # We end up here when auto-loading a soft link
                self._tree_load_link(parent_traj_node, load_data=load_data, traj=trajectory,
                                     as_new=as_new, hdf5_soft_link=hdf5_group)
                return
            else:
                raise RuntimeError('`%s` of `%s` is a link but you set ``with_links=False``. '
                                   'I am not allowed to load the link.' %
                                   (hdf5_group._v_name, parent_traj_node.v_full_name))


        name = hdf5_group._v_name
        is_leaf = self._all_get_from_attrs(hdf5_group, HDF5StorageService.LEAF)
        in_trajectory = name in parent_traj_node._children

        if is_leaf:
            # In case we have a leaf node, we need to check if we have to create a new
            # parameter or result

            if in_trajectory:
                instance = parent_traj_node._children[name]
            # Otherwise we need to create a new instance
            else:
                instance, range_length = self._tree_create_leaf(name, trajectory, hdf5_group)

                if range_length is not None and range_length != len(trajectory):
                    raise RuntimeError('Something is completely odd. You load parameter'
                               ' `%s` of length %d into a trajectory of length'
                               ' %d. They should be equally long!' %
                               (name, range_length, len(trajectory)))

                # Add the instance to the trajectory tree
                parent_traj_node._nn_interface._add_generic(parent_traj_node,
                                                            type_name=nn.LEAF,
                                                            group_type_name=nn.GROUP,
                                                            args=(instance,), kwargs={},
                                                            add_prefix=False,
                                                            check_naming=False)

                # If it has a range we add it to the explored parameters
                if range_length:
                    trajectory._explored_parameters[instance.v_full_name] = instance

            self._prm_load_parameter_or_result(instance, load_data=load_data,
                                               _hdf5_group=hdf5_group)
            if as_new:
                instance._stored = False

            # Signal completed node loading
            self._node_processing_timer.signal_update()

        else:
            if in_trajectory:
                traj_group = parent_traj_node._children[name]

                if load_data == pypetconstants.OVERWRITE_DATA:
                    traj_group.v_annotations.f_empty()
                    traj_group.v_comment = ''
            else:
                if HDF5StorageService.CLASS_NAME in hdf5_group._v_attrs:
                    class_name = self._all_get_from_attrs(hdf5_group,
                                                          HDF5StorageService.CLASS_NAME)
                    class_constructor = trajectory._create_class(class_name)
                    instance = trajectory._construct_instance(class_constructor, name)
                    args = (instance,)
                else:
                    args = (name,)
                # If the group does not exist create it'
                traj_group = parent_traj_node._nn_interface._add_generic(parent_traj_node,
                                                                        type_name=nn.GROUP,
                                                                        group_type_name=nn.GROUP,
                                                                        args=args,
                                                                        kwargs={},
                                                                        add_prefix=False,
                                                                        check_naming=False)

            # Load annotations and comment
            self._grp_load_group(traj_group, load_data=load_data, with_links=with_links,
                                 recursive=recursive, _traj=trajectory, _as_new=as_new,
                                 _hdf5_group=hdf5_group)

    def _tree_load_link(self, new_traj_node, load_data, traj, as_new, hdf5_soft_link):
        """Loads a link
        
        :param new_traj_node: Node in traj containing link 
        :param load_data: How to load data in the linked node
        :param traj: The trajectory
        :param as_new: If data in linked node should be loaded as new
        :param hdf5_soft_link: The hdf5 soft link

        """
        try:
            linked_group = hdf5_soft_link()
            link_name = hdf5_soft_link._v_name

            if (not link_name in new_traj_node._links or
                        load_data==pypetconstants.OVERWRITE_DATA):

                link_location = linked_group._v_pathname
                full_name = '.'.join(link_location.split('/')[2:])
                if not full_name in traj:
                    self._tree_load_sub_branch(traj, full_name,
                                               load_data=pypetconstants.LOAD_SKELETON,
                                               with_links=False, recursive=False, trajectory=traj,
                                               as_new=as_new, hdf5_group=self._trajectory_group)
                if not link_name in new_traj_node._links:
                    new_traj_node._nn_interface._create_link(new_traj_node ,
                                                                   link_name,
                                                                   traj.f_get(full_name),
                                                                   check_naming=False)
                elif load_data == pypetconstants.OVERWRITE_DATA:
                    new_traj_node.f_remove_link(link_name)
                    new_traj_node._nn_interface._create_link(new_traj_node ,
                                                               link_name,
                                                               traj.f_get(full_name),
                                                               check_naming=False)
                else:
                    raise RuntimeError('You shall not pass!')
        except pt.NoSuchNodeError:
            self._logger.error('Link `%s` under `%s` is broken, cannot load it, '
                               'I will ignore it, you have to '
                               'manually delete it!' %
                               (hdf5_soft_link._v_name, new_traj_node.v_full_name))

    def _tree_store_nodes(self, parent_traj_node, name, store_data, with_links, recursive,
                          parent_hdf5_group):
        """Stores a node to hdf5 and if desired stores recursively everything below it.

        :param parent_traj_node: The parental node
        :param name: Name of node to be stored
        :param store_data: How to store data
        :param with_links: If links should be stored
        :param recursive: Whether to store recursively the subtree
        :param parent_hdf5_group: Parent hdf5 group

        """
        # Check if we create a link
        if name in parent_traj_node._links:
            if with_links:
                self._tree_store_link(parent_traj_node, name, parent_hdf5_group)
            return

        traj_node = parent_traj_node._children[name]

        # If the node does not exist in the hdf5 file create it
        if not hasattr(parent_hdf5_group, name):
            newly_created = True
            new_hdf5_group = ptcompat.create_group(self._hdf5file, where=parent_hdf5_group,
                                                   name=name, filters=self._all_get_filters())
        else:
            newly_created = False
            new_hdf5_group = getattr(parent_hdf5_group, name)

        if traj_node.v_is_leaf:
            self._prm_store_parameter_or_result(traj_node, store_data=store_data,
                                                 _hdf5_group=new_hdf5_group,
                                                _newly_created=newly_created)
            self._node_processing_timer.signal_update()

        else:
            self._grp_store_group(traj_node, store_data=store_data, with_links=with_links,
                                  recursive=recursive,
                                  _hdf5_group=new_hdf5_group,
                                  _newly_created=newly_created)

    def _tree_store_link(self, node_in_traj, link, hdf5_group):
        """Creates a soft link.
        
        :param node_in_traj: parental node
        :param store_data: how to store data
        :param link: name of link
        :param hdf5_group: current parental hdf5 group
        """

        if hasattr(hdf5_group, link):
            return

        linked_traj_node = node_in_traj._links[link]
        linking_name = linked_traj_node.v_full_name.replace('.','/')
        linking_name = '/' + self._trajectory_name + '/' + linking_name
        try:
            to_link_hdf5_group = ptcompat.get_node(self._hdf5file,
                                                   where=linking_name)
        except pt.NoSuchNodeError:
            self._logger.info('Could not store link `%s` under `%s` immediately, '
                                 'need to store `%s` first.' % (link,
                                                            node_in_traj.v_full_name,
                                                            linked_traj_node.v_full_name))
            root = node_in_traj._nn_interface._root_instance
            self._tree_store_sub_branch(root, linked_traj_node.v_full_name,
                                        store_data=pypetconstants.STORE_DATA_SKIPPING,
                                        with_links=False, recursive=False,
                                        hdf5_group=self._trajectory_group)
            to_link_hdf5_group = ptcompat.get_node(self._hdf5file,
                                                   where=linking_name)
        ptcompat.create_soft_link(self._hdf5file, where=hdf5_group,
                                  name=link,
                                  target=to_link_hdf5_group)

    ######################## Storing a Single Run ##########################################

    def _srn_store_single_run(self, traj, store_final=False,
                              store_data=pypetconstants.STORE_DATA,
                              store_full_in_run=False):
        """ Stores a single run instance to disk (only meta data)"""

        if store_data != pypetconstants.STORE_NOTHING:
            if store_full_in_run:
                self._logger.info('Storing full date tree of trajectory during single run!')
                for child in traj._children:
                    self._tree_store_tree(traj_node=traj, child_name=child,
                                          store_data=store_data, with_links=True,
                                          recursive=True,
                                          _parent_hdf5_group=self._trajectory_group)
            else:
                self._logger.info('Storing Data of single run `%s`.' % traj.v_crun)
                for group_name in traj._run_parent_groups:
                    group = traj._run_parent_groups[group_name]
                    if group.f_contains(traj.v_crun):
                        self._tree_store_tree(group, traj.v_crun, store_data=store_data,
                                              with_links=True,
                                              recursive=True,
                                              _parent_hdf5_group=None)

        if store_final:
            self._logger.info('Finishing Storage of single run `%s`.' % traj.v_crun)
            idx = traj.v_idx

            add_table = self._overview_explored_parameters_runs

            # For better readability and if desired add the explored parameters to the results
            # Also collect some summary information about the explored parameters
            # So we can add this to the `run` table
            run_summary = self._srn_add_explored_params(traj.v_crun,
                                                        compat.listvalues(
                                                            traj._explored_parameters),
                                                        add_table)

            # Finally, add the real run information to the `run` table
            runtable = getattr(self._overview_group, 'runs')

            # If the table is not large enough already (maybe because the trajectory got expanded
            # We have to manually increase it here
            actual_rows = runtable.nrows
            if idx + 1 > actual_rows:
                self._all_fill_run_table_with_dummys(actual_rows, idx + 1)

            insert_dict = self._all_extract_insert_dict(traj, runtable.colnames)
            insert_dict['parameter_summary'] = run_summary
            insert_dict['completed'] = 1

            self._hdf5file.flush()
            self._all_add_or_modify_row(traj, insert_dict, runtable,
                                        index=idx, flags=(HDF5StorageService.MODIFY_ROW,))

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
        paramdescriptiondict = {'name': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'value': pt.StringCol(pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH)}

        location = 'results.runs.' + run_name

        where = location
        where = where.replace('.', '/')

        if not where in self._trajectory_group:
            if create_run_group:
                self._all_create_or_get_groups(location)
            else:
                add_table = False

        if add_table:

            rungroup = getattr(self._trajectory_group, where)

            # Check if the table already exists
            if 'explored_parameters' in rungroup:
                # This can happen if trajectories are merged
                # If the number of explored parameters changed due to merging we
                # need to create the table new in order to show the correct parameters
                paramtable = getattr(rungroup, 'explored_parameters')

                # If more parameters became explored we need to create the table new
                if paramtable.nrows != len(paramlist):
                    del paramtable
                    ptcompat.remove_node(self._hdf5file, where=rungroup,
                                         name='explored_parameters')
                else:
                    add_table = False

            if not 'explored_parameters' in rungroup:
                paramtable = ptcompat.create_table(self._hdf5file,
                                                   where=rungroup,
                                                   name='explored_parameters',
                                                   description=paramdescriptiondict,
                                                   title='explored_parameters',
                                                   filters=self._all_get_filters())

        runsummary = ''
        paramlist = sorted(paramlist, key=lambda name: name.v_name + name.v_location)
        for idx, expparam in enumerate(paramlist):

            # Create the run summary for the `run` overview
            if idx > 0:
                runsummary += ',   '

            valstr = expparam.f_val_to_str()

            if len(valstr) >= pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH:
                valstr = valstr[0:pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH - 3]
                valstr += '...'

            if expparam.v_name in runsummary:
                param_name = expparam.v_full_name
            else:
                param_name = expparam.v_name

            runsummary = runsummary + param_name + ': ' + valstr

            # If Add the explored parameter overview table if dersired and necessary
            if add_table:
                self._all_store_param_or_result_table_entry(expparam, paramtable,
                                                            (HDF5StorageService.ADD_ROW,))

        return runsummary


    ################# Methods used across Storing and Loading different Items #####################

    @staticmethod
    def _all_find_param_or_result_entry_and_return_iterator(param_or_result, table):
        """Searches for a particular entry in `table` based on the name and location
        of `param_or_result` and returns an iterator over the found rows
        (should contain only a single row).

        """
        location = param_or_result.v_location
        name = param_or_result.v_name

        condvars = {'namecol': table.cols.name, 'locationcol': table.cols.location,
                    'name': name, 'location': location}

        condition = """(namecol == name) & (locationcol == location)"""

        return table.where(condition, condvars=condvars)


    @staticmethod
    def _all_get_table_name(where, creator_name):
        """Returns an overview table name for a given subtree name

        :param where:

            Either `parameters`, `config`, `derived_parameters`, or `results`

        :param creator_name:

            Either `trajectory` or `run_XXXXXXXXX`

        :return: Name of overview table

        """
        if where in ['config', 'parameters']:
            return where
        else:
            if creator_name == 'trajectory' or creator_name == pypetconstants.RUN_NAME_DUMMY:
                return '%s_trajectory' % where
            else:
                return '%s_runs' % where


    def _all_store_param_or_result_table_entry(self, instance, table, flags,
                                               additional_info=None):
        """Stores a single row into an overview table

        :param instance: A parameter or result instance

        :param table: Table where row will be inserted

        :param flags:

            Flags how to insert into the table. Potential Flags are
            `ADD_ROW`, `REMOVE_ROW`, `MODIFY_ROW`

        :param additional_info:

            Dictionary containing information that cannot be extracted from
            `instance`, but needs to be inserted, too.


        """
        # assert isinstance(table, pt.Table)

        location = instance.v_location
        name = instance.v_name
        fullname = instance.v_full_name

        if (flags == (HDF5StorageService.ADD_ROW,) and table.nrows < 2
                and 'location' in table.colnames):
            # We add the modify row option here because you cannot delete the very first
            # row of the table, so there is the rare condition, that the row might already
            # exist.
            # We also need to check if 'location' is in the columns in order to avoid
            # confusion with the smaller explored parameter overviews
            flags = (HDF5StorageService.ADD_ROW, HDF5StorageService.MODIFY_ROW)

        if flags == (HDF5StorageService.ADD_ROW,):
            # If we are sure we only want to add a row we do not need to search!
            condvars = None
            condition = None
        else:
            # Condition to search for an entry
            condvars = {'namecol': table.cols.name, 'locationcol': table.cols.location,
                        'name': name, 'location': location}

            condition = """(namecol == name) & (locationcol == location)"""

        colnames = set(table.colnames)

        if HDF5StorageService.REMOVE_ROW in flags:
            # If we want to remove a row, we don't need to extract information
            insert_dict = {}
        else:
            # Extract information to insert from the instance and the additional info dict
            insert_dict = self._all_extract_insert_dict(instance, colnames, additional_info)

        # Write the table entry
        self._all_add_or_modify_row(fullname, insert_dict, table, condition=condition,
                                    condvars=condvars, flags=flags)


    def _all_get_or_create_table(self, where, tablename, description, expectedrows=None):
        """Creates a new table, or if the table already exists, returns it."""
        where_node = ptcompat.get_node(self._hdf5file, where)

        if not tablename in where_node:
            if not expectedrows is None:
                table = ptcompat.create_table(self._hdf5file,
                                              where=where_node, name=tablename,
                                              description=description, title=tablename,
                                              expectedrows=expectedrows,
                                              filters=self._all_get_filters())
            else:
                table = ptcompat.create_table(self._hdf5file,
                                              where=where_node, name=tablename,
                                              description=description, title=tablename,
                                              filters=self._all_get_filters())
        else:
            table = ptcompat.get_child(where_node, tablename)

        return table

    def _all_get_node_by_name(self, name):
        """Returns an HDF5 node by the path specified in `name`"""
        path_name = name.replace('.', '/')
        where = '/%s/%s' % (self._trajectory_name, path_name)
        return ptcompat.get_node(self._hdf5file, where=where)

    @staticmethod
    def _all_attr_equals(ptitem, name, value):
        """Checks if a given hdf5 node attribute exists and if so if it matches the `value`."""
        try:
            return ptitem._v_attrs[name] == value
        except KeyError:
            return False

    @staticmethod
    def _all_get_from_attrs(ptitem, name):
        """Gets an attribute `name` from `ptitem`, returns None if attribute does not exist."""
        # if name in ptitem._v_attrs:
        # return ptitem._v_attrs[name]
        # else:
        # return None
        try:
            return ptitem._v_attrs[name]
        except KeyError:
            return None

    @staticmethod
    def _all_set_attributes_to_recall_natives(data, ptitem, prefix):
        """Stores original data type to hdf5 node attributes for preserving the data type.

        :param data:

            Data to be stored

        :param ptitem:

            HDF5 node to store data types as attributes. Can also be just a PTItemMock.

        :param prefix:

            String prefix to label and name data in HDF5 attributes

        """



        # If `data` is a container, remember the container type
        if type(data) is tuple:
            ptcompat.set_attribute(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_TUPLE)

        elif type(data) is list:
            ptcompat.set_attribute(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_LIST)

        elif type(data) is np.ndarray:
            ptcompat.set_attribute(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_NDARRAY)

        elif type(data) is np.matrix:
            ptcompat.set_attribute(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_MATRIX)

        elif type(data) in pypetconstants.PARAMETER_SUPPORTED_DATA:
            ptcompat.set_attribute(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_SCALAR)

            strtype = type(data).__name__

            if not strtype in pypetconstants.PARAMETERTYPEDICT:
                raise TypeError('I do not know how to handle `%s` its type is `%s`.' %
                                (str(data), repr(type(data))))

            ptcompat.set_attribute(ptitem, prefix + HDF5StorageService.SCALAR_TYPE, strtype)

        elif type(data) is dict:
            ptcompat.set_attribute(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_DICT)

        else:
            raise TypeError('I do not know how to handle `%s` its type is `%s`.' %
                            (str(data), repr(type(data))))

        if type(data) in (list, tuple):
            # If data is a list or tuple we need to remember the data type of the elements
            # in the list or tuple.
            # We do NOT need to remember the elements of `dict` explicitly, though.
            # `dict` is stored
            # as an `ObjectTable` and thus types are already conserved.
            if len(data) > 0:
                strtype = type(data[0]).__name__

                if not strtype in pypetconstants.PARAMETERTYPEDICT:
                    raise TypeError('I do not know how to handle `%s` its type is '
                                    '`%s`.' % (str(data), strtype))

                ptcompat.set_attribute(ptitem, prefix +
                                       HDF5StorageService.SCALAR_TYPE, strtype)
        elif (type(data) in (np.ndarray, np.matrix) and
                  np.issubdtype(data.dtype, compat.unicode_type)):
            ptcompat.set_attribute(ptitem, prefix +
                                   HDF5StorageService.SCALAR_TYPE, compat.unicode_type.__name__)

    def _all_recall_native_type(self, data, ptitem, prefix):
        """Checks if loaded data has the type it was stored in. If not converts it.

        :param data: Data item to be checked and converted
        :param ptitem: HDf5 Node or Leaf from where data was loaded
        :param prefix: Prefix for recalling the data type from the hdf5 node attributes

        :return:

            Tuple, first item is the (converted) `data` item, second boolean whether
            item was converted or not.

        """
        typestr = self._all_get_from_attrs(ptitem, prefix + HDF5StorageService.SCALAR_TYPE)
        type_changed = False

        # Check what the original data type was from the hdf5 node attributes
        if self._all_attr_equals(ptitem, prefix + HDF5StorageService.COLL_TYPE,
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
                if typestr != type(data).__name__:

                    if typestr == compat.unicode_type.__name__:
                        data = data.decode(self._encoding)
                    else:
                        try:
                            data = pypetconstants.PARAMETERTYPEDICT[typestr](data)
                        except KeyError:
                            # For compatibility with files from older pypet versions
                            data = pypetconstants.COMPATPARAMETERTYPEDICT[typestr](data)

                    type_changed = True


        elif (self._all_attr_equals(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                    HDF5StorageService.COLL_TUPLE) or
                  self._all_attr_equals(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                        HDF5StorageService.COLL_LIST)):
            # Here data item was originally a tuple or a list

            if not isinstance(data, (list, tuple)):
                # If the original type cannot be recalled, first convert it to a list
                type_changed = True
                data = list(data)

            if len(data) > 0:
                first_item = data[0]
            else:
                first_item = None

            if not first_item is None:
                # Check if the type of the first item was conserved
                if not typestr == type(first_item).__name__:

                    if not isinstance(data, list):
                        data = list(data)

                    # If type was not conserved we need to convert all items
                    # in the list or tuple
                    for idx, item in enumerate(data):
                        if typestr == compat.unicode_type.__name__:
                            data[idx] = data[idx].decode(self._encoding)
                        else:
                            try:
                                data[idx] = pypetconstants.PARAMETERTYPEDICT[typestr](item)
                            except KeyError:
                                # For compatibility with files from older pypet versions:
                                data[idx] = pypetconstants.COMPATPARAMETERTYPEDICT[typestr](item)
                        type_changed = True

            if self._all_attr_equals(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                     HDF5StorageService.COLL_TUPLE):
                # If it was originally a tuple we need to convert it back to tuple
                if not isinstance(data, tuple):
                    data = tuple(data)
                    type_changed = True

        elif isinstance(data, np.ndarray):

            if typestr == compat.unicode_type.__name__:
                data = np.core.defchararray.decode(data, self._encoding)
                type_changed = True

            if (self._all_attr_equals(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                      HDF5StorageService.COLL_MATRIX)):
                # Here data item was originally a matrix
                data = np.matrix(data)
                type_changed = True

        return data, type_changed

    def _all_add_or_modify_row(self, item_name, insert_dict, table, index=None, condition=None,
                               condvars=None,
                               flags=(ADD_ROW, MODIFY_ROW,)):
        """Adds or changes a row in a pytable.

        :param item_name: Name of item, the row is about, only important for throwing errors.

        :param insert_dict:

            Dictionary of data that is about to be inserted into the pytables row.

        :param table:

            The table to insert or modify a row in

        :param index:

            Index of row to be modified. Instead of an index a search condition can be
            used as well, see below.

        :param condition:

            Condition to search for in the table

        :param condvars:

            Variables for the search condition

        :param flags:

            Flags whether to add, modify, or remove a row in the table


        """

        # You can only specify either an index or a condition not both
        if index is not None and condition is not None:
            raise ValueError('Please give either a condition or an index or none!')
        elif condition is not None:
            row_iterator = table.where(condition, condvars=condvars)
        elif index is not None:
            row_iterator = table.iterrows(index, index + 1)
        else:
            row_iterator = None

        try:
            row = next(row_iterator)
        except TypeError:
            row = None
        except StopIteration:
            row = None

        multiple_entries = []

        if ((HDF5StorageService.MODIFY_ROW in flags or HDF5StorageService.ADD_ROW in flags) and
                    HDF5StorageService.REMOVE_ROW in flags):
            # You cannot remove and modify or add at the same time
            raise ValueError('You cannot add or modify and remove a row at the same time.')

        if row is None and HDF5StorageService.ADD_ROW in flags:
            # Here we add a new row

            row = table.row

            self._all_insert_into_row(row, insert_dict)

            row.append()

        elif row is not None and HDF5StorageService.MODIFY_ROW in flags:
            # Here we modify an existing row

            self._all_insert_into_row(row, insert_dict)

            row.update()

        elif HDF5StorageService.REMOVE_ROW in flags:
            # Here we delete an existing row

            if row is not None:
                # Only delete if the row does exist otherwise we do not have to do anything
                row_number = row.nrow

                try:
                    for new_row in row_iterator:
                        new_row_number = new_row.nrow
                        if new_row_number > row_number:
                            new_row_number -= 1 # -1 because we will remove the current row
                        multiple_entries.append(new_row_number)
                        # later on
                except StopIteration:
                    pass

                try:
                    ptcompat.remove_rows(table, start=row_number, stop=row_number+1)
                except NotImplementedError:
                    pass
                    # We get here if we try to remove the last row of a table
                    # there is nothing we can do but keep it :-(
        else:
            raise ValueError('Something is wrong, you might not have found '
                             'a row, or your flags are not set appropriately')

        # Check if there are several entries which should not happen
        # and correct for that
        if len(multiple_entries) == 0:
            try:
                for new_row in row_iterator:
                    multiple_entries.append(new_row.nrow)
            except TypeError:
                pass
            except StopIteration:
                pass

        table.flush()

        if len(multiple_entries) > 0:
            self._logger.error('There is something wrong, `%s` '
                               'appears more than once in table %s.'
                               % (item_name, table._v_name))
            self._srvc_fix_table(table, multiple_entries)

        # Check if we added something. Note that row is also not None in case REMOVE_ROW,
        # then it refers to the deleted row
        if HDF5StorageService.REMOVE_ROW not in flags and row is None:
            raise RuntimeError('Could not add or modify entries of `%s` in '
                               'table %s' % (item_name, table._v_name))

    def _srvc_fix_table(self, table, multiple_entries):
        """ Fixes mutliple entries in a table.

        This may happen due to deleting leaves,
        because the last row cannot be removed with PyTables

        """
        self._logger.error('I will fix this by removing all entries except the last')
        removed = 0
        for row_number in sorted(multiple_entries):
            ptcompat.remove_rows(table, start=row_number - removed,
                                 stop=row_number - removed + 1)
            removed += 1 # keep track of how many have been removed, because
                         # the index of the later rows are decreased thereby
            table.flush()

    def _all_insert_into_row(self, row, insert_dict):
        """Copies data from `insert_dict` into a pytables `row`."""
        for key, val in insert_dict.items():
            try:
                row[key] = val
            except KeyError as ke:
                self._logger.warning('Could not write `%s` into a table, ' % key + repr(ke))


    def _all_extract_insert_dict(self, item, colnames, additional_info=None):
        """Extracts information from a given item to be stored into a pytable row.

        Items can be a variety of things here, trajectories, single runs, group node,
        parameters, results.

        :param item: Item from which data should be extracted

        :param colnames: Names of the columns in the pytable

        :param additional_info: (dict)

            Additional information that should be stored into the pytable row that cannot be
            read out from `item`.

        :return: Dictionary containing the data to be inserted into a row

        """
        insert_dict = {}

        if 'length' in colnames:
            insert_dict['length'] = len(item)

        if 'comment' in colnames:
            comment = self._all_cut_string(compat.tobytes(item.v_comment),
                                           pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH,
                                           self._logger)

            insert_dict['comment'] = comment

        if 'location' in colnames:
            insert_dict['location'] = compat.tobytes(item.v_location)

        if 'name' in colnames:
            name = item._name if (not item.v_is_root or not item.v_is_run) else item._crun
            insert_dict['name'] = compat.tobytes(name)

        if 'class_name' in colnames:
            insert_dict['class_name'] = compat.tobytes(item.f_get_class_name())

        if 'value' in colnames:
            insert_dict['value'] = self._all_cut_string(
                compat.tobytes(item.f_val_to_str()),
                pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH,
                self._logger)

        if 'example_item_run_name' in colnames:
            insert_dict['example_item_run_name'] = additional_info['example_item_run_name']

        if 'idx' in colnames:
            insert_dict['idx'] = item.v_idx

        if 'time' in colnames:
            time_ = item._time if not item._is_run else item._time_run
            insert_dict['time'] = time_

        if 'timestamp' in colnames:
            timestamp = item._timestamp if not item._is_run else item._timestamp_run
            insert_dict['timestamp'] = timestamp

        if 'range' in colnames:
            insert_dict['range'] = self._all_cut_string(
                compat.tobytes(repr(item.f_get_range())),
                pypetconstants.HDF5_STRCOL_MAX_ARRAY_LENGTH,
                self._logger)

        # To allow backwards compatibility
        if 'array' in colnames:
            insert_dict['array'] = self._all_cut_string(
                compat.tobytes(repr(item.f_get_range())),
                pypetconstants.HDF5_STRCOL_MAX_ARRAY_LENGTH,
                self._logger)

        if 'version' in colnames:
            insert_dict['version'] = compat.tobytes(item.v_version)

        if 'python' in colnames:
            insert_dict['python'] = compat.tobytes(item.v_python)

        if 'finish_timestamp' in colnames:
            insert_dict['finish_timestamp'] = item._finish_timestamp_run

        if 'runtime' in colnames:
            runtime = item._runtime_run
            if len(runtime) > pypetconstants.HDF5_STRCOL_MAX_RUNTIME_LENGTH:
                # If string is too long we cut the microseconds
                runtime = runtime.split('.')[0]

            insert_dict['runtime'] = compat.tobytes(runtime)

        if 'short_environment_hexsha' in colnames:
            insert_dict['short_environment_hexsha'] = compat.tobytes(
                item.v_environment_hexsha[0:7])

        return insert_dict

    @staticmethod
    def _all_cut_string(string, max_length, logger):
        """Cuts string data to the maximum length allowed in a pytables column
        if string is too long.

        :param string: String to be cut
        :param max_length: Maximum allowed string length
        :param logger: Logger where messages about truncating should be written

        :return: String, cut if too long

        """
        if len(string) > max_length:
            logger.debug('The string `%s` was too long I truncated it to'
                         ' %d characters' %
                         (string, max_length))
            string = string[0:max_length - 3] + compat.tobytes('...')

        return string

    def _all_create_or_get_groups(self, key):
        """Creates new or follows existing group nodes along a given colon separated `key`.

        :param key:

            Colon separated path along hdf5 file, e.g. `parameters.mobiles.cars`.

        :return:

            Final group node, e.g. group node with name `cars`.

        """
        newhdf5_group = self._trajectory_group
        split_key = key.split('.')
        created = False
        for name in split_key:
            if not name in newhdf5_group:
                newhdf5_group = ptcompat.create_group(self._hdf5file, where=newhdf5_group, name=name,
                                                     title=name, filters=self._all_get_filters())
                created = True
            else:
                newhdf5_group = ptcompat.get_child(newhdf5_group, name)

        return newhdf5_group, created


    ################# Storing and loading Annotations ###########################################

    def _ann_store_annotations(self, item_with_annotations, node, overwrite=False):
        """Stores annotations into an hdf5 file."""

        # If we overwrite delete all annotations first
        if overwrite is True or overwrite == 'v_annotations':
            annotated = self._all_get_from_attrs(node, HDF5StorageService.ANNOTATED)
            if annotated:
                current_attrs = node._v_attrs
                for attr_name in current_attrs._v_attrnames:
                    if attr_name.startswith(HDF5StorageService.ANNOTATION_PREFIX):
                        delattr(current_attrs, attr_name)
                delattr(current_attrs, HDF5StorageService.ANNOTATED)
                self._hdf5file.flush()

        # Only store annotations if the item has some
        if not item_with_annotations.v_annotations.f_is_empty():

            anno_dict = item_with_annotations.v_annotations.__dict__

            current_attrs = node._v_attrs

            changed = False

            for field_name in anno_dict:
                val = anno_dict[field_name]

                field_name_with_prefix = HDF5StorageService.ANNOTATION_PREFIX + field_name
                if field_name_with_prefix not in current_attrs:
                    # Only store *new* annotations, if they already exist on disk, skip storage
                    setattr(current_attrs, field_name_with_prefix, val)
                    changed = True

            if changed:
                setattr(current_attrs, HDF5StorageService.ANNOTATED, True)
                self._hdf5file.flush()

    def _ann_load_annotations(self, item_with_annotations, node):
        """Loads annotations from disk."""

        annotated = self._all_get_from_attrs(node, HDF5StorageService.ANNOTATED)

        if annotated:

            annotations = item_with_annotations.v_annotations

            # You can only load into non-empty annotations, to prevent overwriting data in RAM
            if not annotations.f_is_empty():
                raise TypeError('Loading into non-empty annotations!')

            current_attrs = node._v_attrs

            for attr_name in current_attrs._v_attrnames:

                if attr_name.startswith(HDF5StorageService.ANNOTATION_PREFIX):
                    key = attr_name
                    key = key.replace(HDF5StorageService.ANNOTATION_PREFIX, '')

                    data = getattr(current_attrs, attr_name)
                    setattr(annotations, key, data)


    ########################## Storing/Loading Groups ################################

    def _grp_store_group(self, traj_group, store_data=pypetconstants.STORE_DATA,
                         with_links=True, recursive=False,
                         _hdf5_group=None, _newly_created=False):
        """Stores a group node.

        For group nodes only annotations and comments need to be stored.

        """
        if store_data == pypetconstants.STORE_NOTHING:
            return
        elif store_data == pypetconstants.STORE_DATA_SKIPPING and traj_group._stored:
            self._logger.debug('Already found `%s` on disk I will not store it!' %
                                   traj_group.v_full_name)
        else:
            if _hdf5_group is None:
                _hdf5_group, _newly_created = self._all_create_or_get_groups(traj_group.v_full_name)

            overwrite = store_data == pypetconstants.OVERWRITE_DATA

            if (traj_group.v_comment != '' and
                    (HDF5StorageService.COMMENT not in _hdf5_group._v_attrs or overwrite)):
                setattr(_hdf5_group._v_attrs, HDF5StorageService.COMMENT, traj_group.v_comment)

            if ((_newly_created or overwrite) and
                type(traj_group) not in (nn.NNGroupNode, nn.ConfigGroup, nn.ParameterGroup,
                                             nn.DerivedParameterGroup, nn.ResultGroup)):
                # We only store the name of the class if it is not one of the standard groups,
                # that are always used.
                setattr(_hdf5_group._v_attrs, HDF5StorageService.CLASS_NAME,
                        traj_group.f_get_class_name())

            self._ann_store_annotations(traj_group, _hdf5_group, overwrite=overwrite)
            self._hdf5file.flush()
            traj_group._stored = True

        if recursive:
            # And if desired store recursively the subtree
            self._node_processing_timer.signal_update()

            for child in compat.iterkeys(traj_group._children):
                self._tree_store_nodes(traj_group, child, store_data=store_data,
                                       with_links=with_links, recursive=recursive,
                                       parent_hdf5_group=_hdf5_group)

    def _grp_load_group(self, traj_group, load_data=pypetconstants.LOAD_DATA, with_links=True,
                        recursive=False, _traj=None, _as_new=False, _hdf5_group=None):
        """Loads a group node and potentially everything recursively below"""
        if load_data == pypetconstants.LOAD_NOTHING:
            return

        elif load_data == pypetconstants.OVERWRITE_DATA:
            traj_group.v_annotations.f_empty()
            traj_group.v_comment = ''

        if _hdf5_group is None:
            _hdf5_group = self._all_get_node_by_name(traj_group.v_full_name)
            _traj = traj_group.v_root

        self._all_load_skeleton(traj_group, _hdf5_group)
        traj_group._stored = not _as_new

        if recursive:
            # We load recursively everything below it
            self._node_processing_timer.signal_update()

            children = _hdf5_group._v_groups
            for new_hdf5_group_name in children:
                new_hdf5_group = children[new_hdf5_group_name]
                self._tree_load_nodes(traj_group, load_data=load_data, with_links=with_links,
                                      recursive=recursive, trajectory=_traj, as_new=_as_new,
                                      hdf5_group=new_hdf5_group)

        if recursive and with_links:
            links = _hdf5_group._v_links
            for new_hdf5_group_name in links:
                new_hdf5_group = links[new_hdf5_group_name]
                self._tree_load_link(traj_group, load_data=load_data, traj=_traj, as_new=_as_new,
                                     hdf5_soft_link=new_hdf5_group)

    def _all_load_skeleton(self, traj_node, hdf5_group):
        """Reloads skeleton data of a tree node"""
        if traj_node.v_annotations.f_is_empty():
            self._ann_load_annotations(traj_node, hdf5_group)
        if traj_node.v_comment == '':
            comment = self._all_get_from_attrs(hdf5_group, HDF5StorageService.COMMENT)
            if comment is None:
                comment = ''
            traj_node.v_comment = comment

    ################# Storing and Loading Parameters ############################################

    @staticmethod
    def _prm_extract_missing_flags(data_dict, flags_dict):
        """Extracts storage flags for data in `data_dict`
        if they were not specified in `flags_dict`.

        See :const:`~pypet.storageservice.HDF5StorageService.TYPE_FLAG_MAPPING`
        for how to store different types of data per default.

        """
        for key, data in compat.iteritems(data_dict):
            if not key in flags_dict:
                dtype = type(data)
                if dtype in HDF5StorageService.TYPE_FLAG_MAPPING:
                    flags_dict[key] = HDF5StorageService.TYPE_FLAG_MAPPING[dtype]
                else:
                    raise pex.NoSuchServiceError('I cannot store `%s`, I do not understand the'
                                                 'type `%s`.' % (key, str(dtype)))

    def _prm_meta_remove_summary(self, instance):
        """Changes a summary table entry if the current `instance` is removed from the trajectory
        and from disk.

        The number of items represented by a summary is decreased, if the
        number of items shrinks to zero the whole row is deleted.

        """
        split_name = instance.v_full_name.split('.')
        where = split_name[0]

        if where in ['derived_parameters', 'results']:
            # There are only summaries for derived parameters and results
            creator_name = instance.v_run_branch
            if (creator_name.startswith(pypetconstants.RUN_NAME) and
                creator_name != pypetconstants.RUN_NAME_DUMMY):
                run_mask = pypetconstants.RUN_NAME + 'X' * pypetconstants.FORMAT_ZEROS

                split_name[instance._run_branch_pos - 1] = run_mask

                new_full_name = '.'.join(split_name)
                old_full_name = instance.v_full_name
                instance._rename(new_full_name)
                try:
                    table_name = where + '_runs_summary'
                    table = getattr(self._overview_group, table_name)

                    row_iterator = self._all_find_param_or_result_entry_and_return_iterator(
                        instance, table)

                    row = next(row_iterator)

                    # Decrease the number of items represented by the summary
                    nitems = row['number_of_items'] - 1
                    row['number_of_items'] = nitems
                    row.update()

                    table.flush()

                    multiple_entries = []

                    try:
                        for new_row in row_iterator:
                            multiple_entries.append(new_row.nrow)
                    except StopIteration:
                        pass

                    if len(multiple_entries) > 0:
                        self._logger.error('There is something wrong, `%s` '
                                           'appears more than once in table %s.'
                                           % (instance.v_full_name, table._v_name))
                        self._srvc_fix_table(table, multiple_entries)

                    if nitems == 0:
                        # Here the summary became obsolete
                        self._all_store_param_or_result_table_entry(
                            instance,
                            table,
                            flags=(HDF5StorageService.REMOVE_ROW,))


                except pt.NoSuchNodeError:
                    pass
                except StopIteration:
                    pass
                finally:
                    # Get the old name back
                    instance._rename(old_full_name)

    def _all_meta_add_summary(self, instance):
        """Adds data to the summary tables and returns if `instance`s comment has to be stored.

        Also moves comments upwards in the hierarchy if purge_duplicate_comments is true
        and a lower index run has completed. Only necessary for *multiprocessing*.

        :return: Tuple

            * String specifying the subtree

            * Boolean whether to store the comment to `instance`s hdf5 node

        """
        definitely_store_comment = True

        split_name = instance.v_full_name.split('.')
        where = split_name[0]

        # Check if we are in the subtree that has runs overview tables
        creator_name = instance.v_run_branch
        if (creator_name.startswith(pypetconstants.RUN_NAME) and
                    creator_name != pypetconstants.RUN_NAME_DUMMY):

            try:
                # Get the overview table
                table_name = where + '_runs_summary'

                # Check if the overview table exists, otherwise skip the rest of
                # the meta adding
                if table_name in self._overview_group:
                    table = getattr(self._overview_group, table_name)
                else:
                    return where, definitely_store_comment
            except pt.NoSuchNodeError:
                return where, definitely_store_comment

            # Create the dummy name `result.run_XXXXXXXX` as a general mask and example item
            run_mask = pypetconstants.RUN_NAME + 'X' * pypetconstants.FORMAT_ZEROS

            split_name[instance._run_branch_pos - 1] = run_mask

            new_full_name = '.'.join(split_name)
            old_full_name = instance.v_full_name
            # Rename the item for easier storage
            instance._rename(new_full_name)
            try:

                # True if comment must be moved upwards to lower index
                erase_old_comment = False

                # Find the overview table entry

                row_iterator = \
                    self._all_find_param_or_result_entry_and_return_iterator(instance, table)

                row = None
                try:
                    row = next(row_iterator)
                except StopIteration:
                    pass

                if row is not None:
                    # If row found we need to increase the number of items
                    nitems = row['number_of_items'] + 1

                    # Get the run name of the example
                    example_item_run_name = compat.tostr(row['example_item_run_name'])

                    # Get the old comment:
                    location_string = compat.tostr(row['location'])
                    other_parent_node_name = location_string.replace(run_mask,
                                                                     example_item_run_name)
                    other_parent_node_name = '/' + self._trajectory_name + '/' + \
                                             other_parent_node_name.replace('.', '/')

                    # If the instance actually has the name of the run as it's own name
                    # We need this replacement as well:
                    instance_name = instance.v_name.replace(run_mask, example_item_run_name)
                    example_item_node = ptcompat.get_node(self._hdf5file,
                                                          where=other_parent_node_name,
                                                          name=instance_name)

                    # Check if comment is obsolete
                    example_comment = ''
                    if HDF5StorageService.COMMENT in example_item_node._v_attrs:
                        example_comment = str(
                            example_item_node._v_attrs[HDF5StorageService.COMMENT])
                    definitely_store_comment = instance.v_comment != example_comment

                    # We can rely on lexicographic comparisons with run indices
                    if creator_name < example_item_run_name:
                        # In case the statement is true and the comments are equal, we need
                        # to move the comment to a result or derived parameter with a lower
                        # run name:
                        if not definitely_store_comment:

                            # We need to purge the comment in the other result or derived parameter
                            erase_old_comment = True
                            definitely_store_comment = True

                            row['example_item_run_name'] = creator_name

                            row['value'] = self._all_cut_string(
                                instance.f_val_to_str(),
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
                                                 (instance.v_name, creator_name,
                                                  example_item_run_name))

                    row['number_of_items'] = nitems
                    row.update()

                    table.flush()

                    multiple_entries = []

                    try:
                        for new_row in row_iterator:
                            multiple_entries.append(new_row.nrow)
                    except StopIteration:
                        pass

                    if len(multiple_entries) > 0:
                        self._logger.error('There is something wrong, `%s` '
                                           'appears more than once in table %s.'
                                           % (instance.v_full_name, table._v_name))
                        self._srvc_fix_table(table, multiple_entries)

                    if (self._purge_duplicate_comments and erase_old_comment and
                                HDF5StorageService.COMMENT in example_item_node._v_attrs):
                        del example_item_node._v_attrs[HDF5StorageService.COMMENT]

                    self._hdf5file.flush()
                else:
                    self._all_store_param_or_result_table_entry(instance, table,
                                                                flags=(
                                                                    HDF5StorageService.ADD_ROW,),
                                                                additional_info={
                                                                    'example_item_run_name':
                                                                    creator_name})

                    definitely_store_comment = True

            # There are 2 cases of exceptions, either the table is switched off, or
            # the entry already exists, in both cases we  have to store the comments
            except pt.NoSuchNodeError:
                definitely_store_comment = True
            finally:
                # Get the old name back
                instance._rename(old_full_name)

        return where, definitely_store_comment

    def _prm_add_meta_info(self, instance, group, overwrite=False):
        """Adds information to overview tables and meta information to
        the `instance`s hdf5 `group`.

        :param instance: Instance to store meta info about
        :param group: HDF5 group of instance
        :param overwrite: If data should be explicitly overwritten

        """

        if overwrite:
            flags = (HDF5StorageService.ADD_ROW, HDF5StorageService.MODIFY_ROW)
        else:
            flags = (HDF5StorageService.ADD_ROW,)

        definitely_store_comment = True
        try:
            # Check if we need to store the comment. Maybe update the overview tables
            # accordingly if the current run index is lower than the one in the table.
            where, definitely_store_comment = self._all_meta_add_summary(instance)

            try:
                # Update the summary overview table
                table_name = self._all_get_table_name(where, instance.v_run_branch)

                table = getattr(self._overview_group, table_name)

                self._all_store_param_or_result_table_entry(instance, table,
                                                            flags=flags)
            except pt.NoSuchNodeError:
                pass
        except Exception as e:
            self._logger.error('Could not store information table due to `%s`.' % str(e))

        if ((not self._purge_duplicate_comments or definitely_store_comment) and
                    instance.v_comment != ''):
            # Only add the comment if necessary
            setattr(group._v_attrs, HDF5StorageService.COMMENT, instance.v_comment)

        # Add class name and whether node is a leaf to the HDF5 attributes
        setattr(group._v_attrs, HDF5StorageService.CLASS_NAME, instance.f_get_class_name())
        setattr(group._v_attrs, HDF5StorageService.LEAF, True)

        if instance.v_is_parameter and instance.f_has_range():
            # If the stored parameter was an explored one we need to mark this in the
            # explored overview table
            setattr(group._v_attrs, HDF5StorageService.LENGTH, instance.f_get_range_length())
            try:
                tablename = 'explored_parameters'
                table = getattr(self._overview_group, tablename)
                self._all_store_param_or_result_table_entry(instance, table,
                                                            flags=flags)
            except pt.NoSuchNodeError:
                pass
            except Exception as e:
                self._logger.error('Could not store information '
                                   'table due to `%s`.' % str(e))

    def _prm_store_parameter_or_result(self,
                                       instance,
                                       store_data=pypetconstants.STORE_DATA,
                                       store_flags=None,
                                       overwrite=None,
                                       with_links=False,
                                       recursive=False,
                                       _hdf5_group=None,
                                       _newly_created=False,
                                       **kwargs):
        """Stores a parameter or result to hdf5.

        :param instance:

            The instance to be stored

        :param store_data:

            How to store data

        :param store_flags:

            Dictionary containing how to store individual data, usually empty.

        :param overwrite:

            Instructions how to overwrite data

        :param with_links:

            Placeholder because leaves have no links

        :param recursive:

            Placeholder, because leaves have no children

        :param _hdf5_group:

            The hdf5 group for storing the parameter or result

        :param _newly_created:

            If should be created in a new form

        """
        if store_data == pypetconstants.STORE_NOTHING:
            return
        elif store_data == pypetconstants.STORE_DATA_SKIPPING and instance._stored:
            self._logger.debug('Already found `%s` on disk I will not store it!' %
                                   instance.v_full_name)
            return
        elif store_data == pypetconstants.OVERWRITE_DATA:
            if not overwrite:
                overwrite = True

        fullname = instance.v_full_name
        self._logger.debug('Storing %s.' % fullname)

        if _hdf5_group is None:
            # If no group is provided we might need to create one
            _hdf5_group, _newly_created = self._all_create_or_get_groups(fullname)

        # kwargs_flags = {} # Dictionary to change settings
        # old_kwargs = {}
        store_dict = {}
        # If the user did not supply storage flags, we need to set it to the empty dictionary
        if store_flags is None:
            store_flags = {}

        try:
            # Get the data to store from the instance
            if not instance.f_is_empty():
                store_dict = instance._store()

            try:
                # Ask the instance for storage flags
                instance_flags = instance._store_flags().copy() # copy to avoid modifying the
                # original data
            except AttributeError:
                # If it does not provide any, set it to the empty dictionary
                instance_flags = {}

            # User specified flags have priority over the flags from the instance
            instance_flags.update(store_flags)
            store_flags = instance_flags

            # If we still have data in `store_dict` about which we do not know how to store
            # it, pick default storage flags
            self._prm_extract_missing_flags(store_dict, store_flags)

            if overwrite:
                if isinstance(overwrite, compat.base_type):
                    overwrite = [overwrite]

                if overwrite is True:
                    to_delete = [key for key in store_dict.keys() if key in _hdf5_group]
                    self._all_delete_parameter_or_result_or_group(instance,
                                                                  delete_only=to_delete,
                                                                  _hdf5_group=_hdf5_group)
                elif isinstance(overwrite, (list, tuple)):
                    overwrite_set = set(overwrite)
                    key_set = set(store_dict.keys())

                    stuff_not_to_be_overwritten = overwrite_set - key_set

                    if overwrite!='v_annotations' and len(stuff_not_to_be_overwritten) > 0:
                        self._logger.warning('Cannot overwrite `%s`, these items are not supposed to '
                                             'be stored by the leaf node.' %
                                             str(stuff_not_to_be_overwritten))

                    stuff_to_overwrite = overwrite_set & key_set
                    if len(stuff_to_overwrite) > 0:
                        self._all_delete_parameter_or_result_or_group(instance,
                                                                      delete_only=list(
                                                                          stuff_to_overwrite))
                else:
                    raise ValueError('Your value of overwrite `%s` is not understood. '
                                     'Please pass `True` of a list of strings to fine grain '
                                     'overwriting.' % str(overwrite))

            for key, data_to_store in store_dict.items():
                # Iterate through the data and store according to the storage flags
                if key in _hdf5_group:
                    # We won't change any data that is found on disk
                    self._logger.debug(
                        'Found %s already in hdf5 node of %s, so I will ignore it.' %
                        (key, fullname))
                    continue
                flag = store_flags[key]
                if flag == HDF5StorageService.TABLE:
                    self._prm_write_into_pytable(key, data_to_store, _hdf5_group, fullname,
                                                 **kwargs)
                elif flag == HDF5StorageService.DICT:
                    self._prm_write_dict_as_table(key, data_to_store, _hdf5_group, fullname,
                                                  **kwargs)
                elif flag == HDF5StorageService.ARRAY:
                    self._prm_write_into_array(key, data_to_store, _hdf5_group, fullname,
                                               **kwargs)
                elif flag in (HDF5StorageService.CARRAY,
                              HDF5StorageService.EARRAY,
                              HDF5StorageService.VLARRAY):
                    self._prm_write_into_other_array(key, data_to_store,
                                                     _hdf5_group, fullname,
                                                     flag=flag, **kwargs)
                elif flag in (HDF5StorageService.SERIES,
                              HDF5StorageService.FRAME,
                              HDF5StorageService.PANEL):
                    self._prm_write_pandas_data(key, data_to_store, _hdf5_group, fullname,
                                                flag, **kwargs)
                else:
                    raise RuntimeError('You shall not pass!')

            # Store annotations
            self._ann_store_annotations(instance, _hdf5_group, overwrite=overwrite)

            if _newly_created or overwrite is True:
                # If we created a new group or the parameter was extended we need to
                # update the meta information and summary tables
                self._prm_add_meta_info(instance, _hdf5_group, overwrite=overwrite is True)

            instance._stored = True

        except:
            # I anything fails, we want to remove the data of the parameter again
            self._logger.error(
                'Failed storing leaf `%s`. I will remove the hdf5 data I added  again.' % fullname)
            # Delete data
            for key in store_dict.keys():
                if key in  _hdf5_group:
                    hdf5_child = ptcompat.get_child(_hdf5_group, key)
                    hdf5_child._f_remove(recursive=True)
            # If no data left delete the whole parameter
            if _hdf5_group._v_nchildren == 0:
                _hdf5_group._f_remove(recursive=True)
            raise

    def _prm_write_shared_data(self, key, hdf5_group, full_name, **kwargs):
        try:

            if 'obj' in kwargs:
                data = kwargs.pop('obj')
            elif 'object' in kwargs:
                data = kwargs.pop('object')
            elif 'data' in kwargs:
                data = kwargs.pop('data')
            else:
                data = None

            flag = kwargs.pop('flag', None)

            if flag is None and data is None:
                raise RuntimeError('You must provide at least data or a flag')

            if flag is None:
                flags_dict={}
                self._prm_extract_missing_flags({key: data}, flags_dict)
                flag = flags_dict[key]

            if flag == HDF5StorageService.TABLE:
                self._prm_write_shared_table(key, hdf5_group,
                                           full_name, **kwargs)
            elif flag in (HDF5StorageService.FRAME,
                          HDF5StorageService.SERIES,
                          HDF5StorageService.PANEL) :

                self._prm_write_pandas_data(key, data, hdf5_group, full_name, flag, **kwargs)
            else:
                self._prm_write_shared_array(key, data, hdf5_group,
                                           full_name, flag, **kwargs)

            hdf5data = ptcompat.get_child(hdf5_group, key)
            setattr(hdf5data._v_attrs, HDF5StorageService.STORAGE_TYPE,
                HDF5StorageService.SHARED_DATA)
            setattr(hdf5data._v_attrs, HDF5StorageService.SHARED_DATA_TYPE, flag)
        except:
            self._logger.error('Failed storing shared data `%s` of `%s`.' % (key, full_name))
            raise

    def _prm_select_shared_pandas_data(self, pd_node, full_name, **kwargs):
        """Reads a DataFrame from dis.

        :param pd_node:

            hdf5 node storing the pandas DataFrame

        :param full_name:

            Full name of the parameter or result whose data is to be loaded

        :param kwargs:

            Arguments passed to pandas' select method

        """
        try:
            pathname = pd_node._v_pathname
            pandas_store = self._hdf5store
            return pandas_store.select(pathname, **kwargs)
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (pd_node._v_name, full_name))
            raise

    def _prm_write_shared_array(self, key, data, hdf5_group, full_name, flag, **kwargs):
        """Creates and array that can be used with an HDF5 array object"""

        if flag == HDF5StorageService.ARRAY:
            self._prm_write_into_array(key, data, hdf5_group, full_name, **kwargs)
        elif flag in (HDF5StorageService.CARRAY,
                    HDF5StorageService.EARRAY,
                    HDF5StorageService.VLARRAY):
            self._prm_write_into_other_array(key, data, hdf5_group, full_name,
                                             flag=flag, **kwargs)
        else:
            raise RuntimeError('Flag `%s` of hdf5 data `%s` of `%s` not understood' %
                               (flag, key, full_name))

        self._hdf5file.flush()

    def _prm_write_shared_table(self, key, hdf5_group, fullname, **kwargs):
        """Creates a new empty table"""
        first_row = None
        description = None
        if 'first_row' in kwargs:
            first_row = kwargs.pop('first_row')
            if not 'description' in kwargs:
                description = {}
                for colname in first_row:
                    data = first_row[colname]
                    column = self._prm_get_table_col(key, [data], fullname)
                    description[colname] = column

        if 'description' in kwargs:
            description = kwargs.pop('description')

        if 'filters' in kwargs:
            filters = kwargs.pop('filters')
        else:
            filters = self._all_get_filters(kwargs)

        table = ptcompat.create_table(self._hdf5file,
                                          where=hdf5_group, name=key,
                                          description=description,
                                          filters=filters,
                                          **kwargs)
        table.flush()

        if first_row is not None:
            row = table.row
            for key in description:
                row[key] = first_row[key]

            row.append()
            table.flush()

    def _prm_write_dict_as_table(self, key, data_to_store, group, fullname, **kwargs):
        """Stores a python dictionary as pytable

        :param key:

            Name of data item to store

        :param data_to_store:

            Dictionary to store

        :param group:

            Group node where to store data in hdf5 file

        :param fullname:

            Full name of the `data_to_store`s original container, only needed for throwing errors.

        """
        if key in group:
            raise ValueError(
                'Dictionary `%s` already exists in `%s`. Appending is not supported (yet).')

        if key in group:
            raise ValueError('Dict `%s` already exists in `%s`. Appending is not supported (yet).')

        temp_dict = {}
        for innerkey in data_to_store:
            val = data_to_store[innerkey]
            temp_dict[innerkey] = [val]

        # Convert dictionary to object table
        objtable = ObjectTable(data=temp_dict)

        # Then store the object table
        self._prm_write_into_pytable(key, objtable, group, fullname, **kwargs)

        new_table = ptcompat.get_child(group, key)

        # Remember that the Object Table represents a dictionary
        self._all_set_attributes_to_recall_natives(temp_dict, new_table,
                                                   HDF5StorageService.DATA_PREFIX)

        setattr(new_table._v_attrs, HDF5StorageService.STORAGE_TYPE,
                HDF5StorageService.DICT)

        self._hdf5file.flush()

    def _prm_write_pandas_data(self, key, data, group, fullname, flag, **kwargs):
        """Stores a pandas DataFrame into hdf5.

        :param key:

            Name of data item to store

        :param data:

            Pandas Data to Store

        :param group:

            Group node where to store data in hdf5 file

        :param fullname:

            Full name of the `data_to_store`s original container, only needed for throwing errors.

        :param flag:

            If it is a series, frame or panel

        """
        try:
            if 'filters' not in kwargs:
                filters = self._all_get_filters(kwargs)
                kwargs['filters'] = filters
            if 'format' not in kwargs:
                kwargs['format'] = self.pandas_format
            if 'encoding' not in kwargs:
                kwargs['encoding'] = self.encoding

            overwrite = kwargs.pop('overwrite', False)

            if key in group and not (overwrite or kwargs.get('append', False)):
                raise ValueError(
                    'DataFrame `%s` already exists in `%s`. '
                    'To append pass ``append=`True```.' % (key, fullname))
            else:
                self._logger.debug('Appending to pandas data `%s` in `%s`' % (key, fullname))

            if data is not None and (kwargs['format'] == 'f' or kwargs['format'] == 'fixed'):
                kwargs['expectedrows'] = data.shape[0]

            name = group._v_pathname + '/' + key
            self._hdf5store.put(name, data, **kwargs)
            self._hdf5store.flush()
            self._hdf5file.flush()

            frame_group = ptcompat.get_child(group, key)
            setattr(frame_group._v_attrs, HDF5StorageService.STORAGE_TYPE, flag)
            self._hdf5file.flush()

        except:
            self._logger.error('Failed storing pandas data `%s` of `%s`.' % (key, fullname))
            raise

    def _prm_write_into_other_array(self, key, data, group, fullname,
                                    flag, **kwargs):
        """Stores data as carray, earray or vlarray depending on `flag`.

        :param key:

            Name of data item to store

        :param data:

            Data to store

        :param group:

            Group node where to store data in hdf5 file

        :param fullname:

            Full name of the `data_to_store`s original container, only needed for throwing errors.

        :param recall:

            If container type and data type for perfect recall should be stored

        :param flag:

            How to store:
                CARRAY, EARRAY, VLARRAY

        """
        try:

            if flag == HDF5StorageService.CARRAY:
                factory = ptcompat.create_carray
            elif flag == HDF5StorageService.EARRAY:
                factory = ptcompat.create_earray
            elif flag == HDF5StorageService.VLARRAY:
                factory = ptcompat.create_vlarray
            else:
                raise RuntimeError('You shall not pass!')

            if key in group:
                raise ValueError(
                    'CArray `%s` already exists in `%s`. Appending is not supported (yet).')

            if 'filters' in kwargs:
                filters = kwargs.pop('filters')
            else:
                filters = self._all_get_filters(kwargs)

            try:
                other_array = factory(self._hdf5file, where=group, name=key, obj=data,
                                                filters=filters, **kwargs)
            except (ValueError, TypeError):
                conv_data = data[:]
                conv_data = np.core.defchararray.encode(conv_data, self.encoding)
                other_array = factory(self._hdf5file, where=group, name=key,
                                                obj=conv_data,
                                                filters=filters, **kwargs)


            if data is not None:
                # Remember the types of the original data to recall them on loading
                self._all_set_attributes_to_recall_natives(data, other_array,
                                                       HDF5StorageService.DATA_PREFIX)
            setattr(other_array._v_attrs, HDF5StorageService.STORAGE_TYPE, flag)
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing %s `%s` of `%s`.' % (flag, key, fullname))
            raise

    def _prm_write_into_array(self, key, data, group, fullname, **kwargs):
        """Stores data as array.

        :param key:

            Name of data item to store

        :param data:

            Data to store

        :param group:

            Group node where to store data in hdf5 file

        :param fullname:

            Full name of the `data_to_store`s original container, only needed for throwing errors.

        :param recall:

            If container type and data type for perfect recall should be stored

        """

        try:
            if key in group:
                raise ValueError(
                    'Array `%s` already exists in `%s`. Appending is not supported (yet).')

            try:

                array = ptcompat.create_array(self._hdf5file, where=group,
                                              name=key, obj=data, **kwargs)
            except (TypeError, ValueError):
                if isinstance(data, compat.unicode_type):
                    conv_data = data.encode(self._encoding)
                else:
                    conv_data = []
                    for string in data:
                        conv_data.append(string.encode(self._encoding))
                array = ptcompat.create_array(self._hdf5file, where=group,
                                              name=key, obj=conv_data, **kwargs)

            if data is not None:
                # Remember the types of the original data to recall them on loading
                self._all_set_attributes_to_recall_natives(data, array,
                                                           HDF5StorageService.DATA_PREFIX)
            setattr(array._v_attrs, HDF5StorageService.STORAGE_TYPE,
                    HDF5StorageService.ARRAY)
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing array `%s` of `%s`.' % (key, fullname))
            raise

    def _lnk_delete_link(self, link_name):
        """Removes a link from disk"""
        translated_name = '/' + self._trajectory_name + '/' + link_name.replace('.','/')
        link = ptcompat.get_node(self._hdf5file, where=translated_name)
        link._f_remove()

    def _all_delete_parameter_or_result_or_group(self, instance,
                                                 delete_only=None,
                                                 remove_from_item=False,
                                                 recursive=False,
                                                 _hdf5_group=None):
        """Removes a parameter or result or group from the hdf5 file.

        :param instance: Instance to be removed

        :param delete_only:

            List of elements if you only want to delete parts of a leaf node. Note that this
            needs to list the names of the hdf5 subnodes. BE CAREFUL if you erase parts of a leaf.
            Erasing partly happens at your own risk, it might be the case that you can
            no longer reconstruct the leaf from the leftovers!

        :param remove_from_item:

            If using `delete_only` and `remove_from_item=True` after deletion the data item is
            also removed from the `instance`.

        :param recursive:

            If a group node has children, you will can delete it if recursive is True.


        """
        split_name = instance.v_location.split('.')
        if _hdf5_group is None:
            where = '/' + self._trajectory_name + '/' + '/'.join(split_name)
            node_name = instance.v_name
            _hdf5_group = ptcompat.get_node(self._hdf5file, where=where, name=node_name)

        if delete_only is None:
            if instance.v_is_leaf:
                # If we delete a leaf we need to take care about overview tables
                base_group = split_name[0]

                table_name = self._all_get_table_name(base_group, instance.v_run_branch)

                if table_name in self._overview_group:
                    table = getattr(self._overview_group, table_name)

                    self._all_store_param_or_result_table_entry(
                        instance,
                        table,
                        flags=(HDF5StorageService.REMOVE_ROW,))

                if instance.v_is_parameter:
                    table_name = 'explored_parameters'
                    if table_name in self._overview_group:
                        table = getattr(self._overview_group, table_name)

                        self._all_store_param_or_result_table_entry(
                            instance,
                            table,
                            flags=(HDF5StorageService.REMOVE_ROW,))

                self._prm_meta_remove_summary(instance)

                _hdf5_group._f_remove(recursive=True)
            else:
                if not recursive and len(_hdf5_group._v_groups) != 0:
                    raise TypeError('You cannot remove the group `%s`, it has children, please '
                                    'use `recursive=True` to enforce removal.' %
                                    instance.v_full_name)
                trajectory = instance.v_root
                leaf_deletion_list = []
                for hdf5_sub_group in ptcompat.walk_groups(_hdf5_group):
                    # We have to manually remove all leaves to ensure deletion from the
                    # overview tables
                    if self._all_get_from_attrs(hdf5_sub_group, HDF5StorageService.LEAF):
                        leaf_deletion_list.append(hdf5_sub_group)

                for hdf5_sub_group in leaf_deletion_list:
                    # Delete every leaf one by one to ensure removal from overview tables
                    full_name = '.'.join(hdf5_sub_group._v_pathname.split('/')[2:])
                    mock_instance, range_length = self._tree_create_leaf(full_name, trajectory,
                                                             hdf5_sub_group)
                    if range_length:
                        # You cannot delete an explored parameter
                        raise TypeError('Your want to delete the explored parameter `%s`. '
                                           'Sorry, I cannot delete explored parameters, please '
                                           'create a new empty trajectory instead or load '
                                           'as new.' % full_name)
                    self._all_delete_parameter_or_result_or_group(mock_instance,
                                                                  delete_only=None,
                                                                  remove_from_item=False,
                                                                  recursive=False,
                                                                  _hdf5_group=hdf5_sub_group)
                _hdf5_group._f_remove(recursive=recursive)
        else:
            if not instance.v_is_leaf:
                raise ValueError('You can only choose `delete_only` mode for leafs.')

            if isinstance(delete_only, compat.base_type):
                delete_only = [delete_only]

            for delete_item in delete_only:
                if (remove_from_item and
                        hasattr(instance, '__contains__') and
                        hasattr(instance, '__delattr__') and
                            delete_item in instance):
                    delattr(instance, delete_item)
                try:
                    _hdf5_sub_group = ptcompat.get_node(self._hdf5file,
                                                        where=_hdf5_group,
                                                        name=delete_item)
                    _hdf5_sub_group._f_remove(recursive=True)
                except pt.NoSuchNodeError:
                    self._logger.warning('Could not delete `%s` from `%s`. HDF5 node not found!' %
                                         (delete_item, instance.v_full_name))

    def _prm_write_into_pytable(self, tablename, data, hdf5_group, fullname, **kwargs):
        """Stores data as pytable.

        :param tablename:

            Name of the data table

        :param data:

            Data to store

        :param hdf5_group:

            Group node where to store data in hdf5 file

        :param fullname:

            Full name of the `data_to_store`s original container, only needed for throwing errors.

        """

        datasize = data.shape[0]

        try:

            # Get a new pytables description from the data and create a new table
            description_dict, data_type_dict = self._prm_make_description(data, fullname)
            description_dicts = [{}]

            if len(description_dict) > pypetconstants.HDF5_MAX_OBJECT_TABLE_TYPE_ATTRS:
                # For optimzation we want to store the original data types into another table
                new_table_group = ptcompat.create_group(self._hdf5file, where=hdf5_group,
                                                    name=tablename,
                                                    filters=self._all_get_filters(kwargs.copy()))

                if len(description_dict) > ptpa.MAX_COLUMNS:
                    # For further optimization we need to split the table into several
                    count = 0
                    for innerkey in description_dict:
                        val = description_dict[innerkey]
                        if count == ptpa.MAX_COLUMNS:
                            description_dicts.append({})
                            count = 0
                        description_dicts[-1][innerkey] = val
                        count += 1
                else:
                    description_dicts = [description_dict]

                setattr(new_table_group._v_attrs, HDF5StorageService.STORAGE_TYPE,
                        HDF5StorageService.TABLE)
                setattr(new_table_group._v_attrs, HDF5StorageService.SPLIT_TABLE, 1)

                hdf5_group = new_table_group
            else:
                description_dicts = [description_dict]

            for idx, descr_dict in enumerate(description_dicts):

                if idx == 0:
                    tblname = tablename
                else:
                    tblname = tablename + '_%d' % idx

                table = ptcompat.create_table(self._hdf5file,
                                              where=hdf5_group, name=tblname,
                                              description=descr_dict,
                                              title=tblname,
                                              expectedrows=datasize,
                                              filters=self._all_get_filters(kwargs.copy()))

                row = table.row
                for n in range(datasize):
                    # Fill the columns with data, note if the parameter was extended nstart!=0

                    for key in descr_dict:
                        row[key] = data[key][n]

                    row.append()

                # Remember the original types of the data for perfect recall
                if idx == 0 and len(
                        description_dict) <= pypetconstants.HDF5_MAX_OBJECT_TABLE_TYPE_ATTRS:
                    # We only have a single table and
                    # we can store the original data types as attributes
                    for field_name in data_type_dict:
                        type_description = data_type_dict[field_name]
                        ptcompat.set_attribute(table, field_name, type_description)

                    setattr(table._v_attrs, HDF5StorageService.STORAGE_TYPE,
                            HDF5StorageService.TABLE)

                table.flush()
                self._hdf5file.flush()

            if len(description_dict) > pypetconstants.HDF5_MAX_OBJECT_TABLE_TYPE_ATTRS:
                # We have potentially many split tables and the data types are
                # stored into an additional table for performance reasons
                tblname = tablename + '__' + HDF5StorageService.STORAGE_TYPE
                field_names, data_types = list(zip(*data_type_dict.items()))
                data_type_table_dict = {'field_name': field_names, 'data_type': data_types}
                descr_dict, _ = self._prm_make_description(data_type_table_dict, fullname)

                table = ptcompat.create_table(self._hdf5file,
                                              where=hdf5_group, name=tblname,
                                              description=descr_dict,
                                              title=tblname,
                                              expectedrows=len(field_names),
                                              filters=self._all_get_filters(kwargs))

                row = table.row

                for n in range(len(field_names)):
                    # Fill the columns with data, note if the parameter was extended nstart!=0

                    for key in data_type_table_dict:
                        row[key] = data_type_table_dict[key][n]

                    row.append()

                setattr(table._v_attrs, HDF5StorageService.DATATYPE_TABLE, 1)

                table.flush()
                self._hdf5file.flush()

        except:
            self._logger.error('Failed storing table `%s` of `%s`.' % (tablename, fullname))
            raise

    def _prm_make_description(self, data, fullname):
        """ Returns a description dictionary for pytables table creation"""

        def _convert_lists_and_tuples(series_of_data):
            """Converts lists and tuples to numpy arrays"""
            if isinstance(series_of_data[0],
                          (list, tuple)):  # and not isinstance(series_of_data[0], np.ndarray):
                # If the first data item is a list, the rest must be as well, since
                # data has to be homogeneous
                for idx, item in enumerate(series_of_data):
                    series_of_data[idx] = np.array(item)


        descriptiondict = {}  # dictionary containing the description to build a pytables table
        original_data_type_dict = {}  # dictionary containing the original data types

        for key in data:
            val = data[key]


            # remember the original data types
            self._all_set_attributes_to_recall_natives(val[0], PTItemMock(original_data_type_dict),
                                                       HDF5StorageService.FORMATTED_COLUMN_PREFIX %
                                                       key)

            _convert_lists_and_tuples(val)

            # get a pytables column from the data
            col = self._prm_get_table_col(key, val, fullname)

            descriptiondict[key] = col

        return descriptiondict, original_data_type_dict

    def _prm_get_table_col(self, key, column, fullname):
        """ Creates a pytables column instance.

        The type of column depends on the type of `column[0]`.
        Note that data in `column` must be homogeneous!

        """
        val = column[0]

        try:

            # # We do not want to loose int_
            if type(val) is int:
                return pt.IntCol()

            if isinstance(val, (compat.unicode_type, compat.bytes_type)):
                itemsize = int(self._prm_get_longest_stringsize(column))
                return pt.StringCol(itemsize)

            if isinstance(val, np.ndarray):
                if (np.issubdtype(val.dtype, compat.unicode_type) or
                        np.issubdtype(val.dtype, compat.bytes_type)):
                    itemsize = int(self._prm_get_longest_stringsize(column))
                    return pt.StringCol(itemsize, shape=val.shape)
                else:
                    return pt.Col.from_dtype(np.dtype((val.dtype, val.shape)))
            else:
                return pt.Col.from_dtype(np.dtype(type(val)))
        except Exception:
            self._logger.error('Failure in storing `%s` of Parameter/Result `%s`.'
                               ' Its type was `%s`.' % (key, fullname, repr(type(val))))
            raise

    @staticmethod
    def _prm_get_longest_stringsize(string_list):
        """ Returns the longest string size for a string entry across data."""
        maxlength = 1

        for stringar in string_list:
            if isinstance(stringar, np.ndarray):
                if stringar.ndim > 0:
                    for string in stringar.ravel():
                        maxlength = max(len(string), maxlength)
                else:
                    maxlength = max(len(stringar.tolist()), maxlength)
            else:
                maxlength = max(len(stringar), maxlength)

        # Make the string Col longer than needed in order to allow later on slightly larger strings
        return int(maxlength * 1.5)

    def _prm_load_parameter_or_result(self, instance,
                                      load_data=pypetconstants.LOAD_DATA,
                                      load_only=None,
                                      load_except=None,
                                      load_flags=None,
                                      with_links=False,
                                      recursive=False,
                                      _hdf5_group=None,):
        """Loads a parameter or result from disk.

        :param instance:

            Empty parameter or result instance

        :param load_data:

            How to load stuff

        :param load_only:

            List of data keys if only parts of a result should be loaded

        :param load_except:

            List of data key that should NOT be loaded.

        :param load_flags:

            Dictionary to determine how something is loaded

        :param with_links:

            Placeholder, because leaves have no links

        :param recursive:

            Dummy variable, no-op because leaves have no children

        :param _hdf5_group:

            The corresponding hdf5 group of the instance

        """
        if load_data == pypetconstants.LOAD_NOTHING:
            return

        if _hdf5_group is None:
            _hdf5_group = self._all_get_node_by_name(instance.v_full_name)

        if load_data == pypetconstants.OVERWRITE_DATA:
            if instance.v_is_parameter and instance.v_locked:
                self._logger.warning('Parameter `%s` is locked, I will skip loading.' %
                                     instance.v_full_name)
                return
            instance.f_empty()
            instance.v_annotations.f_empty()
            instance.v_comment = ''

        self._all_load_skeleton(instance, _hdf5_group)
        instance._stored = True

        # If load only is just a name and not a list of names, turn it into a 1 element list
        if isinstance(load_only, compat.base_type):
            load_only = [load_only]
        if isinstance(load_except, compat.base_type):
            load_except = [load_except]

        if load_data == pypetconstants.LOAD_SKELETON:
            #We only load skeletong if asked for it
            return
        elif load_only is not None:
            if load_except is not None:
                raise ValueError('Please use either `load_only` or `load_except` and not '
                             'both at the same time.')
            elif instance.v_is_parameter and instance.v_locked:
                raise pex.ParameterLockedException('Parameter `%s` is locked, '
                                                   'I will skip loading.' %
                                                    instance.v_full_name)
            self._logger.debug('I am in load only mode, I will only load %s.' %
                               str(load_only))
            load_only = set(load_only)
        elif load_except is not None:
            if instance.v_is_parameter and instance.v_locked:
                raise pex.ParameterLockedException('Parameter `%s` is locked, '
                                                   'I will skip loading.' %
                                                    instance.v_full_name)
            self._logger.debug('I am in load except mode, I will load everything except %s.' %
                               str(load_except))
            # We do not want to modify the original list
            load_except = set(load_except)
        elif not instance.f_is_empty():
            # We only load data if the instance is empty or we specified load_only or
            # load_except
            return

        full_name = instance.v_full_name
        self._logger.debug('Loading data of %s' % full_name)

        load_dict = {}  # Dict that will be used to keep all data for loading the parameter or
        # result

        if load_flags is None:
            load_flags = {}
        try:
            # Ask the instance for load flags
            instance_flags = instance._load_flags().copy() # copy to avoid modifying the
            # original data
        except AttributeError:
            # If it does not provide any, set it to the empty dictionary
            instance_flags = {}
        # User specified flags have priority over the flags from the instance
        instance_flags.update(load_flags)
        load_flags = instance_flags

        for node in _hdf5_group:

            if load_only is not None:

                if node._v_name not in load_only:
                    continue
                else:
                    load_only.remove(node._v_name)

            elif load_except is not None:
                if node._v_name in load_except:
                    load_except.remove(node._v_name)
                    continue

            # Recall from the hdf5 node attributes how the data was stored and reload accordingly
            if node._v_name in load_flags:
                load_type = load_flags[node._v_name]
            else:
                load_type = self._all_get_from_attrs(node, HDF5StorageService.STORAGE_TYPE)

            if load_type == HDF5StorageService.DICT:
                self._prm_read_dictionary(node, load_dict, full_name)
            elif load_type == HDF5StorageService.TABLE:
                self._prm_read_table(node, load_dict, full_name)
            elif load_type in (HDF5StorageService.ARRAY, HDF5StorageService.CARRAY,
                                HDF5StorageService.EARRAY, HDF5StorageService.VLARRAY):
                self._prm_read_array(node, load_dict, full_name)
            elif load_type in (HDF5StorageService.FRAME,
                               HDF5StorageService.SERIES,
                               HDF5StorageService.PANEL):
                self._prm_read_pandas(node, load_dict, full_name)
            elif load_type.startswith(HDF5StorageService.SHARED_DATA):
                pass # Shared data does not need to be loaded, it remains on disk.
            else:
                raise pex.NoSuchServiceError('Cannot load %s, do not understand the hdf5 file '
                                             'structure of %s [%s].' %
                                             (full_name, str(node), str(load_type)))

        if load_only is not None:
            # Check if all data in `load_only` was actually found in the hdf5 file
            if len(load_only) > 0:
                self._logger.warning('You marked %s for load only, '
                                     'but I cannot find these for `%s`' %
                                     (str(load_only), full_name))
        elif load_except is not None:
            if len(load_except) > 0:
                self._logger.warning(('You marked `%s` for not loading, but these were not part '
                                      'of `%s` anyway.' % (str(load_except), full_name)))

        # Finally tell the parameter or result to load the data, if there was any ;-)
        if load_dict:
            try:
                instance._load(load_dict)
                if instance.v_is_parameter:
                    # Lock parameter as soon as data is loaded
                    instance.f_lock()
            except:
                self._logger.error(
                    'Error while reconstructing data of leaf `%s`.' % full_name)
                raise

    def _prm_read_dictionary(self, leaf, load_dict, full_name):
        """Loads data that was originally a dictionary when stored

        :param leaf:

            PyTables table containing the dictionary data

        :param load_dict:

            Dictionary to keep the loaded data in

        :param full_name:

            Full name of the parameter or result whose data is to be loaded

        """
        try:
            # if self._all_get_from_attrs(leaf, HDF5StorageService.DICT_SPLIT):
            # temp_dict = {}
            # children = leaf._v_children
            # for tablename in children:
            # table = children[tablename]
            # self._prm_read_dictionary(table, temp_dict, full_name)
            # key =leaf._v_name
            # load_dict[key]={}
            # for dictname in temp_dict:
            # dictionary = temp_dict[dictname]
            # load_dict[key].update(dictionary)
            # else:
            temp_dict = {}
            # Load as Pbject Table
            self._prm_read_table(leaf, temp_dict, full_name)
            key = leaf._v_name
            temp_table = temp_dict[key]
            # Turn the ObjectTable into a dictionary of lists (with length 1).
            temp_dict = temp_table.to_dict('list')

            innder_dict = {}
            load_dict[key] = innder_dict

            # Turn the dictionary of lists into a normal dictionary
            for innerkey, vallist in temp_dict.items():
                innder_dict[innerkey] = vallist[0]
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (leaf._v_name, full_name))
            raise


    def _prm_read_pandas(self, pd_node, load_dict, full_name):
        """Reads a DataFrame from dis.

        :param pd_node:

            hdf5 node stroing the pandas DataFrame

        :param load_dict:

            Dictionary to keep the loaded data in

        :param full_name:

            Full name of the parameter or result whose data is to be loaded

        """
        try:
            name = pd_node._v_name
            pathname = pd_node._v_pathname
            pandas_store = self._hdf5store
            pandas_data = pandas_store.get(pathname)
            load_dict[name] = pandas_data
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (pd_node._v_name, full_name))
            raise

    def _prm_read_table(self, table_or_group, load_dict, full_name):
        """Reads a non-nested PyTables table column by column and created a new ObjectTable for
        the loaded data.

        :param table_or_group:

            PyTables table to read from or a group containing subtables.

        :param load_dict:

            Dictionary where the loaded ObjectTable will be kept

        :param full_name:

            Full name of the parameter or result whose data is to be loaded

        """
        try:
            if self._all_get_from_attrs(table_or_group, HDF5StorageService.SPLIT_TABLE):
                table_name = table_or_group._v_name

                data_type_table_name = table_name + '__' + HDF5StorageService.STORAGE_TYPE

                data_type_table = table_or_group._v_children[data_type_table_name]
                data_type_dict = {}
                for row in data_type_table:
                    fieldname = str(row['field_name'])
                    data_type_dict[fieldname] = str(row['data_type'])

                for sub_table in table_or_group:
                    sub_table_name = sub_table._v_name

                    if sub_table_name == data_type_table_name:
                        continue

                    for colname in sub_table.colnames:
                        # Read Data column by column
                        col = sub_table.col(colname)
                        data_list = list(col)

                        prefix = HDF5StorageService.FORMATTED_COLUMN_PREFIX % colname
                        for idx, data in enumerate(data_list):
                            # Recall original type of data
                            data, type_changed = self._all_recall_native_type(data,
                                                                              PTItemMock(
                                                                                  data_type_dict),
                                                                              prefix)
                            if type_changed:
                                data_list[idx] = data
                            else:
                                break

                        # Construct or insert into an ObjectTable
                        if table_name in load_dict:
                            load_dict[table_name][colname] = data_list
                        else:
                            load_dict[table_name] = ObjectTable(data={colname: data_list})

            else:

                table_name = table_or_group._v_name

                for colname in table_or_group.colnames:
                    # Read Data column by column
                    col = table_or_group.col(colname)
                    data_list = list(col)

                    prefix = HDF5StorageService.FORMATTED_COLUMN_PREFIX % colname
                    for idx, data in enumerate(data_list):
                        # Recall original type of data
                        data, type_changed = self._all_recall_native_type(data, table_or_group,
                                                                          prefix)
                        if type_changed:
                            data_list[idx] = data
                        else:
                            break

                    # Construct or insert into an ObjectTable
                    if table_name in load_dict:
                        load_dict[table_name][colname] = data_list
                    else:
                        load_dict[table_name] = ObjectTable(data={colname: data_list})
        except:
            self._logger.error(
                'Failed loading `%s` of `%s`.' % (table_or_group._v_name, full_name))
            raise


    def _prm_read_array(self, array, load_dict, full_name):
        """Reads data from an array or carray

        :param array:

            PyTables array or carray to read from

        :param load_dict:

            Dictionary where the loaded ObjectTable will be kept

        :param full_name:

            Full name of the parameter or result whose data is to be loaded
        """
        try:
            result = array.read()
            # Recall original data types
            result, dummy = self._all_recall_native_type(result, array,
                                                         HDF5StorageService.DATA_PREFIX)

            load_dict[array._v_name] = result
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (array._v_name, full_name))
            raise

    def _hdf5_interact_with_data(self, path_to_data, item_name, request, args, kwargs):

        hdf5_group = self._all_get_node_by_name(path_to_data)

        if request == 'create_shared_data' or request == 'pandas_put':
            return self._prm_write_shared_data(key=item_name, hdf5_group=hdf5_group,
                                        full_name=path_to_data, **kwargs)

        hdf5data = ptcompat.get_child(hdf5_group, item_name)

        if request == '__thenode__':
            return hdf5data
        elif request == 'pandas_get':
            data_dict = {}
            self._prm_read_pandas(hdf5data, data_dict, path_to_data)
            return data_dict[item_name]
        elif request == 'pandas_select':
            return self._prm_select_shared_pandas_data(hdf5data, path_to_data, **kwargs)
        elif request == 'make_ordinary':
            new_class_name = kwargs.pop('new_class_name')
            new_data_name = kwargs.pop('new_data_name', None)
            if new_data_name is None:
                new_data_name = item_name
            flag = getattr(hdf5data._v_attrs, HDF5StorageService.SHARED_DATA_TYPE)
            delattr(hdf5data._v_attrs, HDF5StorageService.SHARED_DATA_TYPE)
            setattr(hdf5data._v_attrs, HDF5StorageService.STORAGE_TYPE, flag)
            hdf5data._f_rename(new_data_name)
            setattr(hdf5_group._v_attrs, HDF5StorageService.CLASS_NAME, new_class_name)
            return
        elif request == 'make_shared':
            if hdf5_group._v_nchildren != 1:
                raise RuntimeError('Cannot convert to shared result, the hdf5_group `%s` '
                                   'has more than one child.' % hdf5_group._v_name)
            new_class_name = kwargs.pop('new_class_name')
            new_data_name = kwargs.pop('new_data_name', None)
            if new_data_name is None:
                new_data_name = item_name
            flag = getattr(hdf5data._v_attrs, HDF5StorageService.STORAGE_TYPE)
            setattr(hdf5data._v_attrs, HDF5StorageService.SHARED_DATA_TYPE, flag)
            setattr(hdf5data._v_attrs, HDF5StorageService.STORAGE_TYPE,
                    HDF5StorageService.SHARED_DATA)
            hdf5data._f_rename(new_data_name)
            setattr(hdf5_group._v_attrs, HDF5StorageService.CLASS_NAME, new_class_name)
            return

        if kwargs and kwargs.pop('_col_func', False):
            colname = kwargs.pop('colname', None)
            if colname is None:
                colname = args[0]
            name_list = colname.split('/')
            curr = hdf5data.cols
            for name in name_list:
                curr = getattr(curr, name)
            hdf5data = curr

        what = getattr(hdf5data, request)
        if args is None and kwargs is None:
            return what
        else:
            if args is None:
                args=()
            if kwargs is None:
                kwargs = {}
            result = what(*args, **kwargs)
            return result
