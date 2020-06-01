""" Module containing the storage services.

Contains the standard :class:`~pypet.storageservice.HDF5StorageSerivce`.

"""

__author__ = 'Robert Meyer'

import os
import warnings
import time
import hashlib
import itertools as itools

import tables as pt
tables_version = int(pt.__version__[0])
if tables_version < 3:
    raise ImportError('Please use PyTables 3 or newer, older versions are not supported!')
import tables.parameters as ptpa

import numpy as np
from pandas import DataFrame, Series, HDFStore

import pypet.pypetconstants as pypetconstants
import pypet.pypetexceptions as pex
from pypet._version import __version__ as VERSION
from pypet.parameter import ObjectTable, Parameter
import pypet.naturalnaming as nn
from pypet.pypetlogging import HasLogger, DisableAllLogging
from pypet.utils.decorators import deprecated
import pypet.shareddata as shared
from pypet.utils.helpful_functions import racedirs


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
    def __init__(self, *args, **kwargs):
        """Swallows all arguments for easier debugging"""
        pass

    def load(self, *args, **kwargs):
        """Nope, I won't care, dude!"""
        pass

    def store(self, *args, **kwargs):
        """Do whatever you want, I won't store anything!"""
        pass


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


class DictWrap(object):
    """Wraps dictionary to allow get and setattr access"""
    def __init__(self, dictionary):
        self.__dict__ = dictionary


class PTItemMock(object):
    """Class that mocks a PyTables item and wraps around a dictionary"""
    def __init__(self, dictionary):
        self._v_attrs = DictWrap(dictionary)


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
    COLL_EMPTY_DICT = 'COLL_EMPTY_DICT'
    ''' Container was an empty dictionary'''
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
        '_overview_config': 'config_overview',
        '_overview_parameters': 'parameters_overview',
        '_overview_derived_parameters': 'derived_parameters_overview',
        '_overview_results': 'results_overview',
        '_overview_explored_parameters': 'explored_parameters_overview',
        '_overview_derived_parameters_summary': 'derived_parameters_summary',
        '_overview_results_summary': 'results_summary'
    }
    ''' Mapping of trajectory config names to the tables'''

    PR_ATTR_NAME_MAPPING = {
        '_derived_parameters_per_run': 'derived_parameters_per_run',
        '_results_per_run': 'results_per_run',
        '_purge_duplicate_comments': 'purge_duplicate_comments'
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

    SPLIT_TABLE = pypetconstants.SPLIT_TABLE
    ''' If a table was split due to too many columns'''

    DATATYPE_TABLE = pypetconstants.DATATYPE_TABLE
    '''If a table contains the data types instead of the attrs'''

    SHARED_DATA = pypetconstants.SHARED_DATA
    ''' An HDF5 data object for direct interaction '''

    NESTED_GROUP = pypetconstants.NESTED_GROUP
    ''' An HDF5 data object containing nested data '''

    TYPE_FLAG_MAPPING = {
        ObjectTable: TABLE,
        list: ARRAY,
        tuple: ARRAY,
        dict: DICT,
        np.ndarray: CARRAY,
        np.matrix: CARRAY,
        DataFrame: FRAME,
        Series: SERIES,
        shared.SharedTable: SHARED_DATA,
        shared.SharedArray: SHARED_DATA,
        shared.SharedPandasFrame: SHARED_DATA,
        shared.SharedCArray: SHARED_DATA,
        shared.SharedEArray: SHARED_DATA,
        shared.SharedVLArray: SHARED_DATA,
    }
    ''' Mapping from object type to storage flag'''

    # Python native data should always be stored as an ARRAY
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
    ''' Length of a parameter if it is explored, no longer in use, only for backwards
    compatibility'''
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

        if os.path.isdir(filename):
            head, tail = (filename, '')
        else:
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
        self._overview_derived_parameters = large_overview_tables
        self._overview_derived_parameters_summary = summary_tables
        self._overview_results = large_overview_tables
        self._overview_results_summary = summary_tables

        self._overview_group_ = None  # to cache link to overview

        self._disable_logger = DisableAllLogging()


        self._mode = None
        self._keep_open = False

        if trajectory is not None and not trajectory.v_stored:
            self._srvc_set_config(trajectory=trajectory)

        if overwrite_file:
            try:
                os.remove(filename)
                self._logger.info('You specified ``overwrite_file=True``, so I deleted the '
                                  'file `%s`.' % filename)
            except OSError:
                # File not found, we're good
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
        if self._overview_group_ is None:
            self._overview_group_ = self._all_create_or_get_groups('overview')[0]
        return self._overview_group_

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
            _set_config('hdf5.overview.' + table_name,
                         value,
                         comment='Whether or not to have an overview '
                                 'table with that name')

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

                :param max_depth:

                    Maximum depth in case of recursion. `None` for no limit.

            * :const:`pypet.pypetconstants.TREE` ('TREE')

                Loads a whole subtree

                :param stuff_to_load: The parent node (!) not the one where loading starts!

                :param child_name: Name of child node that should be loaded

                :param recursive: Whether to load recursively the subtree below child

                :param load_data:

                    How to load stuff, accepted values as above for loading the trajectory

                :param max_depth:

                    Maximum depth in case of recursion. `None` for no limit.

                :param trajectory: The trajectory object

            * :const:`pypet.pypetconstants.LIST` ('LIST')

                Analogous to :ref:`storing lists <store-lists>`

        :raises:

            NoSuchServiceError if message or data is not understood

            DataNotInStorageError if data to be loaded cannot be found on disk

        """
        opened = True
        try:

            opened = self._srvc_opening_routine('r', kwargs=kwargs)

            if msg == pypetconstants.TRAJECTORY:
                self._trj_load_trajectory(stuff_to_load, *args, **kwargs)

            elif msg == pypetconstants.LEAF:
                self._prm_load_parameter_or_result(stuff_to_load, *args, **kwargs)

            elif msg == pypetconstants.GROUP:
                self._grp_load_group(stuff_to_load, *args, **kwargs)

            elif msg == pypetconstants.TREE:
                self._tree_load_sub_branch(stuff_to_load, *args, **kwargs)

            elif msg == pypetconstants.LIST:
                self._srvc_load_several_items(stuff_to_load, *args, **kwargs)

            else:
                raise pex.NoSuchServiceError('I do not know how to handle `%s`' % msg)

        except pt.NoSuchNodeError as exc:
            self._logger.error('Failed loading  `%s`' % str(stuff_to_load))
            raise pex.DataNotInStorageError(repr(exc))
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

                :param old_length:

                    Old length of trajectory before merge

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

                :param max_depth:

                    Maximum depth in case of recursion. `None` for no limit.

            * :const:`pypet.pypetconstants.TREE`

                Stores a single node or a full subtree

                :param stuff_to_store: Node to store

                :param store_data: How to store data

                :param recursive: Whether to store recursively the whole sub-tree

                :param max_depth:

                    Maximum depth in case of recursion. `None` for no limit.

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

            opened = self._srvc_opening_routine('a', msg, kwargs)

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
                self._tree_store_sub_branch(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.DELETE_LINK:
                self._lnk_delete_link(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.LIST:
                self._srvc_store_several_items(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.ACCESS_DATA:
                return self._hdf5_interact_with_data(stuff_to_store, *args, **kwargs)

            elif msg == pypetconstants.OPEN_FILE:
                opened = False  # Wee need to keep the file open to allow later interaction
                self._keep_open = True
                self._node_processing_timer.active = False # This might be open quite long
                # so we don't want to display horribly long opening times

            elif msg == pypetconstants.CLOSE_FILE:
                opened = True  # Simply conduct the closing routine afterwards
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
                self._logger.debug('Could not find `%s` in traj config, '
                                     'using (default) value `%s`.' %
                                     (attr_name, str(getattr(self, attr_name))))

        for attr_name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():
            try:
                if table_name in ('parameters', 'config'):
                    table_name += '_overview'
                config = traj.f_get('config.hdf5.overview.' + table_name).f_get()
                setattr(self, attr_name, config)
            except AttributeError:
                self._logger.debug('Could not find `%s` in traj config, '
                                     'using (default) value `%s`.' %
                                     (table_name, str(getattr(self, attr_name))))

        for attr_name, name in HDF5StorageService.PR_ATTR_NAME_MAPPING.items():
            try:
                config = traj.f_get('config.hdf5.' + name).f_get()
                setattr(self, attr_name, config)
            except AttributeError:
                self._logger.debug('Could not find `%s` in traj config, '
                                     'using (default) value `%s`.' %
                                     (name, str(getattr(self, attr_name))))

        if ((not self._overview_results_summary or
                    not self._overview_derived_parameters_summary) and
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

    def _srvc_opening_routine(self, mode, msg=None, kwargs=()):
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

        :param kwargs:

            Arguments to extract file information from

        :return:

            `True` if file is opened

            `False` if the file was already open before calling this function

        """
        self._mode = mode
        self._srvc_extract_file_information(kwargs)

        if not self.is_open:

            if 'a' in mode:
                (path, filename) = os.path.split(self._filename)
                racedirs(os.path.abspath(path))

                self._hdf5store = HDFStore(self._filename, mode=self._mode, complib=self._complib,
                                           complevel=self._complevel, fletcher32=self._fletcher32)
                self._hdf5file = self._hdf5store._handle
                self._hdf5file.title = self._file_title

                if self._trajectory_name is not None:
                    if not '/' + self._trajectory_name in self._hdf5file:
                        # If we want to store individual items we we have to check if the
                        # trajectory has been stored before
                        if not msg == pypetconstants.TRAJECTORY:
                            raise ValueError('Your trajectory cannot be found in the hdf5file, '
                                             'please use >>traj.f_store()<< '
                                             'before storing anything else.')

                    else:
                        # Keep a reference to the top trajectory node
                        self._trajectory_group = self._hdf5file.get_node('/' +
                                                                         self._trajectory_name)
                else:
                    raise ValueError('I don`t know which trajectory to load')
                self._logger.debug('Opening HDF5 file `%s` in mode `a` with trajectory `%s`' %
                                   (self._filename, self._trajectory_name))

            elif mode == 'r':

                if self._trajectory_name is not None and self._trajectory_index is not None:
                    raise ValueError('Please specify either a name of a trajectory or an index, '
                                     'but not both at the same time.')

                if not os.path.isfile(self._filename):
                    raise ValueError('File `' + self._filename + '` does not exist.')

                self._hdf5store = HDFStore(self._filename, mode=self._mode, complib=self._complib,
                                           complevel=self._complevel, fletcher32=self._fletcher32)
                self._hdf5file = self._hdf5store._handle

                if self._trajectory_index is not None:
                    # If an index is provided pick the trajectory at the corresponding
                    # position in the trajectory node list
                    nodelist = self._hdf5file.list_nodes(where='/')

                    if (self._trajectory_index >= len(nodelist) or
                            self._trajectory_index < -len(nodelist)):
                        raise ValueError('Trajectory No. %d does not exists, there are only '
                                         '%d trajectories in %s.'
                                         % (self._trajectory_index, len(nodelist), self._filename))

                    self._trajectory_group = nodelist[self._trajectory_index]
                    self._trajectory_name = self._trajectory_group._v_name

                elif self._trajectory_name is not None:
                    # Otherwise pick the trajectory group by name
                    if not '/' + self._trajectory_name in self._hdf5file:
                        raise ValueError('File %s does not contain trajectory %s.'
                                         % (self._filename, self._trajectory_name))

                    self._trajectory_group = self._hdf5file.get_node('/' + self._trajectory_name)
                else:
                    raise ValueError('Please specify a name of a trajectory to load or its '
                                     'index, otherwise I cannot open one.')

                self._logger.debug('Opening HDF5 file `%s` in mode `r` with trajectory `%s`' %
                                   (self._filename, self._trajectory_name))

            else:
                raise RuntimeError('You shall not pass!')

            self._node_processing_timer = NodeProcessingTimer(display_time=self._display_time,
                                                              logger_name=self._logger.name)
            self._overview_group_ = None

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
            except OSError as exc:
                # This seems to be the only way to avoid an OSError under Windows
                errmsg = ('Encountered OSError while flushing file.'
                                   'If you are using Windows, don`t worry! '
                                   'I will ignore the error and try to close the file. '
                                   'Original error: %s' % repr(exc))
                self._logger.debug(errmsg)

            self._hdf5store.close()
            if self._hdf5file.isopen:
                self._logger.error('Could not close HDF5 file!')
            self._hdf5file = None
            self._hdf5store = None
            self._trajectory_group = None
            self._trajectory_name = None
            self._trajectory_index = None
            self._overview_group_ = None
            self._logger.debug('Closing HDF5 file')
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

        backup_hdf5file = pt.open_file(filename=backup_filename,
                                             mode='a', title=backup_filename)

        if '/' + self._trajectory_name in backup_hdf5file:
            raise ValueError('I cannot backup  `%s` into file `%s`, there is already a '
                             'trajectory with that name.' % (traj.v_name, backup_filename))

        backup_root = backup_hdf5file.root

        self._trajectory_group._f_copy(newparent=backup_root, recursive=True)

        backup_hdf5file.flush()
        backup_hdf5file.close()

        self._logger.info('Finished backup of %s.' % traj.v_name)

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


    def _trj_merge_trajectories(self, other_trajectory_name, rename_dict, move_nodes=False,
                                delete_trajectory=False, other_filename=None):
        """Merges another trajectory into the current trajectory (as in self._trajectory_name).

        :param other_trajectory_name: Name of other trajectory
        :param rename_dict: Dictionary with old names (keys) and new names (values).
        :param move_nodes: Whether to move hdf5 nodes or copy them
        :param delete_trajectory: Whether to delete the other trajectory

        """
        if other_filename is None or other_filename == self.filename:
            other_filename = self.filename
            other_file = self._hdf5file
            other_is_different = False
        else:
            other_file = pt.open_file(filename=other_filename, mode='r+')
            other_is_different = True

        try:
            if not '/' + other_trajectory_name in other_file:
                raise ValueError('Cannot merge `%s` and `%s`, because the second trajectory cannot '
                                 'be found in file: %s.' % (self._trajectory_name,
                                                            other_trajectory_name,
                                                            other_filename))
            for old_name in rename_dict:
                new_name = rename_dict[old_name]

                # Iterate over all items that need to be merged
                split_name = old_name.split('.')
                old_location = '/' + other_trajectory_name + '/' + '/'.join(split_name)

                split_name = new_name.split('.')
                new_parent_location = '/' + self._trajectory_name + '/' + '/'.join(split_name[:-1])

                new_short_name = split_name[-1]

                # Get the data from the other trajectory
                old_node = other_file.get_node(old_location)

                # Now move or copy the data
                if move_nodes:
                    self._hdf5file.move_node( where=old_node, newparent=new_parent_location,
                                       newname=new_short_name, createparents=True)
                else:
                    if other_is_different:
                        new_parent_dot_location = '.'.join(split_name[:-1])
                        new_parent_or_loc, _ = self._all_create_or_get_groups(
                            new_parent_dot_location)
                        create_parents = False
                    else:
                        new_parent_or_loc = new_parent_location
                        create_parents = True
                    self._hdf5file.copy_node(where=old_node, newparent=new_parent_or_loc,
                                       newname=new_short_name, createparents=create_parents,
                                       recursive=True)


            if delete_trajectory:
                other_file.remove_node(where='/', name=other_trajectory_name, recursive=True)
        finally:
            if other_is_different:
                other_file.flush()
                other_file.close()

    def _trj_prepare_merge(self, traj, changed_parameters, old_length):
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

            try:
                self._all_delete_parameter_or_result_or_group(param)
            except pt.NoSuchNodeError:
                pass  # We are fine and the node did not exist in the first place

        # Increase the run table by the number of new runs
        run_table = getattr(self._overview_group, 'runs')
        actual_rows = run_table.nrows
        self._trj_fill_run_table(traj, actual_rows, len(traj))

        # Extract parameter summary and if necessary create new explored parameter tables
        # in the result groups
        for idx in range(old_length, len(traj)):
            run_name = traj.f_idx_to_run(idx)
            run_info = traj.f_get_run_information(run_name)
            run_info['name'] = run_name

            traj._set_explored_parameters_to_idx(idx)

            run_summary = self._srn_summarize_explored_parameters(list(
                                                            traj._explored_parameters.values()))

            run_info['parameter_summary'] = run_summary

            self._all_add_or_modify_row(run_name, run_info, run_table, index=idx,
                                        flags=(HDF5StorageService.MODIFY_ROW,))

        traj.f_restore_default()


    ######################## Loading a Trajectory #################################################

    def _trj_load_trajectory(self, traj, as_new, load_parameters, load_derived_parameters,
                             load_results, load_other_data, recursive, max_depth,
                             with_run_information, with_meta_data, force):
        """Loads a single trajectory from a given file.


        :param traj: The trajectory

        :param as_new: Whether to load trajectory as new

        :param load_parameters: How to load parameters and config

        :param load_derived_parameters: How to load derived parameters

        :param load_results: How to load results

        :param load_other_data: How to load anything not within the four subbranches

        :param recursive: If data should be loaded recursively

        :param max_depth: Maximum depth of loading

        :param with_run_information:

            If run information should be loaded

        :param with_meta_data:

            If meta data infor should be loaded

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
        if (as_new and (load_derived_parameters != pypetconstants.LOAD_NOTHING or
                                load_results != pypetconstants.LOAD_NOTHING or
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
        if with_meta_data:
            self._trj_load_meta_data(traj, load_data, as_new, with_run_information, force)

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

                self._tree_load_sub_branch(traj, child_name, load_data=loading, with_links=True,
                                     recursive=recursive,
                                     max_depth=max_depth,
                                     _trajectory=traj, _as_new=as_new,
                                     _hdf5_group=self._trajectory_group)

    def _trj_load_meta_data(self, traj, load_data, as_new, with_run_information, force):
        """Loads meta information about the trajectory

        Checks if the version number does not differ from current pypet version
        Loads, comment, timestamp, name, version from disk in case trajectory is not loaded
        as new. Updates the run information as well.

        """

        metatable = self._overview_group.info
        metarow = metatable[0]

        try:
            version = metarow['version'].decode('utf-8')
        except (IndexError, ValueError) as ke:
            self._logger.error('Could not check version due to: %s' % str(ke))
            version = '`COULD NOT BE LOADED`'

        try:
            python = metarow['python'].decode('utf-8')
        except (IndexError, ValueError) as ke:
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
            traj._comment =  metarow['comment'].decode('utf-8')
            traj._timestamp = float(metarow['timestamp'])
            traj._trajectory_timestamp = traj._timestamp
            traj._time = metarow['time'].decode('utf-8')
            traj._trajectory_time = traj._time
            traj._name = metarow['name'].decode('utf-8')
            traj._trajectory_name = traj._name
            traj._version = version
            traj._python = python

            single_run_table = self._overview_group.runs

            if with_run_information:
                for row in single_run_table.iterrows():
                    name = row['name'].decode('utf-8')
                    idx = int(row['idx'])
                    timestamp = float(row['timestamp'])
                    time_ = row['time'].decode('utf-8')
                    completed = int(row['completed'])
                    summary = row['parameter_summary'].decode('utf-8')
                    hexsha = row['short_environment_hexsha'].decode('utf-8')


                    # To allow backwards compatibility we need this try catch block
                    try:
                        runtime = row['runtime'].decode('utf-8')
                        finish_timestamp = float(row['finish_timestamp'])
                    except (IndexError, ValueError) as ke:
                        runtime = ''
                        finish_timestamp = 0.0
                        self._logger.debug('Could not load runtime, ' + repr(ke))

                    info_dict = {'idx': idx,
                                 'timestamp': timestamp,
                                 'finish_timestamp': finish_timestamp,
                                 'runtime': runtime,
                                 'time': time_,
                                 'completed': completed,
                                 'name': name,
                                 'parameter_summary': summary,
                                 'short_environment_hexsha': hexsha}

                    traj._add_run_info(**info_dict)
            else:
                traj._length = single_run_table.nrows

        # Load explorations
        self._trj_load_exploration(traj)
        # Load the hdf5 config data:
        self._srvc_load_hdf5_settings()

    def _srvc_load_hdf5_settings(self):

        def _extract_meta_data(attr_name, row, name_in_row, conversion_function):
            try:
                setattr(self, attr_name, conversion_function(row[name_in_row]))
            except (IndexError, ValueError) as exc:
                self._logger.error('Using default hdf5 setting, '
                                   'could not extract `%s` hdf5 setting because of: %s' %
                                        (name_in_row, repr(exc)))

        if 'hdf5_settings' in self._overview_group:
            hdf5_table = self._overview_group.hdf5_settings
            hdf5_row = hdf5_table[0]

            tostr = lambda x: x.decode('utf-8')
            _extract_meta_data('complib', hdf5_row, 'complib', tostr)
            _extract_meta_data('complevel', hdf5_row, 'complevel', int)
            _extract_meta_data('shuffle', hdf5_row, 'shuffle', bool)
            _extract_meta_data('fletcher32', hdf5_row, 'fletcher32', bool)
            _extract_meta_data('pandas_format', hdf5_row, 'pandas_format', tostr)
            _extract_meta_data('encoding', hdf5_row, 'encoding', tostr)

            _extract_meta_data('_results_per_run', hdf5_row,
                               'results_per_run', int)
            _extract_meta_data('_derived_parameters_per_run', hdf5_row,
                               'derived_parameters_per_run', int)
            _extract_meta_data('_purge_duplicate_comments', hdf5_row,
                               'purge_duplicate_comments', bool)

            for attr_name, table_name in self.NAME_TABLE_MAPPING.items():
                _extract_meta_data(attr_name, hdf5_row, table_name, bool)
        else:
            self._logger.warning('Could not find `hdf5_settings` overview table. I will use the '
                                 'standard settings (for `complib`, `complevel` etc.) instead.')

    def _tree_load_sub_branch(self, traj_node, branch_name,
                              load_data=pypetconstants.LOAD_DATA,
                              with_links=True, recursive=False,
                              max_depth=None, _trajectory=None,
                              _as_new=False, _hdf5_group=None):
        """Loads data starting from a node along a branch and starts recursively loading
        all data at end of branch.

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

        :param max_depth:

            The maximum depth to load the tree

        :param _trajectory:

            The trajectory

        :param _as_new:

            If trajectory is loaded as new

        :param _hdf5_group:

            HDF5 node in the file corresponding to `traj_node`.

        """
        if load_data == pypetconstants.LOAD_NOTHING:
            return

        if max_depth is None:
            max_depth = float('inf')

        if _trajectory is None:
            _trajectory = traj_node.v_root

        if _hdf5_group is None:
            hdf5_group_name = traj_node.v_full_name.replace('.', '/')

            # Get child node to load
            if hdf5_group_name == '':
                _hdf5_group = self._trajectory_group
            else:
                try:
                    _hdf5_group = self._hdf5file.get_node(where=self._trajectory_group,
                                                  name=hdf5_group_name)
                except pt.NoSuchNodeError:
                    self._logger.error('Cannot find `%s` the hdf5 node `%s` does not exist!'
                                       % (traj_node.v_full_name, hdf5_group_name))
                    raise

        split_names = branch_name.split('.')

        final_group_name = split_names.pop()

        current_depth = 1

        for name in split_names:
            if current_depth > max_depth:
                return
            # First load along the branch
            _hdf5_group = getattr(_hdf5_group, name)

            self._tree_load_nodes_dfs(traj_node, load_data=load_data, with_links=with_links,
                                  recursive=False, max_depth=max_depth, current_depth=current_depth,
                                  trajectory=_trajectory, as_new=_as_new,
                                  hdf5_group=_hdf5_group)

            current_depth += 1

            traj_node = traj_node._children[name]

        if current_depth <= max_depth:
            # Then load recursively all data in the last group and below
            _hdf5_group = getattr(_hdf5_group, final_group_name)
            self._tree_load_nodes_dfs(traj_node, load_data=load_data, with_links=with_links,
                                  recursive=recursive, max_depth=max_depth,
                                  current_depth=current_depth, trajectory=_trajectory,
                                  as_new=_as_new, hdf5_group=_hdf5_group)

    def _trj_check_version(self, version, python, force):
        """Checks for version mismatch

        Raises a VersionMismatchError if version of loaded trajectory and current pypet version
        do not match. In case of `force=True` error is not raised only a warning is emitted.

        """
        curr_python = pypetconstants.python_version_string

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

    def _trj_fill_run_table(self, traj, start, stop):
        """Fills the `run` overview table with information.

        Will also update new information.

        """

        def _make_row(info_dict):
            row = (info_dict['idx'],
                   info_dict['name'],
                   info_dict['time'],
                   info_dict['timestamp'],
                   info_dict['finish_timestamp'],
                   info_dict['runtime'],
                   info_dict['parameter_summary'],
                   info_dict['short_environment_hexsha'],
                   info_dict['completed'])
            return row

        runtable = getattr(self._overview_group, 'runs')

        rows = []
        updated_run_information = traj._updated_run_information
        for idx in range(start, stop):
            info_dict = traj._run_information[traj._single_run_ids[idx]]
            rows.append(_make_row(info_dict))
            updated_run_information.discard(idx)

        if rows:
            runtable.append(rows)
            runtable.flush()

        # Store all runs that are updated and that have not been stored yet
        rows = []
        indices = []
        for idx in updated_run_information:
            info_dict = traj.f_get_run_information(idx, copy=False)
            rows.append(_make_row(info_dict))
            indices.append(idx)

        if rows:
            runtable.modify_coordinates(indices, rows)

        traj._updated_run_information = set()

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
                                      'derived_parameters_per_run': pt.IntCol(pos=pos + 4)})

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
                                    flags=(HDF5StorageService.ADD_ROW,
                                           HDF5StorageService.MODIFY_ROW))


        # Fill table with dummy entries starting from the current table size
        actual_rows = runtable.nrows
        self._trj_fill_run_table(traj, actual_rows, len(traj._run_information))
        # stop != len(traj) to allow immediate post-proc with QUEUE wrapping

        # Store the annotations and comment of the trajectory node
        self._grp_store_group(traj, store_data=pypetconstants.STORE_DATA,
                                  with_links=False,
                                  recursive=False,
                                  _hdf5_group=self._trajectory_group)

        # Store the list of explored paramters
        self._trj_store_explorations(traj)

        # Prepare the exploration tables
        # Prepare the overview tables
        tostore_tables = []

        for name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():

            # Check if we want the corresponding overview table
            # If the trajectory does not contain information about the table
            # we assume it should be created.

            if getattr(self, name):
                tostore_tables.append(table_name)

        self._srvc_make_overview_tables(tostore_tables, traj)

    def _trj_load_exploration(self, traj):
        """Recalls names of all explored parameters"""
        if hasattr(self._overview_group, 'explorations'):
            explorations_table = self._overview_group._f_get_child( 'explorations')
            for row in explorations_table.iterrows():
                param_name = row['explorations'].decode('utf-8')
                if param_name not in traj._explored_parameters:
                    traj._explored_parameters[param_name] = None
        else:
            # This is for backwards compatibility
            for what in ('parameters', 'derived_parameters'):
                if hasattr(self._trajectory_group, what):
                    parameters = self._trajectory_group._f_get_child(what)
                    for group in parameters._f_walk_groups():
                        if self._all_get_from_attrs(group, HDF5StorageService.LENGTH):
                            group_location = group._v_pathname
                            full_name = '.'.join(group_location.split('/')[2:])
                            traj._explored_parameters[full_name] = None

    def _trj_store_explorations(self, traj):
        """Stores a all explored parameter names for internal recall"""
        nexplored = len(traj._explored_parameters)
        if nexplored > 0:
            if hasattr(self._overview_group, 'explorations'):
                explorations_table = self._overview_group._f_get_child('explorations')
                if len(explorations_table) != nexplored:
                    self._hdf5file.remove_node(where=self._overview_group,
                                         name='explorations')
        if not hasattr(self._overview_group, 'explorations'):
            explored_list = list(traj._explored_parameters.keys())
            if explored_list:
                string_col = self._all_get_table_col('explorations',
                                                      explored_list,
                                                      'overview.explorations')
            else:
                string_col = pt.StringCol(1)
            description = {'explorations': string_col}
            explorations_table = self._hdf5file.create_table(where=self._overview_group,
                                                       name='explorations',
                                                       description=description)
            rows = [(x.encode('utf-8'),) for x in explored_list]
            if rows:
                explorations_table.append(rows)
                explorations_table.flush()

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

            paramdescriptiondict['comment'] = pt.StringCol(
                    pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH)

            paramdescriptiondict['value'] = pt.StringCol(
                    pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH, pos=2)

            if table_name == 'config_overview':
                if traj is not None:
                    expectedrows = len(traj._config)

            if table_name == 'parameters_overview':
                if traj is not None:
                    expectedrows = len(traj._parameters)

            if table_name == 'explored_parameters_overview':
                paramdescriptiondict['range'] = pt.StringCol(
                    pypetconstants.HDF5_STRCOL_MAX_RANGE_LENGTH)
                paramdescriptiondict['length'] = pt.IntCol()
                if traj is not None:
                    expectedrows = len(traj._explored_parameters)

            if table_name.endswith('summary'):
                paramdescriptiondict['hexdigest'] = pt.StringCol(64, pos=10)

            # Check if the user provided an estimate of the amount of results per run
            # This can help to speed up storing
            if table_name == 'derived_parameters_overview':

                expectedrows = self._derived_parameters_per_run

                if traj is not None:
                    expectedrows *= len(traj)
                    expectedrows += len(traj._derived_parameters)

            if table_name == 'results_overview':
                expectedrows = self._results_per_run

                if traj is not None:
                    expectedrows *= len(traj)
                    expectedrows += len(traj._results)

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

    def _trj_store_trajectory(self, traj, only_init=False, store_data=pypetconstants.STORE_DATA,
                              max_depth=None):
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
                               ' `%s` but this trajectory is already found in file `%s`.'
                               'Did you try to accidentally overwrite existing data? If '
                               'you DO want to override existing data, use `overwrite_file=True`.'
                               'Note that this deletes the whole HDF5 file not just the particular '
                               'trajectroy therein! ' %
                               (traj.v_name, self._filename))

        # Extract HDF5 settings from the trajectory
        self._srvc_check_hdf_properties(traj)

        # Store the trajectory for the first time if necessary:
        if self._trajectory_group is None:
            self._trajectory_group = self._hdf5file.create_group(where='/',
                                                           name=self._trajectory_name,
                                                           title=self._trajectory_name,
                                                           filters=self._all_get_filters())
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
                self._tree_store_sub_branch(traj, child_name, store_data=store_data,
                                            with_links=True,
                                            recursive=True, max_depth=max_depth,
                                            hdf5_group=self._trajectory_group)

            self._logger.info('Finished storing Trajectory `%s`.' % self._trajectory_name)
        else:
            self._logger.info('Finished init or meta data update for `%s`.' %
                              self._trajectory_name)
        traj._stored = True

    def _tree_store_sub_branch(self, traj_node, branch_name,
                               store_data=pypetconstants.STORE_DATA,
                               with_links=True,
                               recursive=False,
                               max_depth=None,
                               hdf5_group=None):
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

        :param max_depth:

            Maximum depth to store

        :param hdf5_group:

            HDF5 node in the file corresponding to `traj_node`

        """
        if store_data == pypetconstants.STORE_NOTHING:
            return

        if max_depth is None:
            max_depth = float('inf')

        if hdf5_group is None:
            # Get parent hdf5 node
            location = traj_node.v_full_name
            hdf5_location = location.replace('.', '/')
            try:
                if location == '':
                    hdf5_group = self._trajectory_group
                else:
                    hdf5_group = self._hdf5file.get_node( where=self._trajectory_group,
                                                         name=hdf5_location)
            except pt.NoSuchNodeError:
                self._logger.debug('Cannot store `%s` the parental hdf5 node with path `%s` does '
                                     'not exist on disk.' %
                                     (traj_node.v_name, hdf5_location))

                if traj_node.v_is_leaf:
                    self._logger.error('Cannot store `%s` the parental hdf5 '
                                       'node with path `%s` does '
                                       'not exist on disk! The child '
                                       'you want to store is a leaf node,'
                                       'that cannot be stored without '
                                       'the parental node existing on '
                                       'disk.' % (traj_node.v_name, hdf5_location))
                    raise
                else:
                    self._logger.debug('I will try to store the path from trajectory root to '
                                         'the child now.')

                    self._tree_store_sub_branch(traj_node._nn_interface._root_instance,
                                                traj_node.v_full_name + '.' + branch_name,
                                                store_data=store_data, with_links=with_links,
                                                recursive=recursive,
                                                max_depth=max_depth + traj_node.v_depth,
                                                hdf5_group=self._trajectory_group)
                    return

        current_depth = 1

        split_names = branch_name.split('.')

        leaf_name = split_names.pop()

        for name in split_names:
            if current_depth > max_depth:
                return
            # Store along a branch
            self._tree_store_nodes_dfs(traj_node, name, store_data=store_data, with_links=with_links,
                                   recursive=False, max_depth=max_depth,
                                   current_depth=current_depth, parent_hdf5_group=hdf5_group)
            current_depth += 1

            traj_node = traj_node._children[name]

            hdf5_group = getattr(hdf5_group, name)

        # Store final group and recursively everything below it
        if current_depth <= max_depth:
            self._tree_store_nodes_dfs(traj_node, leaf_name, store_data=store_data,
                               with_links=with_links, recursive=recursive,
                               max_depth=max_depth, current_depth=current_depth,
                               parent_hdf5_group=hdf5_group)


    ########################  Storing and Loading Sub Trees #######################################

    def _tree_create_leaf(self, name, trajectory, hdf5_group):
        """ Creates a new pypet leaf instance.

        Returns the leaf and if it is an explored parameter the length of the range.

        """
        class_name = self._all_get_from_attrs(hdf5_group, HDF5StorageService.CLASS_NAME)

        # Create the instance with the appropriate constructor
        class_constructor = trajectory._create_class(class_name)

        instance = trajectory._construct_instance(class_constructor, name)

        return instance

    def _tree_load_nodes_dfs(self, parent_traj_node, load_data, with_links, recursive,
                         max_depth, current_depth, trajectory, as_new, hdf5_group):
        """Loads a node from hdf5 file and if desired recursively everything below

        :param parent_traj_node: The parent node whose child should be loaded
        :param load_data: How to load the data
        :param with_links: If links should be loaded
        :param recursive: Whether loading recursively below hdf5_group
        :param max_depth: Maximum depth
        :param current_depth: Current depth
        :param trajectory: The trajectory object
        :param as_new: If trajectory is loaded as new
        :param hdf5_group: The hdf5 group containing the child to be loaded

        """
        if max_depth is None:
            max_depth = float('inf')

        loading_list = [(parent_traj_node, current_depth, hdf5_group)]

        while loading_list:
            parent_traj_node, current_depth, hdf5_group = loading_list.pop()

            if isinstance(hdf5_group, pt.link.SoftLink):
                if with_links:
                    # We end up here when auto-loading a soft link
                    self._tree_load_link(parent_traj_node, load_data=load_data, traj=trajectory,
                                         as_new=as_new, hdf5_soft_link=hdf5_group)
                continue


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
                    instance = self._tree_create_leaf(name, trajectory, hdf5_group)

                    # Add the instance to the trajectory tree
                    parent_traj_node._add_leaf_from_storage(args=(instance,), kwargs={})

                self._prm_load_parameter_or_result(instance, load_data=load_data,
                                                   _hdf5_group=hdf5_group)
                if as_new:
                    instance._stored = False

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
                    traj_group = parent_traj_node._add_group_from_storage(args=args, kwargs={})

                # Load annotations and comment
                self._grp_load_group(traj_group, load_data=load_data, with_links=with_links,
                                     recursive=False, max_depth=max_depth,
                                     _traj=trajectory, _as_new=as_new,
                                     _hdf5_group=hdf5_group)

                if recursive and current_depth < max_depth:
                    new_depth = current_depth + 1
                    for children in (hdf5_group._v_groups, hdf5_group._v_links):
                        for new_hdf5_group_name in children:
                            new_hdf5_group = children[new_hdf5_group_name]
                            loading_list.append((traj_group, new_depth, new_hdf5_group))

    def _tree_load_link(self, new_traj_node, load_data, traj, as_new, hdf5_soft_link):
        """ Loads a link
        
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
                                               with_links=False, recursive=False, _trajectory=traj,
                                               _as_new=as_new, _hdf5_group=self._trajectory_group)

                if (load_data == pypetconstants.OVERWRITE_DATA and
                            link_name in new_traj_node._links):
                    new_traj_node.f_remove_link(link_name)
                if not link_name in new_traj_node._links:
                    new_traj_node._nn_interface._add_generic(new_traj_node,
                                                                type_name=nn.LINK,
                                                                group_type_name=nn.GROUP,
                                                                args=(link_name,
                                                                      traj.f_get(full_name)),
                                                                kwargs={},
                                                                add_prefix=False,
                                                                check_naming=False)
                else:
                    raise RuntimeError('You shall not pass!')
        except pt.NoSuchNodeError:
            self._logger.error('Link `%s` under `%s` is broken, cannot load it, '
                               'I will ignore it, you have to '
                               'manually delete it!' %
                               (hdf5_soft_link._v_name, new_traj_node.v_full_name))

    def _tree_store_nodes_dfs(self, parent_traj_node, name, store_data, with_links, recursive,
                          max_depth, current_depth,
                          parent_hdf5_group):
        """Stores a node to hdf5 and if desired stores recursively everything below it.

        :param parent_traj_node: The parental node
        :param name: Name of node to be stored
        :param store_data: How to store data
        :param with_links: If links should be stored
        :param recursive: Whether to store recursively the subtree
        :param max_depth: Maximum recursion depth in tree
        :param current_depth: Current depth
        :param parent_hdf5_group: Parent hdf5 group

        """
        if max_depth is None:
            max_depth = float('inf')

        store_list = [(parent_traj_node, name, current_depth, parent_hdf5_group)]

        while store_list:
            parent_traj_node, name, current_depth, parent_hdf5_group = store_list.pop()

            # Check if we create a link
            if name in parent_traj_node._links:
                if with_links:
                    self._tree_store_link(parent_traj_node, name, parent_hdf5_group)
                continue

            traj_node = parent_traj_node._children[name]

            # If the node does not exist in the hdf5 file create it
            if not hasattr(parent_hdf5_group, name):
                newly_created = True
                new_hdf5_group = self._hdf5file.create_group(where=parent_hdf5_group,
                                                       name=name, filters=self._all_get_filters())
            else:
                newly_created = False
                new_hdf5_group = getattr(parent_hdf5_group, name)

            if traj_node.v_is_leaf:
                self._prm_store_parameter_or_result(traj_node, store_data=store_data,
                                                     _hdf5_group=new_hdf5_group,
                                                    _newly_created=newly_created)

            else:
                self._grp_store_group(traj_node, store_data=store_data, with_links=with_links,
                                      recursive=False, max_depth=max_depth,
                                      _hdf5_group=new_hdf5_group,
                                      _newly_created=newly_created)

                if recursive and current_depth < max_depth:
                    for child in traj_node._children.keys():
                        store_list.append((traj_node, child, current_depth + 1, new_hdf5_group))

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
            to_link_hdf5_group = self._hdf5file.get_node(where=linking_name)
        except pt.NoSuchNodeError:
            self._logger.debug('Could not store link `%s` under `%s` immediately, '
                               'need to store `%s` first. '
                               'Will store the link right after.' % (link,
                                                                     node_in_traj.v_full_name,
                                                                     linked_traj_node.v_full_name))
            root = node_in_traj._nn_interface._root_instance
            self._tree_store_sub_branch(root, linked_traj_node.v_full_name,
                                        store_data=pypetconstants.STORE_DATA_SKIPPING,
                                        with_links=False, recursive=False,
                                        hdf5_group=self._trajectory_group)
            to_link_hdf5_group = self._hdf5file.get_node(where=linking_name)
        self._hdf5file.create_soft_link(where=hdf5_group,
                                  name=link,
                                  target=to_link_hdf5_group)

    ######################## Storing a Single Run ##########################################

    def _srn_store_single_run(self, traj,
                              recursive=True,
                              store_data=pypetconstants.STORE_DATA,
                              max_depth=None):
        """ Stores a single run instance to disk (only meta data)"""

        if store_data != pypetconstants.STORE_NOTHING:
            self._logger.debug('Storing Data of single run `%s`.' % traj.v_crun)
            if max_depth is None:
                max_depth = float('inf')
            for name_pair in traj._new_nodes:
                _, name = name_pair
                parent_group, child_node = traj._new_nodes[name_pair]
                if not child_node._stored:
                    self._tree_store_sub_branch(parent_group, name,
                                          store_data=store_data,
                                          with_links=True,
                                          recursive=recursive,
                                          max_depth=max_depth - child_node.v_depth,
                                          hdf5_group=None)
            for name_pair in traj._new_links:
                _, link = name_pair
                parent_group, _ = traj._new_links[name_pair]
                self._tree_store_sub_branch(parent_group, link,
                                            store_data=store_data,
                                            with_links=True,
                                            recursive=recursive,
                                            max_depth=max_depth - parent_group.v_depth - 1,
                                            hdf5_group=None)

    def _srn_summarize_explored_parameters(self, paramlist):
        """Summarizes the parameter settings.

        :param run_name: Name of the single run

        :param paramlist: List of explored parameters

        :param add_table: Whether to add the overview table

        :param create_run_group:

            If a group with the particular name should be created if it does not exist.
            Might be necessary when trajectories are merged.

        """

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

        return runsummary


    ################# Methods used across Storing and Loading different Items ##################

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

        if HDF5StorageService.REMOVE_ROW in flags:
            # If we want to remove a row, we don't need to extract information
            insert_dict = {}
        else:
            # Extract information to insert from the instance and the additional info dict
            colnames = set(table.colnames)
            insert_dict = self._all_extract_insert_dict(instance, colnames, additional_info)

        # Write the table entry
        self._all_add_or_modify_row(fullname, insert_dict, table, condition=condition,
                                    condvars=condvars, flags=flags)


    def _all_get_or_create_table(self, where, tablename, description, expectedrows=None):
        """Creates a new table, or if the table already exists, returns it."""
        where_node = self._hdf5file.get_node(where)

        if not tablename in where_node:
            if not expectedrows is None:
                table = self._hdf5file.create_table(where=where_node, name=tablename,
                                              description=description, title=tablename,
                                              expectedrows=expectedrows,
                                              filters=self._all_get_filters())
            else:
                table = self._hdf5file.create_table(where=where_node, name=tablename,
                                              description=description, title=tablename,
                                              filters=self._all_get_filters())
        else:
            table = where_node._f_get_child(tablename)

        return table

    def _all_get_node_by_name(self, name):
        """Returns an HDF5 node by the path specified in `name`"""
        path_name = name.replace('.', '/')
        where = '/%s/%s' % (self._trajectory_name, path_name)
        return self._hdf5file.get_node(where=where)

    @staticmethod
    def _all_get_from_attrs(ptitem, name):
        """Gets an attribute `name` from `ptitem`, returns None if attribute does not exist."""
        try:
            return getattr(ptitem._v_attrs, name)
        except AttributeError:
            return None

    @staticmethod
    def _all_set_attr(ptitem, name, value):
        """Sets an attribute `name` from `ptitem`"""
        return setattr(ptitem._v_attrs, name, value)

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
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_TUPLE)

        elif type(data) is list:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_LIST)

        elif type(data) is np.ndarray:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_NDARRAY)

        elif type(data) is np.matrix:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_MATRIX)

        elif type(data) in pypetconstants.PARAMETER_SUPPORTED_DATA:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_SCALAR)

            strtype = type(data).__name__

            if not strtype in pypetconstants.PARAMETERTYPEDICT:
                raise TypeError('I do not know how to handle `%s` its type is `%s`.' %
                                (str(data), repr(type(data))))

            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.SCALAR_TYPE, strtype)

        elif type(data) is dict:
            if len(data) > 0:
                HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_DICT)
            else:
                HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_EMPTY_DICT)
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

                HDF5StorageService._all_set_attr(ptitem, prefix +
                                       HDF5StorageService.SCALAR_TYPE, strtype)
        elif (type(data) in (np.ndarray, np.matrix) and
                  np.issubdtype(data.dtype, str)):
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.SCALAR_TYPE,
                                   str.__name__)

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
        colltype = self._all_get_from_attrs(ptitem, prefix + HDF5StorageService.COLL_TYPE)
        type_changed = False

        # Check what the original data type was from the hdf5 node attributes
        if colltype == HDF5StorageService.COLL_SCALAR:
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

                    if typestr == str.__name__:
                        data = data.decode(self._encoding)
                    else:
                        try:
                            data = pypetconstants.PARAMETERTYPEDICT[typestr](data)
                        except KeyError:
                            # For compatibility with files from older pypet versions
                            data = pypetconstants.COMPATPARAMETERTYPEDICT[typestr](data)

                    type_changed = True

        elif (colltype == HDF5StorageService.COLL_TUPLE or
                        colltype == HDF5StorageService.COLL_LIST):
            # Here data item was originally a tuple or a list

            if type(data) is not list and type is not tuple:
                # If the original type cannot be recalled, first convert it to a list
                type_changed = True
                data = list(data)

            if len(data) > 0:
                first_item = data[0]
                # Check if the type of the first item was conserved
                if not typestr == type(first_item).__name__:

                    if not isinstance(data, list):
                        data = list(data)

                    # If type was not conserved we need to convert all items
                    # in the list or tuple
                    for idx, item in enumerate(data):
                        if typestr == str.__name__:
                            data[idx] = data[idx].decode(self._encoding)
                        else:
                            try:
                                data[idx] = pypetconstants.PARAMETERTYPEDICT[typestr](item)
                            except KeyError:
                                # For compatibility with files from older pypet versions:
                                data[idx] = pypetconstants.COMPATPARAMETERTYPEDICT[typestr](item)
                        type_changed = True

            if colltype == HDF5StorageService.COLL_TUPLE:
                # If it was originally a tuple we need to convert it back to tuple
                if type(data) is not tuple:
                    data = tuple(data)
                    type_changed = True
        elif colltype == HDF5StorageService.COLL_EMPTY_DICT:
            data = {}
            type_changed = True
        elif isinstance(data, np.ndarray):

            if typestr == str.__name__:
                data = np.core.defchararray.decode(data, self._encoding)
                type_changed = True

            if colltype == HDF5StorageService.COLL_MATRIX:
                # Here data item was originally a matrix
                data = np.matrix(data)
                type_changed = True

        return data, type_changed

    @staticmethod
    def _all_kill_iterator(iterator):
        if iterator is not None:
            try:
                while True:
                    next(iterator)
            except StopIteration:
                pass

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
        if len(flags) == 0:
            # No flags means no-op
            return

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

        # multiple_entries = []

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
                    table.remove_rows(start=row_number, stop=row_number+1)
                except NotImplementedError:
                    pass
                    # We get here if we try to remove the last row of a table
                    # there is nothing we can do but keep it :-(
        else:
            raise ValueError('Something is wrong, you might not have found '
                             'a row, or your flags are not set appropriately')

        self._all_kill_iterator(row_iterator)
        table.flush()

        if HDF5StorageService.REMOVE_ROW not in flags and row is None:
            raise RuntimeError('Could not add or modify entries of `%s` in '
                               'table %s' % (item_name, table._v_name))

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
            comment = self._all_cut_string(item.v_comment.encode('utf-8'),
                                           pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH,
                                           self._logger)

            insert_dict['comment'] = comment

        if 'location' in colnames:
            insert_dict['location'] = item.v_location.encode('utf-8')

        if 'name' in colnames:
            name = item._name if (not item.v_is_root or not item.v_is_run) else item._crun
            insert_dict['name'] = name.encode('utf-8')

        if 'class_name' in colnames:
            insert_dict['class_name'] = item.f_get_class_name().encode('utf-8')

        if 'value' in colnames:
            insert_dict['value'] = self._all_cut_string(
                item.f_val_to_str().encode('utf-8'),
                pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH,
                self._logger)

        if 'hexdigest' in colnames:
            insert_dict['hexdigest'] = additional_info['hexdigest']

        if 'idx' in colnames:
            insert_dict['idx'] = item.v_idx

        if 'time' in colnames:
            time_ = item._time
            insert_dict['time'] = time_.encode('utf-8')

        if 'timestamp' in colnames:
            timestamp = item._timestamp
            insert_dict['timestamp'] = timestamp

        if 'range' in colnames:
            third_length = pypetconstants.HDF5_STRCOL_MAX_RANGE_LENGTH // 3 + 10
            item_range = itools.islice(item.f_get_range(copy=False), 0, third_length)
            range_string = ', '.join([repr(x) for x in item_range])
            insert_dict['range'] = self._all_cut_string(
                range_string.encode('utf-8'),
                pypetconstants.HDF5_STRCOL_MAX_RANGE_LENGTH,
                self._logger)

        # To allow backwards compatibility
        if 'array' in colnames:
            third_length = pypetconstants.HDF5_STRCOL_MAX_RANGE_LENGTH // 3 + 10
            item_range = itools.islice(item.f_get_range(copy=False), 0, third_length)
            range_string = ', '.join([repr(x) for x in item_range])
            insert_dict['array'] = self._all_cut_string(
                range_string.encode('utf-8'),
                pypetconstants.HDF5_STRCOL_MAX_RANGE_LENGTH,
                self._logger)

        if 'version' in colnames:
            insert_dict['version'] = item.v_version.encode('utf-8')

        if 'python' in colnames:
            insert_dict['python'] = item.v_python.encode('utf-8')

        if 'finish_timestamp' in colnames:
            insert_dict['finish_timestamp'] = item._finish_timestamp_run

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
            string = string[0:max_length - 3] + '...'.encode('utf-8')

        return string

    def _all_create_or_get_group(self, name, parent_hdf5_group=None):
        """Creates or returns a group"""
        if not name in parent_hdf5_group:
            new_hdf5_group = self._hdf5file.create_group(where=parent_hdf5_group,
                                                      name=name,
                                                      title=name,
                                                      filters=self._all_get_filters())
            return new_hdf5_group, True
        else:
            new_hdf5_group = parent_hdf5_group._f_get_child(name)
            return new_hdf5_group, False

    def _all_create_or_get_groups(self, key, start_hdf5_group=None):
        """Creates new or follows existing group nodes along a given colon separated `key`.

        :param key:

            Colon separated path along hdf5 file, e.g. `parameters.mobiles.cars`.

        :param start_hdf5_group:

            HDF5 group from where to start, leave `None` for the trajectory group.

        :return:

            Final group node, e.g. group node with name `cars`.

        """
        if start_hdf5_group is None:
            newhdf5_group = self._trajectory_group
        else:
            newhdf5_group = start_hdf5_group
        created = False
        if key == '':
            return newhdf5_group, created
        split_key = key.split('.')
        for name in split_key:
            newhdf5_group, created = self._all_create_or_get_group(name, newhdf5_group)

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

            anno_dict = item_with_annotations.v_annotations._dict

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
                         with_links=True, recursive=False, max_depth=None,
                         _hdf5_group=None, _newly_created=False):
        """Stores a group node.

        For group nodes only annotations and comments need to be stored.

        """
        if store_data == pypetconstants.STORE_NOTHING:
            return
        elif store_data == pypetconstants.STORE_DATA_SKIPPING and traj_group._stored:
            self._logger.debug('Already found `%s` on disk I will not store it!' %
                                   traj_group.v_full_name)
        elif not recursive:
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

            # Signal completed node loading
            self._node_processing_timer.signal_update()

        if recursive:
            parent_traj_group = traj_group.f_get_parent()
            parent_hdf5_group = self._all_create_or_get_groups(parent_traj_group.v_full_name)[0]

            self._tree_store_nodes_dfs(parent_traj_group, traj_group.v_name, store_data=store_data,
                                       with_links=with_links, recursive=recursive,
                                       max_depth=max_depth, current_depth=0,
                                       parent_hdf5_group=parent_hdf5_group)

    def _grp_load_group(self, traj_group, load_data=pypetconstants.LOAD_DATA, with_links=True,
                        recursive=False, max_depth=None,
                        _traj=None, _as_new=False, _hdf5_group=None):
        """Loads a group node and potentially everything recursively below"""
        if _hdf5_group is None:
            _hdf5_group = self._all_get_node_by_name(traj_group.v_full_name)
            _traj = traj_group.v_root

        if recursive:
            parent_traj_node = traj_group.f_get_parent()
            self._tree_load_nodes_dfs(parent_traj_node, load_data=load_data, with_links=with_links,
                                  recursive=recursive, max_depth=max_depth,
                                  current_depth=0,
                                  trajectory=_traj, as_new=_as_new,
                                  hdf5_group=_hdf5_group)
        else:
            if load_data == pypetconstants.LOAD_NOTHING:
                return

            elif load_data == pypetconstants.OVERWRITE_DATA:
                traj_group.v_annotations.f_empty()
                traj_group.v_comment = ''

            self._all_load_skeleton(traj_group, _hdf5_group)
            traj_group._stored = not _as_new

            # Signal completed node loading
            self._node_processing_timer.signal_update()

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
        for key, data in data_dict.items():
            if not key in flags_dict:
                dtype = type(data)
                if (dtype is np.ndarray or dtype is dict) and len(data) == 0:
                        # Empty containers are stored as an Array
                        # No need to ask for tuple or list, because they are always
                        # stored as arrays.
                        flags_dict[key] = HDF5StorageService.ARRAY
                        continue
                else:
                    try:
                        flags_dict[key] = HDF5StorageService.TYPE_FLAG_MAPPING[dtype]
                    except KeyError:
                        raise pex.NoSuchServiceError('I cannot store `%s`, I do not understand the'
                                                     'type `%s`.' % (key, str(dtype)))

    def _prm_meta_add_summary(self, instance):
        """Adds data to the summary tables and returns if `instance`s comment has to be stored.

        Also moves comments upwards in the hierarchy if purge_duplicate_comments is true
        and a lower index run has completed. Only necessary for *multiprocessing*.

        :return: Tuple

            * String specifying the subtree

            * Boolean whether to store the comment to `instance`s hdf5 node

        """
        if instance.v_comment == '':
            return False

        where = instance.v_branch
        definitely_store_comment = True

        # Get the hexdigest of the comment to see if such a comment has been stored before
        bytes_comment = instance.v_comment.encode('utf-8')
        hexdigest = hashlib.sha1(bytes_comment).hexdigest()
        hexdigest = hexdigest.encode('utf-8')

        # Get the overview table
        table_name = where + '_summary'

        # Check if the overview table exists, otherwise skip the rest of
        # the meta adding
        if table_name in self._overview_group:
            table = getattr(self._overview_group, table_name)
        else:
            return definitely_store_comment


        try:
            condvars = {'hexdigestcol': table.cols.hexdigest,
                'hexdigest': hexdigest}

            condition = """(hexdigestcol == hexdigest)"""

            row_iterator = table.where(condition, condvars=condvars)

            row = None
            try:
                row = next(row_iterator)
            except StopIteration:
                pass

            if row is None:
                self._all_store_param_or_result_table_entry(instance, table,
                                                            flags=(
                                                                HDF5StorageService.ADD_ROW,),
                                                            additional_info={
                                                                'hexdigest': hexdigest})

                definitely_store_comment = True
            else:
                definitely_store_comment = False
                self._all_kill_iterator(row_iterator)

        except pt.NoSuchNodeError:
            definitely_store_comment = True

        return definitely_store_comment

    def _prm_add_meta_info(self, instance, group, overwrite=False):
        """Adds information to overview tables and meta information to
        the `instance`s hdf5 `group`.

        :param instance: Instance to store meta info about
        :param group: HDF5 group of instance
        :param overwrite: If data should be explicitly overwritten

        """

        if overwrite:
            flags = ()
        else:
            flags = (HDF5StorageService.ADD_ROW,)

        definitely_store_comment = True
        try:
            # Check if we need to store the comment. Maybe update the overview tables
            # accordingly if the current run index is lower than the one in the table.
            definitely_store_comment = self._prm_meta_add_summary(instance)

            try:
                # Update the summary overview table
                table_name = instance.v_branch + '_overview'

                table = getattr(self._overview_group, table_name)
                if len(table) < pypetconstants.HDF5_MAX_OVERVIEW_TABLE_LENGTH:

                    self._all_store_param_or_result_table_entry(instance, table,
                                                                flags=flags)
            except pt.NoSuchNodeError:
                pass
        except Exception as exc:
            self._logger.error('Could not store information table due to `%s`.' % repr(exc))

        if ((not self._purge_duplicate_comments or definitely_store_comment) and
                    instance.v_comment != ''):
            # Only add the comment if necessary
            setattr(group._v_attrs, HDF5StorageService.COMMENT, instance.v_comment)

        # Add class name and whether node is a leaf to the HDF5 attributes
        setattr(group._v_attrs, HDF5StorageService.CLASS_NAME, instance.f_get_class_name())
        setattr(group._v_attrs, HDF5StorageService.LEAF, True)

        if instance.v_is_parameter and instance.v_explored:
            # If the stored parameter was an explored one we need to mark this in the
            # explored overview table
            try:
                tablename = 'explored_parameters_overview'
                table = getattr(self._overview_group, tablename)

                if len(table) < pypetconstants.HDF5_MAX_OVERVIEW_TABLE_LENGTH:
                    self._all_store_param_or_result_table_entry(instance, table,
                                                                flags=flags)
            except pt.NoSuchNodeError:
                pass
            except Exception as exc:
                self._logger.error('Could not store information '
                                   'table due to `%s`.' % repr(exc))

    def _prm_store_from_dict(self, fullname, store_dict, hdf5_group, store_flags, kwargs):
        """Stores a `store_dict`"""
        for key, data_to_store in store_dict.items():
            # self._logger.log(1, 'SUB-Storing %s [%s]', key, str(store_dict[key]))
            original_hdf5_group = None

            flag = store_flags[key]

            if '.' in key:
                original_hdf5_group = hdf5_group
                split_key = key.split('.')
                key = split_key.pop()
                for inner_key in split_key:
                    hdf5_group, newly_created =  self._all_create_or_get_group(inner_key,
                                                                                hdf5_group)
                    if newly_created:
                        setattr(hdf5_group._v_attrs, HDF5StorageService.STORAGE_TYPE,
                                HDF5StorageService.NESTED_GROUP)
                    else:
                        store_type = self._all_get_from_attrs(hdf5_group, HDF5StorageService.STORAGE_TYPE)
                        if store_type != HDF5StorageService.NESTED_GROUP:
                            raise ValueError('You want to nested results but `%s` is already '
                                             'of type `%s`!' % (hdf5_group._v_name, store_type))

            # Iterate through the data and store according to the storage flags
            if key in hdf5_group:
                # We won't change any data that is found on disk
                self._logger.debug(
                    'Found %s already in hdf5 node of %s, so I will ignore it.' %
                    (key, fullname))
                continue

            if flag == HDF5StorageService.TABLE:
                # self._logger.log(1, 'SUB-Storing %s TABLE', key)
                self._prm_write_into_pytable(key, data_to_store, hdf5_group, fullname,
                                             **kwargs)
            elif flag == HDF5StorageService.DICT:
                # self._logger.log(1, 'SUB-Storing %s DICT', key)
                self._prm_write_dict_as_table(key, data_to_store, hdf5_group, fullname,
                                              **kwargs)
            elif flag == HDF5StorageService.ARRAY:
                # self._logger.log(1, 'SUB-Storing %s ARRAY', key)
                self._prm_write_into_array(key, data_to_store, hdf5_group, fullname,
                                           **kwargs)
            elif flag in (HDF5StorageService.CARRAY,
                          HDF5StorageService.EARRAY,
                          HDF5StorageService.VLARRAY):
                self._prm_write_into_other_array(key, data_to_store,
                                                 hdf5_group, fullname,
                                                 flag=flag, **kwargs)
            elif flag in (HDF5StorageService.SERIES,
                          HDF5StorageService.FRAME,
                          #  HDF5StorageService.PANEL
                          ):
                # self._logger.log(1, 'SUB-Storing %s PANDAS', key)
                self._prm_write_pandas_data(key, data_to_store, hdf5_group, fullname,
                                            flag, **kwargs)
            elif flag == HDF5StorageService.SHARED_DATA:
                pass  # Shared data needs to be explicitly created and is not stored on
                # the fly
            else:
                raise RuntimeError('You shall not pass!')

            if original_hdf5_group is not None:
                hdf5_group = original_hdf5_group

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
        self._logger.debug('Storing `%s`.' % fullname)

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
                if isinstance(overwrite, str):
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

            self._prm_store_from_dict(fullname, store_dict, _hdf5_group, store_flags, kwargs)

            # Store annotations
            self._ann_store_annotations(instance, _hdf5_group, overwrite=overwrite)

            if _newly_created or overwrite is True:
                # If we created a new group or the parameter was extended we need to
                # update the meta information and summary tables
                self._prm_add_meta_info(instance, _hdf5_group,
                                        overwrite=not _newly_created)

            instance._stored = True

            #self._logger.debug('Finished Storing `%s`.' % fullname)
            # Signal completed node loading
            self._node_processing_timer.signal_update()

        except:
            # I anything fails, we want to remove the data of the parameter again
            self._logger.error(
                'Failed storing leaf `%s`. I will remove the hdf5 data I added  again.' % fullname)
            # Delete data
            for key in store_dict.keys():
                if key in  _hdf5_group:
                    hdf5_child = _hdf5_group._f_get_child(key)
                    hdf5_child._f_remove(recursive=True)
            # If no data left delete the whole parameter
            if _hdf5_group._v_nchildren == 0:
                _hdf5_group._f_remove(recursive=True)
            raise

    def _shared_write_shared_data(self, key, hdf5_group, full_name, **kwargs):
        try:
            data = kwargs.pop('obj', None)
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
                          #  HDF5StorageService.PANEL
                          ) :

                self._prm_write_pandas_data(key, data,
                                            hdf5_group,
                                            full_name, flag, **kwargs)
            else:
                self._prm_write_shared_array(key, data,
                                             hdf5_group, full_name, flag, **kwargs)

            hdf5data = hdf5_group._f_get_child(key)
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
                    column = self._all_get_table_col(key, [data], fullname)
                    description[colname] = column

        if 'description' in kwargs:
            description = kwargs.pop('description')

        if 'filters' in kwargs:
            filters = kwargs.pop('filters')
        else:
            filters = self._all_get_filters(kwargs)

        table = self._hdf5file.create_table(where=hdf5_group, name=key,
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

        new_table = group._f_get_child(key)

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
                self._logger.debug(
                    'filters are no longer supported by pandas')
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

            if 'expectedrows' in kwargs:
                self._logger.debug('expectedrows no longer supported by pandas, will '
                                   'ignore the option')

            name = group._v_pathname + '/' + key
            self._hdf5store.put(name, data, **kwargs)
            self._hdf5store.flush()
            self._hdf5file.flush()

            frame_group = group._f_get_child(key)
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
                factory = self._hdf5file.create_carray
            elif flag == HDF5StorageService.EARRAY:
                factory = self._hdf5file.create_earray
            elif flag == HDF5StorageService.VLARRAY:
                factory = self._hdf5file.create_vlarray
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
                other_array = factory(where=group, name=key, obj=data,
                                                filters=filters, **kwargs)
            except (ValueError, TypeError) as exc:
                try:
                    conv_data = data[:]
                    conv_data = np.core.defchararray.encode(conv_data, self.encoding)
                    other_array = factory(where=group, name=key,
                                                obj=conv_data,
                                                filters=filters, **kwargs)
                except Exception:
                    # Re-raise original Error
                    raise exc

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

                array = self._hdf5file.create_array(where=group,
                                              name=key, obj=data, **kwargs)
            except (TypeError, ValueError) as exc:
                try:
                    if type(data) is dict and len(data) == 0:
                        # We cannot store an empty dictionary,
                        # but we can use an empty tuple as a dummy.
                        conv_data = ()
                    elif isinstance(data, str):
                        conv_data = data.encode(self._encoding)
                    elif isinstance(data, int):
                        conv_data = np.int64(data)
                    else:
                        conv_data = []
                        for string in data:
                            conv_data.append(string.encode(self._encoding))
                    array = self._hdf5file.create_array(where=group,
                                                  name=key, obj=conv_data, **kwargs)
                except Exception:
                    # Re-raise original error
                    raise exc

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
        link = self._hdf5file.get_node(where=translated_name)
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
            _hdf5_group = self._hdf5file.get_node(where=where, name=node_name)

        if delete_only is None:
            if instance.v_is_group and not recursive and len(_hdf5_group._v_children) != 0:
                    raise TypeError('You cannot remove the group `%s`, it has children, please '
                                    'use `recursive=True` to enforce removal.' %
                                    instance.v_full_name)
            _hdf5_group._f_remove(recursive=True)
        else:
            if not instance.v_is_leaf:
                raise ValueError('You can only choose `delete_only` mode for leafs.')

            if isinstance(delete_only, str):
                delete_only = [delete_only]

            for delete_item in delete_only:
                if (remove_from_item and
                        hasattr(instance, '__contains__') and
                        hasattr(instance, '__delattr__') and
                            delete_item in instance):
                    delattr(instance, delete_item)
                try:
                    _hdf5_sub_group = self._hdf5file.get_node(where=_hdf5_group,
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

            if len(description_dict) > ptpa.MAX_COLUMNS:
                # For optimization we want to store the original data types into another table
                # and split the tables into several ones
                new_table_group = self._hdf5file.create_group(where=hdf5_group,
                                                    name=tablename,
                                                    filters=self._all_get_filters(kwargs.copy()))

                count = 0
                for innerkey in description_dict:
                    val = description_dict[innerkey]
                    if count == ptpa.MAX_COLUMNS:
                        description_dicts.append({})
                        count = 0
                    description_dicts[-1][innerkey] = val
                    count += 1

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

                table = self._hdf5file.create_table(where=hdf5_group, name=tblname,
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
                if idx == 0 and len(description_dict) <= ptpa.MAX_COLUMNS:
                    # We only have a single table and
                    # we can store the original data types as attributes
                    for field_name in data_type_dict:
                        type_description = data_type_dict[field_name]
                        self._all_set_attr(table, field_name, type_description)

                    setattr(table._v_attrs, HDF5StorageService.STORAGE_TYPE,
                            HDF5StorageService.TABLE)

                table.flush()
                self._hdf5file.flush()

            if len(description_dict) > ptpa.MAX_COLUMNS:
                # We have potentially many split tables and the data types are
                # stored into an additional table for performance reasons
                tblname = tablename + '__' + HDF5StorageService.STORAGE_TYPE
                field_names, data_types = list(zip(*data_type_dict.items()))
                data_type_table_dict = {'field_name': field_names, 'data_type': data_types}
                descr_dict, _ = self._prm_make_description(data_type_table_dict, fullname)

                table = self._hdf5file.create_table(where=hdf5_group, name=tblname,
                                              description=descr_dict,
                                              title=tblname,
                                              expectedrows=len(field_names),
                                              filters=self._all_get_filters(kwargs))

                row = table.row

                for n in range(len(field_names)):
                    # Fill the columns with data

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
            col = self._all_get_table_col(key, val, fullname)

            descriptiondict[key] = col

        return descriptiondict, original_data_type_dict

    def _all_get_table_col(self, key, column, fullname):
        """ Creates a pytables column instance.

        The type of column depends on the type of `column[0]`.
        Note that data in `column` must be homogeneous!

        """
        val = column[0]

        try:

            # # We do not want to loose int_
            if type(val) is int:
                return pt.IntCol()

            if isinstance(val, (str, bytes)):
                itemsize = int(self._prm_get_longest_stringsize(column))
                return pt.StringCol(itemsize)

            if isinstance(val, np.ndarray):
                if (np.issubdtype(val.dtype, str) or
                        np.issubdtype(val.dtype, bytes)):
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

    def _prm_load_into_dict(self, full_name, load_dict, hdf5_group, instance,
                            load_only, load_except, load_flags, _prefix = ''):
        """Loads into dictionary"""
        for node in hdf5_group:

            load_type = self._all_get_from_attrs(node, HDF5StorageService.STORAGE_TYPE)

            if _prefix:
                load_name = '%s.%s' % (_prefix, node._v_name)
            else:
                load_name = node._v_name

            if load_type == HDF5StorageService.NESTED_GROUP:
                self._prm_load_into_dict(full_name=full_name,
                                         load_dict=load_dict,
                                         hdf5_group=node,
                                         instance=instance,
                                         load_only=load_only,
                                         load_except=load_except,
                                         load_flags=load_flags,
                                         _prefix=load_name)
                continue

            if load_only is not None:

                if load_name not in load_only:
                    continue
                else:
                    load_only.remove(load_name)

            elif load_except is not None:
                if load_name in load_except:
                    load_except.remove(load_name)
                    continue

            # Recall from the hdf5 node attributes how the data was stored and reload accordingly
            if load_name in load_flags:
                load_type = load_flags[load_name]

            if load_type == HDF5StorageService.DICT:
                to_load = self._prm_read_dictionary(node, full_name)
            elif load_type == HDF5StorageService.TABLE:
                to_load = self._prm_read_table(node, full_name)
            elif load_type in (HDF5StorageService.ARRAY, HDF5StorageService.CARRAY,
                                HDF5StorageService.EARRAY, HDF5StorageService.VLARRAY):
                to_load = self._prm_read_array(node, full_name)
            elif load_type in (HDF5StorageService.FRAME,
                               HDF5StorageService.SERIES,
                               #  HDF5StorageService.PANEL
                               ):
                to_load = self._prm_read_pandas(node, full_name)
            elif load_type.startswith(HDF5StorageService.SHARED_DATA):
                to_load = self._prm_read_shared_data(node, instance)
            else:
                raise pex.NoSuchServiceError('Cannot load %s, do not understand the hdf5 file '
                                             'structure of %s [%s].' %
                                             (full_name, str(node), str(load_type)))

            if to_load is None:
                raise RuntimeError('You shall not pass!')

            load_dict[load_name] = to_load

    def _prm_load_parameter_or_result(self, instance,
                                      load_data=pypetconstants.LOAD_DATA,
                                      load_only=None,
                                      load_except=None,
                                      load_flags=None,
                                      with_links=False,
                                      recursive=False,
                                      max_depth=None,
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

        :param max_depth:

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
                self._logger.debug('Parameter `%s` is locked, I will skip loading.' %
                                     instance.v_full_name)
                return
            instance.f_empty()
            instance.v_annotations.f_empty()
            instance.v_comment = ''

        self._all_load_skeleton(instance, _hdf5_group)
        instance._stored = True

        # If load only is just a name and not a list of names, turn it into a 1 element list
        if isinstance(load_only, str):
            load_only = [load_only]
        if isinstance(load_except, str):
            load_except = [load_except]

        if load_data == pypetconstants.LOAD_SKELETON:
            # We only load skeleton if asked for it and thus only
            # signal completed node loading
            self._node_processing_timer.signal_update()
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
            # load_except and thus only
            # signal completed node loading
            self._node_processing_timer.signal_update()
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

        self._prm_load_into_dict(full_name=full_name,
                                 load_dict=load_dict,
                                 hdf5_group=_hdf5_group,
                                 instance=instance,
                                 load_only=load_only,
                                 load_except=load_except,
                                 load_flags=load_flags)

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

        # Signal completed node loading
        self._node_processing_timer.signal_update()

    def _prm_read_dictionary(self, leaf, full_name):
        """Loads data that was originally a dictionary when stored

        :param leaf:

            PyTables table containing the dictionary data

        :param full_name:

            Full name of the parameter or result whose data is to be loaded

        :return:

            Data to be loaded

        """
        try:
            # Load as Pbject Table
            temp_table = self._prm_read_table(leaf, full_name)
            # Turn the ObjectTable into a dictionary of lists (with length 1).
            temp_dict = temp_table.to_dict('list')

            innder_dict = {}

            # Turn the dictionary of lists into a normal dictionary
            for innerkey, vallist in temp_dict.items():
                innder_dict[innerkey] = vallist[0]

            return innder_dict
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (leaf._v_name, full_name))
            raise

    def _prm_read_shared_data(self, shared_node, instance):
        """Reads shared data and constructs the appropraite class.

        :param shared_node:

            hdf5 node storing the pandas DataFrame

        :param full_name:

            Full name of the parameter or result whose data is to be loaded

        :return:

            Data to load

        """
        try:
            data_type = self._all_get_from_attrs(shared_node,
                                                 HDF5StorageService.SHARED_DATA_TYPE)
            constructor = shared.FLAG_CLASS_MAPPING[data_type]
            name = shared_node._v_name
            result = constructor(name=name, parent=instance)
            return result
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (shared_node._v_name,
                                                                 instance.v_full_name))
            raise

    def _prm_read_pandas(self, pd_node, full_name):
        """Reads a DataFrame from dis.

        :param pd_node:

            hdf5 node storing the pandas DataFrame

        :param full_name:

            Full name of the parameter or result whose data is to be loaded

        :return:

            Data to load

        """
        try:
            name = pd_node._v_name
            pathname = pd_node._v_pathname
            pandas_store = self._hdf5store
            pandas_data = pandas_store.get(pathname)
            return pandas_data
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (pd_node._v_name, full_name))
            raise

    def _prm_read_table(self, table_or_group, full_name):
        """Reads a non-nested PyTables table column by column and created a new ObjectTable for
        the loaded data.

        :param table_or_group:

            PyTables table to read from or a group containing subtables.

        :param full_name:

            Full name of the parameter or result whose data is to be loaded

        :return:

            Data to be loaded

        """
        try:
            result_table = None

            if self._all_get_from_attrs(table_or_group, HDF5StorageService.SPLIT_TABLE):
                table_name = table_or_group._v_name

                data_type_table_name = table_name + '__' + HDF5StorageService.STORAGE_TYPE

                data_type_table = table_or_group._v_children[data_type_table_name]
                data_type_dict = {}


                for row in data_type_table:
                    fieldname = row['field_name'].decode('utf-8')
                    data_type_dict[fieldname] = row['data_type'].decode('utf-8')

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
                        if result_table is None:
                            result_table = ObjectTable(data={colname: data_list})
                        else:
                            result_table[colname] = data_list

            else:
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
                    if result_table is None:
                        result_table = ObjectTable(data={colname: data_list})
                    else:
                        result_table[colname] = data_list

            return result_table
        except:
            self._logger.error(
                'Failed loading `%s` of `%s`.' % (table_or_group._v_name, full_name))
            raise

    @staticmethod
    def _svrc_read_array(array):
        EMPTY_ARRAY_FIX_PT_2 = 'PTCOMPAT__empty__dtype'
        empty_array_val = 0
        none_type = 0
        res = array.read()
        try:
            if (res.shape == (1,) and res[0] == empty_array_val and
                        EMPTY_ARRAY_FIX_PT_2 in array._v_attrs):
                # If the array was stored with pytables 2 we end up here
                dtype = array._v_attrs[EMPTY_ARRAY_FIX_PT_2]
                if dtype == none_type:
                    res = np.array([])
                else:
                    res = np.array([], dtype=np.dtype(dtype))
        except (AttributeError, TypeError):
            pass  # has no size or getitem, we don't need to worry
        return res

    def _prm_read_array(self, array, full_name):
        """Reads data from an array or carray

        :param array:

            PyTables array or carray to read from

        :param full_name:

            Full name of the parameter or result whose data is to be loaded

        :return:

            Data to load

        """
        try:
            result = self._svrc_read_array(array)
            # Recall original data types
            result, dummy = self._all_recall_native_type(result, array,
                                                         HDF5StorageService.DATA_PREFIX)

            return result
        except:
            self._logger.error('Failed loading `%s` of `%s`.' % (array._v_name, full_name))
            raise

    def _hdf5_interact_with_data(self, path_to_data, item_name, request, args, kwargs):

        hdf5_group = self._all_get_node_by_name(path_to_data)

        if request == 'create_shared_data' or request == 'pandas_put':
            return self._shared_write_shared_data(key=item_name, hdf5_group=hdf5_group,
                                        full_name=path_to_data, **kwargs)

        hdf5data = hdf5_group._f_get_child(item_name)

        if request == 'make_shared':
            hdf5data = hdf5_group._f_get_child(item_name)
            flag = getattr(hdf5data._v_attrs, HDF5StorageService.STORAGE_TYPE)
            setattr(hdf5data._v_attrs, HDF5StorageService.SHARED_DATA_TYPE, flag)
            setattr(hdf5data._v_attrs, HDF5StorageService.STORAGE_TYPE,
                    HDF5StorageService.SHARED_DATA)
            return
        elif request == '__thenode__':
            return hdf5data
        elif request == 'pandas_get':
            pandas_data = self._prm_read_pandas(hdf5data, path_to_data)
            return pandas_data
        elif request == 'pandas_select':
            return self._prm_select_shared_pandas_data(hdf5data, path_to_data, **kwargs)
        elif request == 'make_ordinary':
            flag = getattr(hdf5data._v_attrs, HDF5StorageService.SHARED_DATA_TYPE)
            delattr(hdf5data._v_attrs, HDF5StorageService.SHARED_DATA_TYPE)
            setattr(hdf5data._v_attrs, HDF5StorageService.STORAGE_TYPE, flag)
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
