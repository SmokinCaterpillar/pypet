__author__ = 'Robert Meyer'

import numpy as np
import tables as pt
import os
import platform

from pypet.storagedata import StorageDataResult, StorageData, check_hdf5_init
from pypet import Trajectory, load_trajectory
from pypet.tests.test_helpers import make_temp_file, TrajectoryComparator, make_trajectory_name, make_run
from pypet import compact_hdf5_file
from pypet.utils import ptcompat
from pypet import compat
from pypet.pypetconstants import  CARRAY, EARRAY, VLARRAY, ARRAY, TABLE

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

class HDF5TrajectoryTests(TrajectoryComparator):

    def test_storing_and_manipulating(self):
        filename = make_temp_file('hdf5manipulation.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        thedata = np.zeros((1000,1000))
        myarray = StorageData(data=thedata)
        mytable = StorageData(description={'hi':pt.IntCol(), 'huhu':pt.StringCol(33)})
        mytable2 = StorageData(first_row={'ha': compat.tobytes('hi'), 'haha':np.zeros((3,3))})
        mytable3 = StorageData(first_row={'ha': compat.tobytes('hu'), 'haha':np.ones((3,3))})

        traj.f_add_result(StorageDataResult, 'myres1', myarray)
        traj.f_add_result(StorageDataResult, 'myres2', t1=mytable, t2=mytable2, t3=mytable3)

        with self.assertRaises(AttributeError):
            myarray.read()

        with self.assertRaises(AttributeError):
            for irun in mytable:
                pass

        traj.f_store()

        with traj.f_get('myres1').f_context():
            data = myarray.read()
            arr = myarray.v_item
            self.assertTrue(np.all(data == thedata))
            self.assertTrue(traj.v_storage_service.is_open)
            t3 = traj.myres2.t3
            for row in traj.myres2.t2:
                orow = t3.row
                for colname in t3.colnames:
                    orow[colname] = row[colname]
                orow.append()
            myarray[2,2] = 10
            data = myarray.read()
            traj.myres2.f_flush_store()


        self.assertTrue(myarray.v_item is None)
        self.assertTrue(mytable.v_item is None)
        self.assertTrue(data[2,2] == 10 )
        self.assertFalse(traj.v_storage_service.is_open)

        traj = load_trajectory(name=trajname, filename=filename)

        traj.f_load(load_all=2)

        self.assertTrue(traj.myres1.v_type == 'CARRAY')
        self.assertTrue(traj.myres2.t2.v_type == 'TABLE')
        traj.myres2.f_open_store()

        self.assertTrue(traj.myres2.t3.nrows == 2)
        self.assertTrue(traj.myres2.t3[0]['ha'] == compat.tobytes('hu'), traj.myres2.t3[0]['ha'])
        self.assertTrue(traj.myres2.t3[1]['ha'] == compat.tobytes('hi'), traj.myres2.t3[1]['ha'])
        self.assertTrue('huhu' in traj.myres2.t1.colnames)
        self.assertTrue(traj.myres1[2,2] == 10)
        self.assertTrue(traj.myres1)
        traj.myres2.f_close_store()

    @unittest.skipIf(platform.system() == 'Windows', 'Not supported under Windows')
    def test_compacting(self):
        filename = make_temp_file('hdf5compacting.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name
        traj.v_storage_service.complevel = 7

        first_row = {'ha': compat.tobytes('hi'), 'haha':np.zeros((3,3))}
        mytable = StorageData(first_row=first_row)

        traj.f_add_result(StorageDataResult, 'myres', mytable)


        traj.f_store()

        with traj.f_get('myres').f_context():
            tab = traj.myres.v_item
            for irun in range(10000):
                row = traj.myres.row
                for key in first_row:
                    row[key] = first_row[key]
                row.append()

        del traj
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        with traj.f_get('myres').f_context() as cm:
            tb = traj.myres
            ptcompat.remove_rows(tb, 1000, 10000)

            cm.f_flush_store()
            self.assertTrue(traj.myres.nrows == 1001)


        size =  os.path.getsize(filename)
        print('Filesize is %s' % str(size))
        name_wo_ext, ext = os.path.splitext(filename)
        backup_file_name = name_wo_ext + '_backup' + ext
        code = compact_hdf5_file(filename, keep_backup=True)
        if code != 0:
            raise RuntimeError('ptrepack fail')
        backup_size = os.path.getsize(backup_file_name)
        self.assertTrue(backup_size == size)
        new_size = os.path.getsize(filename)
        self.assertTrue(new_size < size, "%s > %s" %(str(new_size), str(size)))

    def test_all_arrays(self):
        filename = make_temp_file('hdf5arrays.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        npearray = np.ones((2,10,3), dtype=np.float)
        thevlarray = np.array([compat.tobytes('j'), 22.2, compat.tobytes('gutter')])
        carray = StorageData(item_type=CARRAY, shape=(10, 10), atom=pt.atom.FloatAtom())
        earray = StorageData(item_type=EARRAY, obj=npearray)
        vlarray = StorageData(item_type=VLARRAY, object=thevlarray)
        array = StorageData(item_type=ARRAY, data=npearray)

        traj.v_standard_result = StorageDataResult
        traj.f_add_result('g.arrays', carray=carray, earray=earray, vlarray=vlarray, array=array,
                          comment='the arrays')

        traj.f_store()

        traj = load_trajectory(name=trajname, filename=filename, load_all=2)

        toappned = [44, compat.tobytes('k')]
        arrays = traj.arrays
        with arrays.f_context() as cm:
            a1 = arrays.array
            a1[0,0,0] = 4.0

            a2 = arrays.carray
            a2[0,1] = 4

            a4 = arrays.vlarray
            a4.append(toappned)


            a3 = arrays.earray
            a3.append(np.zeros((1,10,3)))

            #cm.f_flush_storage()

        traj = load_trajectory(name=trajname, filename=filename, load_all=2)

        arrays = traj.arrays
        with arrays.f_context() as cm:
            a1 = arrays.array
            self.assertTrue(a1[0,0,0] == 4.0)

            a2 = arrays.carray
            self.assertTrue(a2[0,1] == 4)

            a3 = arrays.earray
            self.assertTrue(a3.read().shape == (3,10,3))

            a4 = arrays.vlarray
            for idx, x in enumerate(a4):
                if idx == 0:
                    self.assertTrue(np.all(x == np.array(thevlarray)))
                elif idx == 1:
                    self.assertTrue(np.all(x == np.array(toappned)))
                else:
                    raise RuntimeError()

    def test_errors(self):
        filename = make_temp_file('hdf5errors.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        npearray = np.ones((2,10,3), dtype=np.float)
        thevlarray = np.array([compat.tobytes('j'), 22.2, compat.tobytes('gutter')])
        carray = StorageData(item_type=CARRAY, shape=(10, 10), atom=pt.atom.FloatAtom())
        earray = StorageData(item_type=EARRAY, obj=npearray)
        vlarray = StorageData(item_type=VLARRAY)
        array = StorageData(item_type=ARRAY, data=npearray)

        traj.v_standard_result = StorageDataResult
        traj.f_add_result('g.arrays', carray=carray, earray=earray, vlarray=vlarray, array=array,
                          comment='the arrays')

        with self.assertRaises(Exception):
            traj.f_store()

        with self.assertRaises(Exception):
            check_hdf5_init(vlarray)

        traj.arrays['vlarray'] = StorageData(item_type=VLARRAY, obj=thevlarray)

        self.assertTrue(check_hdf5_init(traj.arrays['vlarray']))

        traj.f_store()

        self.assertTrue(traj.arrays.vlarray.v_item is None)

        with self.assertRaises(AttributeError):
            traj.arrays.array[0]

        with self.assertRaises(RuntimeError):
            traj.arrays.f_close_store()

        with self.assertRaises(RuntimeError):
            traj.arrays.f_flush_store()

        with traj.arrays.f_context() as cm:
            with self.assertRaises(RuntimeError):
                with traj.arrays.f_context() as cm2:
                    pass
            traj.arrays.array.v_item
            traj.arrays.array.f_free_item()
            self.assertFalse(traj.arrays.array.v_uses_store)
            self.assertTrue(traj.arrays.array._item is None)
            traj.arrays.array.v_item
            self.assertTrue(traj.arrays.array.v_uses_store)
            self.assertTrue(traj.arrays.array._item is not None)
            self.assertTrue(traj.v_storage_service.is_open)
            with self.assertRaises(RuntimeError):
                traj.arrays.f_open_store()

        with self.assertRaises(RuntimeError):
            with traj.arrays.f_context() as cm2:
                self.assertTrue(True) # this should still be executed
                traj.arrays.f_close_store()

        self.assertFalse(traj.v_storage_service.is_open)

        with self.assertRaises(Exception):
            check_hdf5_init(StorageData(item_type=TABLE))



