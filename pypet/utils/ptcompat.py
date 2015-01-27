"""Module to allow support for PyTables 2 and 3"""

__author__ = 'Robert Meyer'

import tables as pt

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
    return hdf5_file.createArray(*args, **kwargs)

if tables_version == 2:
    open_file = lambda *args, **kwargs: pt.openFile(*args, **kwargs)

    create_group = lambda hdf5_file, *args, **kwargs: hdf5_file.createGroup(*args, **kwargs)
    get_node = lambda hdf5_file, *args, **kwargs: hdf5_file.getNode(*args, **kwargs)
    list_nodes = lambda hdf5_file, *args, **kwargs: hdf5_file.listNodes(*args, **kwargs)
    move_node = lambda hdf5_file, *args, **kwargs: hdf5_file.moveNode(*args, **kwargs)
    remove_node = lambda hdf5_file, *args, **kwargs: hdf5_file.removeNode(*args, **kwargs)
    copy_node = lambda hdf5_file, *args, **kwargs: hdf5_file.copyNode(*args, **kwargs)
    create_table = lambda hdf5_file, *args, **kwars: hdf5_file.createTable(*args, **kwars)
    create_array = lambda hdf5_file, *args, **kwargs: _make_pt2_array(hdf5_file, *args, **kwargs)
    create_carray = lambda hdf5_file, *args, **kwargs: _make_pt2_carray(hdf5_file, *args,
                                                                        **kwargs)
    create_earray = lambda hdf5_file, *args, **kwargs: _make_pt2_earray(hdf5_file, *args,
                                                                        **kwargs)
    create_vlarray = lambda hdf5_file, *args, **kwargs: _make_pt2_vlarray(hdf5_file, *args,
                                                                        **kwargs)
    create_soft_link = lambda hdf5_file, *args, **kwargs: hdf5_file.createSoftLink(*args, **kwargs)

    get_child = lambda hdf5_node, *args, **kwargs: hdf5_node._f_getChild(*args, **kwargs)

    remove_rows = lambda table, *args, **kwargs: table.removeRows(*args, **kwargs)

    set_attribute = lambda ptitem, *args, **kwargs: ptitem._f_setAttr(*args, **kwargs)

    get_objectid = lambda ptitem: ptitem._v_objectID

    iter_nodes = lambda  ptitem, *args, **kwargs: ptitem._f_iterNodes(*args, **kwargs)

    deleteattr = lambda ptitem, attr: ptitem._f_delAttr(attr)

    walk_groups = lambda ptitem: ptitem._f_walkGroups()

    hdf5_version = pt.hdf5Version

elif tables_version == 3:
    open_file = lambda *args, **kwargs: pt.open_file(*args, **kwargs)

    create_group = lambda hdf5_file, *args, **kwargs: hdf5_file.create_group(*args, **kwargs)
    get_node = lambda hdf5_file, *args, **kwargs: hdf5_file.get_node(*args, **kwargs)
    list_nodes = lambda hdf5_file, *args, **kwargs: hdf5_file.list_nodes(*args, **kwargs)
    move_node = lambda hdf5_file, *args, **kwargs: hdf5_file.move_node(*args, **kwargs)
    remove_node = lambda hdf5_file, *args, **kwargs: hdf5_file.remove_node(*args, **kwargs)
    copy_node = lambda hdf5_file, *args, **kwargs: hdf5_file.copy_node(*args, **kwargs)
    create_table = lambda hdf5_file, *args, **kwars: hdf5_file.create_table(*args, **kwars)
    create_array = lambda hdf5_file, *args, **kwargs: hdf5_file.create_array(*args, **kwargs)
    create_carray = lambda hdf5_file, *args, **kwargs: hdf5_file.create_carray(*args, **kwargs)
    create_earray = lambda hdf5_file, *args, **kwargs: hdf5_file.create_earray(*args, **kwargs)
    create_vlarray = lambda hdf5_file, *args, **kwargs: hdf5_file.create_vlarray(*args, **kwargs)
    create_soft_link = lambda hdf5_file, *args, **kwargs: hdf5_file.create_soft_link(*args,
                                                                                     **kwargs)

    get_child = lambda hdf5_node, *args, **kwargs: hdf5_node._f_get_child(*args, **kwargs)

    remove_rows = lambda table, *args, **kwargs: table.remove_rows(*args, **kwargs)

    set_attribute = lambda ptitem, *args, **kwargs: ptitem._f_setattr(*args, **kwargs)

    get_objectid = lambda ptitem: ptitem._v_objectid

    iter_nodes = lambda  ptitem, *args, **kwargs: ptitem._f_iter_nodes(*args, **kwargs)

    deleteattr = lambda ptitem, attr: ptitem._f_delattr(attr)

    walk_groups = lambda ptitem: ptitem._f_walk_groups()

    hdf5_version = pt.hdf5_version

else:
    raise RuntimeError('You shall not pass! Your PyTables version is weird!')

