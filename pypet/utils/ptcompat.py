"""Module to allow support for PyTables 2 and 3"""

#pylint: skip-file

__author__ = 'Robert Meyer'


import tables as pt
import numpy as np


EMPTY_ARRAY_FIX_PT_2 = 'PTCOMPAT__empty__dtype'
empty_array_val = 0
none_type = 0
tables_version = int(pt.__version__[0])


def _make_pt2_carray(hdf5_file, *args, **kwargs):
    read_data = False
    if 'obj' in kwargs:
        data = kwargs.pop('obj')
        if data is not None:
            read_data = True
            atom = pt.Atom.from_dtype(data.dtype)
            if 'atom' not in kwargs:
                kwargs['atom']  = atom
            if 'shape' not in kwargs:
                kwargs['shape'] = data.shape
    carray = hdf5_file.createCArray(*args, **kwargs)
    if read_data:
        carray[:] = data[:]
    return carray


def _make_pt2_earray(hdf5_file, *args, **kwargs):
    read_data = False
    if 'obj' in kwargs:
        data = kwargs.pop('obj')
        if data is not None:
            read_data = True
            atom = pt.Atom.from_dtype(data.dtype)
            if 'atom' not in kwargs:
                kwargs['atom']  = atom
            if 'shape' not in kwargs:
                shape = list(data.shape)
                shape[0] = 0 # set first dimension to the one that can be enlarged
                shape = tuple(shape)
                kwargs['shape'] =  shape# add 0th dimension
    earray = hdf5_file.createEArray(*args, **kwargs)
    if read_data:
        earray.append(data)
    return earray


def _make_pt2_vlarray(hdf5_file, *args, **kwargs):
    if 'expectedrows' in kwargs:
        expectedrows=kwargs.pop('expectedrows') # this is termed expetedsizeinMB in python2.7
        kwargs['expectedsizeinMB'] = expectedrows
    read_data = False
    if 'obj' in kwargs:
        data = kwargs.pop('obj')
        if data is not None:
            read_data = True
            atom = pt.Atom.from_dtype(data.dtype)
            if 'atom' not in kwargs:
                kwargs['atom']  = atom
    vlarray = hdf5_file.createVLArray(*args, **kwargs)
    if read_data:
        vlarray.append(data)
    return vlarray


def _make_pt2_array(hdf5_file, *args, **kwargs):
    if 'obj' in kwargs:
        data = kwargs.pop('obj')
        kwargs['object'] = data
    is_empty = False
    if 'object' in kwargs:
        data = kwargs['object']
        try:
            if len(data) == 0:
                # We need the empty array fix for pytables 2
                kwargs['object'] = np.array([empty_array_val])
                is_empty = True
        except TypeError:
            pass # Does not support len operation, we're good
    array = hdf5_file.createArray(*args, **kwargs)
    if is_empty:
        # Remember dtype for pytables 2
        if type(data) is np.ndarray:
            setattr(array._v_attrs, EMPTY_ARRAY_FIX_PT_2, str(data.dtype))
        else:
            setattr(array._v_attrs, EMPTY_ARRAY_FIX_PT_2, none_type)
    return array


def _read_array(array):
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


if tables_version == 2:
    def open_file(*args, **kwargs): return pt.openFile(*args, **kwargs)

    def create_group(hdf5_file, *args, **kwargs): return hdf5_file.createGroup(*args, **kwargs)
    def get_node(hdf5_file, *args, **kwargs): return hdf5_file.getNode(*args, **kwargs)
    def list_nodes(hdf5_file, *args, **kwargs): return hdf5_file.listNodes(*args, **kwargs)
    def move_node(hdf5_file, *args, **kwargs): return hdf5_file.moveNode(*args, **kwargs)
    def remove_node(hdf5_file, *args, **kwargs): return hdf5_file.removeNode(*args, **kwargs)
    def copy_node(hdf5_file, *args, **kwargs): return hdf5_file.copyNode(*args, **kwargs)
    def create_table(hdf5_file, *args, **kwars): return hdf5_file.createTable(*args, **kwars)
    def create_array(hdf5_file, *args, **kwargs): return _make_pt2_array(hdf5_file, *args,
                                                                         **kwargs)
    def create_carray(hdf5_file, *args, **kwargs): return _make_pt2_carray(hdf5_file, *args,
                                                                        **kwargs)
    def create_earray(hdf5_file, *args, **kwargs): return _make_pt2_earray(hdf5_file, *args,
                                                                        **kwargs)
    def create_vlarray(hdf5_file, *args, **kwargs): return _make_pt2_vlarray(hdf5_file, *args,
                                                                        **kwargs)

    def read_array(array): return _read_array(array)

    def create_soft_link(hdf5_file, *args, **kwargs): return hdf5_file.createSoftLink(*args,
                                                                                      **kwargs)

    def get_child(hdf5_node, *args, **kwargs): return hdf5_node._f_getChild(*args, **kwargs)

    def remove_rows(table, *args, **kwargs): return table.removeRows(*args, **kwargs)

    def get_objectid(ptitem): return ptitem._v_objectID

    def iter_nodes( ptitem, *args, **kwargs): return ptitem._f_iterNodes(*args, **kwargs)

    def deleteattr(ptitem, attr): return ptitem._f_delAttr(attr)

    def walk_groups(ptitem): return ptitem._f_walkGroups()

    hdf5_version = pt.hdf5Version

elif tables_version == 3:
    def open_file(*args, **kwargs): return pt.open_file(*args, **kwargs)

    def create_group(hdf5_file, *args, **kwargs): return hdf5_file.create_group(*args, **kwargs)
    def get_node(hdf5_file, *args, **kwargs): return hdf5_file.get_node(*args, **kwargs)
    def list_nodes(hdf5_file, *args, **kwargs): return hdf5_file.list_nodes(*args, **kwargs)
    def move_node(hdf5_file, *args, **kwargs): return hdf5_file.move_node(*args, **kwargs)
    def remove_node(hdf5_file, *args, **kwargs): return hdf5_file.remove_node(*args, **kwargs)
    def copy_node(hdf5_file, *args, **kwargs): return hdf5_file.copy_node(*args, **kwargs)
    def create_table(hdf5_file, *args, **kwars): return hdf5_file.create_table(*args, **kwars)
    def create_array(hdf5_file, *args, **kwargs): return hdf5_file.create_array(*args, **kwargs)
    def create_carray(hdf5_file, *args, **kwargs): return hdf5_file.create_carray(*args, **kwargs)
    def create_earray(hdf5_file, *args, **kwargs): return hdf5_file.create_earray(*args, **kwargs)
    def create_vlarray(hdf5_file, *args, **kwargs): return hdf5_file.create_vlarray(*args,
                                                                                    **kwargs)

    def read_array(array): return _read_array(array)

    def create_soft_link(hdf5_file, *args, **kwargs): return hdf5_file.create_soft_link(*args,
                                                                                     **kwargs)
    def get_child(hdf5_node, *args, **kwargs): return hdf5_node._f_get_child(*args, **kwargs)

    def remove_rows(table, *args, **kwargs): return table.remove_rows(*args, **kwargs)

    def get_objectid(ptitem): return ptitem._v_objectid

    def iter_nodes( ptitem, *args, **kwargs): return ptitem._f_iter_nodes(*args, **kwargs)

    def deleteattr(ptitem, attr): return ptitem._f_delattr(attr)

    def walk_groups(ptitem): return ptitem._f_walk_groups()

    hdf5_version = pt.hdf5_version

else:
    raise RuntimeError('You shall not pass! Your PyTables version is weird!')

