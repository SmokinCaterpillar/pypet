__author__ = 'robert'

import os

from pypet import pypetconstants
from pypet.parameter import Result
import pypet.compat as compat
import pypet.utils.ptcompat as ptcompat
import pypet.pypetconstants as pypetconstants
import warnings
from pypet.naturalnaming import NNLeafNode
from pypet.pypetlogging import HasLogger

def check_hdf5_init(storage_data):
    file_created = False
    item_created = False
    filename = '__tmp__.hdf5'
    try:
        with ptcompat.open_file(filename, mode='a') as file:
            file_created = True
            factory_dict = {pypetconstants.TABLE: ptcompat.create_table,
                            pypetconstants.CARRAY: ptcompat.create_carray,
                            pypetconstants.EARRAY: ptcompat.create_earray,
                            pypetconstants.VLARRAY: ptcompat.create_vlarray}
            factory = factory_dict[storage_data._type]
            kwargs = storage_data._kwargs
            factory(file, where='/', name='__test__', **kwargs)
        item_created = True
    finally:
        if file_created:
            os.remove(filename)
    return item_created

class StorageData(object):
    def __init__(self, **kwargs):
        self._traj = None
        self._path_to_data = None
        self._item_name = None
        self.f_set_init_args(**kwargs)

    def f_set_init_args(self, **kwargs):
        self._kwargs = kwargs

    def __getstate__(self):
        """Called for pickling.

        Removes the keyword arguments and the item in case it is till
        bundled with the storage.

        """
        statedict = self.__dict__.copy()
        statedict['_kwargs'] = {}
        statedict['_traj'] = None
        return statedict

    def _set_dependencies(self, trajectory, full_name, data_name):
        self._traj = trajectory
        self._path_to_data = full_name
        self._item_name = data_name

    def _request_data(self, request, args=None, kwargs=None):
        service = self._traj.v_storage_service
        return service.store(pypetconstants.STORAGE_DATA, self._path_to_data, self._item_name,
                                       request, args, kwargs,
                                       trajectory_name=self._traj.v_name)

    def f_get_store_item(self):
        service = self._traj.v_storage_service
        if not service.is_open:
            warnings.warn('You requesting the data item but your store is not open, '
                                 'the item itself will be closed, too!')
        return self._request_data('__theitem__')

class ArrayData(StorageData):
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
        return iter(self.f_read())

    def __getitem__(self, item):
        return self._request_data('__getitem__', args=(item,))

    def __setitem__(self, key, value):
        return self._request_data('__setitem__', args=(key, value))

    def __len__(self):
        return self.v_nrows


class CArrayData(ArrayData):
    pass


class EArrayData(ArrayData):
    def f_append(self, sequence):
        return self._request_data('append', args=(sequence,))


class VLArrayData(EArrayData):
    pass


class TableData(StorageData):
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
        return self._request_data('__setattr__', args=('autoindex', value))

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
        return iter(self.f_read())

    def __getitem__(self, key):
        return self._request_data('__getitem__', args=(key,))

    def __len__(self):
        return self.v_nrows

    def f_append(self, rows):
        return self._request_data('append', args=(rows,))

    def f_append_row(self, row):
        return self.f_append([row])

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

    def flush_rows_to_index(self, _lastrow=True):
        return self._request_data('flush_rows_to_index', kwargs=dict(_lastrow=_lastrow))

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

    def f_flush(self):
        return self._request_data('flush', args=())



class StorageContextManager(HasLogger):
    def __init__(self, trajectory):
        self._traj = trajectory

    def __enter__(self):
        self.f_open_store()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        try:
            self.f_close_store()
        except Exception as e:
            self._logger.error('Could not close file because of `%s`' % str(e))
            if exception_type is None:
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


class KnowsTrajectory(NNLeafNode):
    KNOWS_TRAJECTORY = True


class StorageDataResult(Result, KnowsTrajectory):
    def __init__(self, full_name, trajectory, *args, **kwargs):
        self._traj = trajectory
        super(StorageDataResult, self).__init__(full_name, *args, **kwargs)

    def __setstate__(self, statedict):
        """Called after loading a pickle dump.

        """
        super(StorageDataResult, self).__setstate__(statedict)
        self._set_dependencies()

    def _supports(self, data):
        if isinstance(data, StorageData):
            return True
        else:
            return super(StorageDataResult, self)._supports(data)

    def f_set_single(self, name, item):
        if isinstance(item, StorageData):
            item._set_dependencies(self._traj, self.v_full_name, name)

            if self.v_stored:
                self._logger.warning('You are changing an already stored result. If '
                                 'you not explicitly overwrite the data on disk, this change '
                                 'might be lost and not propagated to disk.')

            self._data[name] = item
        else:
            super(StorageDataResult, self).f_set_single(name, item)

    def _set_dependencies(self):
        for name in self._data:
            item = self._data[name]
            try:
                item._set_dependencies(self._traj, self.v_full_name, name)
            except AttributeError:
                pass

    def _load(self, load_dict):
        super(StorageDataResult, self)._load(load_dict)
        self._set_dependencies()

