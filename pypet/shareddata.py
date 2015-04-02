"""
New module allowing to share data across processes in a multiprocessing environment.

Already functional but not yet documented or thoroughly tested.

Use at your own risk!

"""

__author__ = 'Robert Meyer'

import warnings

import pandas as pd
import numpy as np

import pypet.pypetconstants as pypetconstants
from pypet.pypetlogging import HasLogger
from pypet.utils.decorators import with_open_store
from pypet.parameter import ObjectTable, Result
from pypet.naturalnaming import KnowsTrajectory


class StorageContextManager(HasLogger):
    def __init__(self, trajectory):
        self._traj = trajectory

    def __enter__(self):
        self.f_open_store()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.f_close_store()
        except Exception as exc:
            self._logger.error('Could not close file because of `%s`' % repr(exc))
            if exc_type is None:
                raise
            else:
                return False

    def f_close_store(self):
        service = self._traj.v_storage_service
        if not service.is_open:
            raise RuntimeError('The storage service is not open, '
                               'please open via `f_open_storage`.')
        service.store(pypetconstants.CLOSE_FILE, None)

    def f_open_store(self):
        service = self._traj.v_storage_service
        if service.is_open:
            raise RuntimeError('Your service is already open, there is no need to re-open it.')
        service.store(pypetconstants.OPEN_FILE, None,
                      trajectory_name=self._traj.v_name)

    def f_flush_store(self):
        service = self._traj.v_storage_service
        if not service.is_open:
            raise RuntimeError('The storage service is not open, '
                               'please open via `f_open_storage`.')
        service.store(pypetconstants.FLUSH, None)


def make_ordinary_result(result, key, trajectory=None, reload=True):
    """Turns a given shared result into a an ordinary one.

    :return: The `result`

    """
    shared_data = result.f_get(key)
    if trajectory is not None:
        shared_data.traj = trajectory
    shared_data._request_data('make_ordinary')
    result.f_remove(key)
    if reload:
        trajectory.f_load_item(result, load_data=pypetconstants.OVERWRITE_DATA)
    return result


def make_shared_result(result, key, trajectory, new_class=None):
    """Turns an ordinary result into a shared one.

    Removes the old result from the trajectory and replaces it.
    Empties the given result.

    :return: The `result`

    """
    data = result.f_get(key)
    if new_class is None:
        if isinstance(data, ObjectTable):
            new_class = SharedTable
        elif isinstance(data, pd.DataFrame):
            new_class = SharedPandasFrame
        elif isinstance(data, (tuple, list)):
            new_class = SharedArray
        elif isinstance(data, (np.ndarray, np.matrix)):
            new_class = SharedCArray
        else:
            raise RuntimeError('Your data `%s` is not understood.' % key)
    shared_data = new_class(result.f_translate_key(key), result, trajectory=trajectory)
    shared_data._request_data('make_shared')
    result[key] = shared_data
    return result


class SharedData(HasLogger):

    FLAG = None

    def __init__(self, name=None, parent=None, trajectory=None, add_to_parent=False):
        self._set_logger()
        self.name = name
        self.parent = parent
        self.traj = trajectory
        if add_to_parent:
            self.parent[name] = self

    def _check_state(self):
        if self.traj is None:
            raise TypeError('Please pass the trajectory to the shared data, via'
                            '`shared_data.traj = trajectory`, otherwise you cannot '
                            'access the data.')
        if self.parent is None:
            raise TypeError('Please pass the parent to the shared data, via'
                            '`shared_data.parent = parent`, otherwise you cannot '
                            'access the data.')
        if self.name is None:
            raise TypeError('Please pass the name of the shared data, via'
                            '`shared_data.name = name`, otherwise you cannot '
                            'access the data.')
    def _store_parent(self):
        self._check_state()
        if not self.parent._stored:
            self.traj.f_store_item(self.parent)

    def create_shared_data(self, **kwargs):
        if 'flag' not in kwargs:
            kwargs['flag'] = self.FLAG
        if 'data' in kwargs:
            kwargs['obj'] = kwargs.pop('data')
        if 'trajectory' in kwargs:
            self.traj = kwargs.pop('trajectory')
        if 'traj' in kwargs:
            self.traj = kwargs.pop('traj')
        if 'name' in kwargs:
            self.name = kwargs.pop['name']
        if 'parent' in kwargs:
            self.parent = kwargs.pop('parent')
            if self.name is not None:
                self.parent[self.name] = self
        return self._request_data('create_shared_data', kwargs=kwargs)

    def _request_data(self, request, args=None, kwargs=None):
        return self._storage_service.store(pypetconstants.ACCESS_DATA, self.parent.v_full_name,
                                           self.name,
                                           request, args, kwargs,
                                           trajectory_name=self.traj.v_name)

    def get_data_node(self):
        if not self._storage_service.is_open:
            warnings.warn('You requesting the data item but your store is not open, '
                                 'the item itself will be closed, too!')
        return self._request_data('__thenode__')

    @property
    def _storage_service(self):
        self._store_parent()
        return self.traj.v_storage_service


class SharedArray(SharedData):

    FLAG = pypetconstants.ARRAY

    @property
    def rowsize(self):
        return self._request_data('rowsize')

    @property
    def nrows(self):
        return self._request_data('nrows')

    @property
    def atom(self):
        return self._request_data('atom')

    def get_enum(self):
        return self._request_data('get_enum')

    def read(self, start=None, stop=None, step=None, out=None):
        kwargs = dict(start=start, stop=stop, step=step, out=out)
        return self._request_data('read', kwargs=kwargs)

    def __iter__(self):
        if self._storage_service.is_open:
            return self.iter_rows()
        else:
            return iter(self.read())

    def __getitem__(self, item):
        return self._request_data('__getitem__', args=(item,))

    def __setitem__(self, key, value):
        return self._request_data('__setitem__', args=(key, value))

    def __len__(self):
        return self.nrows

    @with_open_store
    def iter_rows(self, start=None, stop=None, step=None):
        return self._request_data('iterrows', kwargs=dict(start=start, stop=stop, step=step))

    @with_open_store
    def next(self):
        return self._request_data('next', args=())


class SharedCArray(SharedArray):

    FLAG = pypetconstants.CARRAY


class SharedEArray(SharedArray):

    FLAG = pypetconstants.EARRAY

    def append(self, sequence):
        return self._request_data('append', args=(sequence,))


class SharedVLArray(SharedEArray):

    FLAG = pypetconstants.VLARRAY


class SharedTable(SharedData):

    FLAG = pypetconstants.TABLE

    @property
    def coldescrs(self):
        return self._request_data('coldescrs')

    @property
    def coldtypes(self):
        return self._request_data('coldtypes')

    @property
    def colindexed(self):
        return self._request_data('colindexed')

    @property
    def colnames(self):
        return self._request_data('colnames')

    @property
    def colpathnames(self):
        return self._request_data('colpathnames')

    @property
    def coltypes(self):
        return self._request_data('coltypes')

    @property
    def description(self):
        return self._request_data('description')

    @property
    def indexed(self):
        return self._request_data('indexed')

    @property
    def extdim(self):
        return self._request_data('extdim')

    @property
    def nrows(self):
        return self._request_data('nrows')

    @property
    def rowsize(self):
        return self._request_data('rowsize')

    @property
    def autoindex(self):
        return self._request_data('autoindex')

    @autoindex.setter
    def autoindex(self, value):
        self._request_data('__setattr__', args=('autoindex', value))

    @property
    def indexedcolpathnames(self):
        return self._request_data('indexedcolpathnames')

    def col(self, name):
        return self._request_data('col', args=(name,))

    def read(self, start=None, stop=None, step=None, field=None, out=None):
        kwargs = dict(start=start, stop=stop, step=step, field=field, out=out)
        return self._request_data('read', kwargs=kwargs)

    def read_coordinates(self, coords, field=None):
        return self._request_data('read_coordinates', args=(coords,), kwargs=dict(filed=field))

    def read_sorted(self, sortby, checkCSI=False, field=None, start=None, stop=None, step=None):
        kwargs = dict(checkCSI=checkCSI, field=field, start=start, stop=stop, step=step)
        return self._request_data('read_sorted', args=(sortby,), kwargs=kwargs)

    def __iter__(self):
        if self._storage_service.is_open:
            return self._request_data('__iter__', args=())
        else:
            return iter(self.read())

    def __getitem__(self, key):
        return self._request_data('__getitem__', args=(key,))

    def __len__(self):
        return self.nrows

    def append(self, rows):
        return self._request_data('append', args=(rows,))

    # def append_row(self, row):
    #     return self.append([row])

    def modify_column(self, start=None, stop=None, step=None, column=None, colname=None):
        kwargs = dict(start=start, stop=stop, step=step, column=column, colname=colname)
        return self._request_data('modify_column', kwargs=kwargs)

    def modify_columns(self, start=None, stop=None, step=None, column=None, colname=None):
        kwargs = dict(start=start, stop=stop, step=step, column=column, colname=colname)
        return self._request_data('modify_columns', kwargs=kwargs)

    def modify_coordinates(self, coords, rows):
        self._request_data('modify_coordinates', args=(coords, rows))

    def modify_rows(self, start=None, stop=None, step=None, rows=None):
        kwargs = dict(start=start, stop=stop, step=step, rows=rows)
        self._request_data('modify_rows', kwargs=kwargs)

    def remove_rows(self, start=None, stop=None, step=None):
        kwargs = dict(start=start, stop=stop, step=step)
        self._request_data('remove_rows', kwargs=kwargs)

    def remove_row(self, n):
        self._request_data('remove_row', args=(n,))

    def __setitem__(self, key, value):
        return self._request_data('__setitem__', args=(key, value))

    def get_where_list(self, condition, condvars=None,
                         sort=False, start=None, stop=None, step=None):
        kwargs = dict(condvars=condvars, sort=sort, start=start, stop=stop, step=step)
        return self._request_data('get_where_list', args=(condition,), kwargs=kwargs)

    def read_where(self, condition, condvars=None, field=None,
                     start=None, stop=None, step=None):
        kwargs = dict(condvars=condvars, field=field, start=start, stop=stop, step=step)
        return self._request_data('read_where', args=(condition,), kwargs=kwargs)

    def will_query_use_indexing(self, condition, condvars=None):
        return self._request_data('will_query_use_indexing', args=(condition,),
                                  kwargs=dict(condvars=condvars))

    def get_enum(self, colname):
        return self._request_data('get_enum', args=(colname,))

    def reindex(self, colname=None):
        return self._request_data('reindex', kwargs=dict(colname=colname,
                                                         _col_func=colname is not None))

    def reindex_dirty(self, colname=None):
        return self._request_data('reindex_dirty', kwargs=dict(colname=colname,
                                                                _col_func=colname is not None))

    def remove_index(self, colname):
        return self._request_data('remove_index', args=(colname,),
                                  kwargs=dict(_col_func=True))

    def create_index(self, colname, optlevel=6,
                       kind='medium', filters=None,
                       tmp_dir=None, _blocksizes=None,
                       _testmode=False, _verbose=False):
        kwargs = dict(optlevel=optlevel, kind=kind, filters=filters, tmp_dir=tmp_dir,
                      _blocksizes=_blocksizes, _testmode=_testmode, _verbose=_verbose,
                      _col_func=True, colname=colname)
        return self._request_data('create_index', kwargs=kwargs)

    def create_csindex(self, colname, filters=None, tmp_dir=None,
                         _blocksizes=None, _testmode=False, _verbose=False):
        kwargs = dict(filters=filters, tmp_dir=tmp_dir, _blocksizes=_blocksizes,
                      _testmode=_testmode, _verbose=_verbose,
                      _col_func=True, colname=colname)

        return self._request_data('create_csindex', kwargs=kwargs)

    @property
    @with_open_store
    def colindexes(self):
        return self._request_data('colindexes')

    @property
    @with_open_store
    def cols(self):
        return self._request_data('cols')

    @property
    @with_open_store
    def row(self):
        return self._request_data('row')

    @with_open_store
    def iter_rows(self, start=None, stop=None, step=None):
        return self._request_data('iterrows', kwargs=dict(start=start, stop=stop, step=step))

    @with_open_store
    def iter_sequence(self, sequence):
        return self._request_data('itersequence', args=(sequence,))

    @with_open_store
    def iter_sorted(self, sortby, checkCSI=False, start=None, stop=None, step=None):
        kwargs = dict(checkCSI=checkCSI, start=start, stop=stop, step=step)
        return self._request_data('itersorted', args=(sortby,), kwargs=kwargs)

    @with_open_store
    def where(self, condition, condvars=None, start=None, stop=None, step=None):
        kwargs = dict(condvars=condvars, start=start, stop=stop, step=step)
        return self._request_data('where', args=(condition,), kwargs=kwargs)

    @with_open_store
    def append_where(self, dstTable, condition, condvars=None, start=None, stop=None, step=None):
        kwargs = dict(condvars=condvars, start=start, stop=stop, step=step)
        return self._request_data('append_where', args=(dstTable, condition), kwargs=kwargs)

    @with_open_store
    def flush(self):
        return self._request_data('flush', args=())

    @with_open_store
    def flush_rows_to_index(self, _lastrow=True):
        return self._request_data('flush_rows_to_index', kwargs=dict(_lastrow=_lastrow))


class SharedPandasFrame(SharedData):

    FLAG = pypetconstants.FRAME

    def create_shared_data(self, **kwargs):
        if 'format' not in kwargs:
            kwargs['format'] = 'table'
        return super(SharedPandasFrame, self).create_shared_data(**kwargs)

    def put(self, data=None, format='table', append=False, **kwargs):
        # data = self._extract_data(data)
        kwargs['format'] = format
        kwargs['append'] = append
        kwargs['obj'] = data
        return self._request_data('pandas_put', kwargs=kwargs)

    def append(self, data=None, **kwargs):
        # data = self._extract_data(data)
        return self.put(data, format='table', append=True, **kwargs)

    def select(self, where=None, start = None, stop=None, columns=None,
               chunksize=None, **kwargs):
        kwargs['where'] = where,
        kwargs['start'] = start
        kwargs['stop'] = stop
        kwargs['columns'] = columns
        kwargs['chunksize'] = chunksize
        if not self._storage_service.is_open:
            kwargs['iterator'] = False
        return self._request_data('pandas_select', kwargs=kwargs)
        # return self.data

    def read(self):
        return self._request_data('pandas_get', args=())
        # return self.data


FLAG_CLASS_MAPPING = {
    pypetconstants.ARRAY: SharedArray,
    pypetconstants.CARRAY: SharedCArray,
    pypetconstants.EARRAY: SharedEArray,
    pypetconstants.VLARRAY: SharedVLArray,
    pypetconstants.TABLE: SharedTable,
    pypetconstants.FRAME: SharedPandasFrame,
}


class SharedResult(Result, KnowsTrajectory):
    """Behaves exactly like the normal `Result` but accepts `SharedData` subclasses as data."""

    __slots__ = ('_traj',)

    SUPPORTED_DATA = set(FLAG_CLASS_MAPPING.values())

    def __init__(self, full_name, trajectory, *args, **kwargs):
        self._traj = trajectory
        super(SharedResult, self).__init__(full_name, *args, **kwargs)

    @property
    def traj(self):
        return self._traj

    def _supports(self, item):
        """Checks if outer data structure is supported."""
        result = super(SharedResult, self)._supports(item)
        result = result or type(item) in SharedResult.SUPPORTED_DATA
        return result

    def _pass_to_shared(self, name, item):
        try:
            item.traj = self.traj
            item.name = name
            item.parent = self
        except AttributeError:
            pass

    def f_set_single(self, name, item):
        super(SharedResult, self).f_set_single(name, item)
        self._pass_to_shared(name, item)

    def _load(self, load_dict):
        super(SharedResult, self)._load(load_dict)
        for key in self:
            item = self[key]
            self._pass_to_shared(key, item)

    def create_shared_data(self, name=None, **kwargs):
        if name is None:
            item = self.f_get()
        else:
            item = self.f_get(name)
        return item.create_shared_data(**kwargs)
