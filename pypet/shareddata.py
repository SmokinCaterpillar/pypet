"""
New module allowing to share data across processes in a multiprocessing environment.

Already functional but not yet documented or thoroughly tested.

Use at your own risk!

"""

__author__ = 'Robert Meyer'

import warnings

import pandas as pd
import numpy as np

from pypet import pypetconstants
from pypet.parameter import BaseResult, Result, ObjectTable
import pypet.compat as compat
from pypet.naturalnaming import KnowsTrajectory
from pypet.pypetlogging import HasLogger
from pypet.utils.decorators import with_open_store


class StorageContextManager(HasLogger):
    def __init__(self, trajectory):
        self._traj = trajectory

    def __enter__(self):
        self.f_open_store()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.f_close_store()
        except Exception as e:
            self._logger.error('Could not close file because of `%s`' % str(e))
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


def make_ordinary_result(shared_result, new_data_name=None):
    """ Irreversible!"""
    if new_data_name is None:
        new_data_name = shared_result.v_name
    kwargs = dict(new_class_name=Result.__name__, new_data_name=new_data_name)
    shared_result._request_data('make_ordinary', kwargs=kwargs)
    del shared_result._traj
    del shared_result._data_name
    shared_result.__class__ = Result
    shared_result.__init__(shared_result.v_full_name, comment=shared_result.v_comment)
    return shared_result


def make_shared_result(ordinary_result, trajectory, new_class=None, old_data_name=None):
    data_dict = ordinary_result.f_to_dict(copy=False)
    if len(data_dict) > 1:
        raise TypeError('Cannot make the result shared, it manages more than one data item.')
    if old_data_name is None:
        old_data_name = compat.listkeys(data_dict)[0]
    if new_class is None:
        data = data_dict[old_data_name]
        if isinstance(data, ObjectTable):
            new_class = SharedTableResult
        elif isinstance(data, (pd.Series, pd.DataFrame, pd.Panel, pd.Panel4D)):
            new_class = SharedPandasDataResult
        elif isinstance(data, (tuple, list)):
            new_class = SharedArrayResult
        elif isinstance(data, (np.ndarray, np.matrix)):
            new_class = SharedCArrayResult
    ordinary_result.f_empty()
    old_class = ordinary_result.__class__
    try:
        ordinary_result.__class__ = new_class
        ordinary_result.__init__(ordinary_result.v_full_name, trajectory=trajectory,
                                 comment=ordinary_result.v_comment)
        ordinary_result._data_name = old_data_name
        kwargs = dict(new_class_name=new_class.__name__, new_data_name=ordinary_result.v_name)
        ordinary_result._request_data('make_shared', kwargs=kwargs)
        ordinary_result._data_name = ordinary_result.v_name
        return ordinary_result
    except Exception:
        ordinary_result.__class__ = old_class
        raise


class SharedDataResult(BaseResult, KnowsTrajectory):
    def __init__(self, full_name=None, trajectory=None, comment=''):
        super(SharedDataResult, self).__init__(full_name=full_name, comment=comment)
        self._traj=trajectory
        self._data_name = self.v_name
        self._set_logger()

    def f_create_shared_data(self, **kwargs):
        if not self._traj.f_contains(self, shortcuts=False):
            raise RuntimeError('Your trajectory must contain the shared result, otherwise '
                               'the shared data cannot be created.')
        if not self.v_stored:
            self._traj.f_store_item(self)
        return self._request_data('create_shared_data', kwargs=kwargs)

    def _store(self):
        return {}

    def _load(self, load_dict):
        pass

    def f_is_empty(self):
        return True # The shared data result is always empty because the data stays on disk

    def f_empty(self):
        pass

    def _request_data(self, request, args=None, kwargs=None):
        return self._storage_service.store(pypetconstants.ACCESS_DATA, self._full_name,
                                           self._data_name,
                                           request, args, kwargs,
                                           trajectory_name=self._traj.v_name)

    def f_get_data_node(self):
        if not self._storage_service.is_open:
            warnings.warn('You requesting the data item but your store is not open, '
                                 'the item itself will be closed, too!')
        return self._request_data('__thenode__')

    @property
    def _storage_service(self):
        return self._traj.v_storage_service

    def f_supports_fast_access(self):
        return False


class SharedArrayResult(SharedDataResult):

    FLAG = pypetconstants.ARRAY

    def f_create_shared_data(self, **kwargs):
        kwargs['flag'] = self.FLAG
        return super(SharedArrayResult, self).f_create_shared_data(**kwargs)

    @property
    def v_rowsize(self):
        return self._request_data('rowsize')

    @property
    def v_nrows(self):
        return self._request_data('nrows')

    @property
    def v_atom(self):
        return self._request_data('atom')

    def f_get_enum(self):
        return self._request_data('get_enum')

    def f_read(self, start=None, stop=None, step=None, out=None):
        kwargs = dict(start=start, stop=stop, step=step, out=out)
        return self._request_data('read', kwargs=kwargs)

    def __iter__(self):
        if self._storage_service.is_open:
            return self.f_iter_rows()
        else:
            return iter(self.f_read())

    def __getitem__(self, item):
        return self._request_data('__getitem__', args=(item,))

    def __setitem__(self, key, value):
        return self._request_data('__setitem__', args=(key, value))

    def __len__(self):
        return self.v_nrows

    @with_open_store
    def f_iter_rows(self, start=None, stop=None, step=None):
        return self._request_data('iterrows', kwargs=dict(start=start, stop=stop, step=step))

    @with_open_store
    def f_next(self):
        return self._request_data('next', args=())


class SharedCArrayResult(SharedArrayResult):

    FLAG = pypetconstants.CARRAY


class SharedEArrayResult(SharedArrayResult):

    FLAG = pypetconstants.EARRAY

    def f_append(self, sequence):
        return self._request_data('append', args=(sequence,))


class SharedVLArrayResult(SharedEArrayResult):

    FLAG = pypetconstants.VLARRAY


class SharedTableResult(SharedDataResult):

    def f_create_shared_data(self, **kwargs):
        kwargs['flag'] = pypetconstants.TABLE
        return super(SharedTableResult, self).f_create_shared_data(**kwargs)

    @property
    def v_coldescrs(self):
        return self._request_data('coldescrs')

    @property
    def v_coldtypes(self):
        return self._request_data('coldtypes')

    @property
    def v_colindexed(self):
        return self._request_data('colindexed')

    @property
    def v_colnames(self):
        return self._request_data('colnames')

    @property
    def v_colpathnames(self):
        return self._request_data('colpathnames')

    @property
    def v_coltypes(self):
        return self._request_data('coltypes')

    @property
    def v_description(self):
        return self._request_data('description')

    @property
    def v_indexed(self):
        return self._request_data('indexed')

    @property
    def v_extdim(self):
        return self._request_data('extdim')

    @property
    def v_nrows(self):
        return self._request_data('nrows')

    @property
    def v_rowsize(self):
        return self._request_data('rowsize')

    @property
    def v_autoindex(self):
        return self._request_data('autoindex')

    @v_autoindex.setter
    def v_autoindex(self, value):
        self._request_data('__setattr__', args=('autoindex', value))

    @property
    def v_indexedcolpathnames(self):
        return self._request_data('indexedcolpathnames')

    def f_col(self, name):
        return self._request_data('col', args=(name,))

    def f_read(self, start=None, stop=None, step=None, field=None, out=None):
        kwargs = dict(start=start, stop=stop, step=step, field=field, out=out)
        return self._request_data('read', kwargs=kwargs)

    def f_read_coordinates(self, coords, field=None):
        return self._request_data('read_coordinates', args=(coords,), kwargs=dict(filed=field))

    def f_read_sorted(self, sortby, checkCSI=False, field=None, start=None, stop=None, step=None):
        kwargs = dict(checkCSI=checkCSI, field=field, start=start, stop=stop, step=step)
        return self._request_data('read_sorted', args=(sortby,), kwargs=kwargs)

    def __iter__(self):
        if self._storage_service.is_open:
            return self._request_data('__iter__', args=())
        else:
            return iter(self.f_read())

    def __getitem__(self, key):
        return self._request_data('__getitem__', args=(key,))

    def __len__(self):
        return self.v_nrows

    def f_append(self, rows):
        return self._request_data('append', args=(rows,))

    # def f_append_row(self, row):
    #     return self.f_append([row])

    def f_modify_column(self, start=None, stop=None, step=None, column=None, colname=None):
        kwargs = dict(start=start, stop=stop, step=step, column=column, colname=colname)
        return self._request_data('modify_column', kwargs=kwargs)

    def f_modify_columns(self, start=None, stop=None, step=None, column=None, colname=None):
        kwargs = dict(start=start, stop=stop, step=step, column=column, colname=colname)
        return self._request_data('modify_columns', kwargs=kwargs)

    def f_modify_coordinates(self, coords, rows):
        self._request_data('modify_coordinates', args=(coords, rows))

    def f_modify_rows(self, start=None, stop=None, step=None, rows=None):
        kwargs = dict(start=start, stop=stop, step=step, rows=rows)
        self._request_data('modify_rows', kwargs=kwargs)

    def f_remove_rows(self, start=None, stop=None, step=None):
        kwargs = dict(start=start, stop=stop, step=step)
        self._request_data('remove_rows', kwargs=kwargs)

    def f_remove_row(self, n):
        self._request_data('remove_row', args=(n,))

    def __setitem__(self, key, value):
        return self._request_data('__setitem__', args=(key, value))

    def f_get_where_list(self, condition, condvars=None,
                         sort=False, start=None, stop=None, step=None):
        kwargs = dict(condvars=condvars, sort=sort, start=start, stop=stop, step=step)
        return self._request_data('get_where_list', args=(condition,), kwargs=kwargs)

    def f_read_where(self, condition, condvars=None, field=None,
                     start=None, stop=None, step=None):
        kwargs = dict(condvars=condvars, field=field, start=start, stop=stop, step=step)
        return self._request_data('read_where', args=(condition,), kwargs=kwargs)

    def f_will_query_use_indexing(self, condition, condvars=None):
        return self._request_data('will_query_use_indexing', args=(condition,),
                                  kwargs=dict(condvars=condvars))

    def f_get_enum(self, colname):
        return self._request_data('get_enum', args=(colname,))

    def f_reindex(self, colname=None):
        return self._request_data('reindex', kwargs=dict(colname=colname,
                                                         _col_func=colname is not None))

    def f_reindex_dirty(self, colname=None):
        return self._request_data('reindex_dirty',  kwargs=dict(colname=colname,
                                                                _col_func= colname is not None))

    def f_remove_index(self, colname):
        return self._request_data('remove_index', args=(colname,),
                                  kwargs=dict( _col_func=True))

    def f_create_index(self, colname, optlevel=6,
                       kind='medium', filters=None,
                       tmp_dir=None, _blocksizes=None,
                       _testmode=False, _verbose=False):
        kwargs = dict(optlevel=optlevel, kind=kind, filters=filters, tmp_dir=tmp_dir,
                      _blocksizes=_blocksizes, _testmode=_testmode, _verbose=_verbose,
                      _col_func=True, colname=colname)
        return self._request_data('create_index', kwargs=kwargs)

    def f_create_csindex(self, colname, filters=None, tmp_dir=None,
                         _blocksizes=None, _testmode=False, _verbose=False):
        kwargs = dict(filters=filters, tmp_dir=tmp_dir, _blocksizes=_blocksizes,
                      _testmode=_testmode, _verbose=_verbose,
                      _col_func=True, colname=colname)

        return self._request_data('create_csindex', kwargs=kwargs)

    @property
    @with_open_store
    def v_colindexes(self):
        return self._request_data('colindexes')

    @property
    @with_open_store
    def v_cols(self):
        return self._request_data('cols')

    @property
    @with_open_store
    def v_row(self):
        return self._request_data('row')

    @with_open_store
    def f_iter_rows(self, start=None, stop=None, step=None):
        return self._request_data('iterrows', kwargs=dict(start=start, stop=stop, step=step))

    @with_open_store
    def f_iter_sequence(self, sequence):
        return self._request_data('itersequence', args=(sequence,))

    @with_open_store
    def f_iter_sorted(self, sortby, checkCSI=False, start=None, stop=None, step=None):
        kwargs = dict(checkCSI=checkCSI, start=start, stop=stop, step=step)
        return self._request_data('itersorted', args=(sortby,), kwargs=kwargs)

    @with_open_store
    def f_where(self, condition, condvars=None, start=None, stop=None, step=None):
        kwargs = dict(condvars=condvars, start=start, stop=stop, step=step)
        return self._request_data('where', args=(condition,), kwargs=kwargs)

    @with_open_store
    def f_append_where(self, dstTable, condition, condvars=None, start=None, stop=None, step=None):
        kwargs = dict(condvars=condvars, start=start, stop=stop, step=step)
        return self._request_data('append_where', args=(dstTable, condition), kwargs=kwargs)

    @with_open_store
    def f_flush(self):
        return self._request_data('flush', args=())

    @with_open_store
    def flush_rows_to_index(self, _lastrow=True):
        return self._request_data('flush_rows_to_index', kwargs=dict(_lastrow=_lastrow))


class SharedPandasDataResult(SharedDataResult):

    def __init__(self, full_name=None, trajectory=None, comment=''):
        self._pandas_data = None
        super(SharedPandasDataResult, self).__init__(full_name=full_name,
                                                     trajectory=trajectory,
                                                     comment=comment,)

    def f_create_shared_data(self, data=None, format='table', **kwargs):
        if data is None:
            if not self.v_stored:
                self._traj.f_store_item(self)
        else:
            return super(SharedPandasDataResult, self).f_create_shared_data(data=data,
                                                                            format=format,
                                                                            **kwargs)

    def f_put(self, data=None, format='table', append=False, **kwargs):
        # data = self._extract_data(data)
        kwargs['format'] = format
        kwargs['append'] = append
        kwargs['data'] = data
        return self._request_data('pandas_put', kwargs=kwargs)

    def f_append(self, data=None, **kwargs):
        # data = self._extract_data(data)
        return self.f_put(data, format='table', append=True, **kwargs)

    def f_select(self, where=None, start = None, stop=None, columns=None,
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

    def f_read(self):
        return self._request_data('pandas_get', args=())
        # return self.data
