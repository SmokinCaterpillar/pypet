__author__ = 'Robert Meyer'

import numpy as np
import tables as pt
import os

from pypet.storagedata import StorageDataResult, StorageData
from pypet import Trajectory, load_trajectory
from pypet.tests.test_helpers import make_temp_file, TrajectoryComparator, make_trajectory_name, make_run
from pypet import compact_hdf5_file

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
        mytable2 = StorageData(first_row={'ha': 'hi', 'haha':np.zeros((3,3))})
        mytable3 = StorageData(first_row={'ha': 'hu', 'haha':np.ones((3,3))})

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
            arr = myarray.v_data_item
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
            traj.myres2.f_flush_storage()


        self.assertTrue(myarray.v_data_item is None)
        self.assertTrue(mytable.v_data_item is None)
        self.assertTrue(data[2,2] == 10 )
        self.assertFalse(traj.v_storage_service.is_open)

        traj = load_trajectory(name=trajname, filename=filename)

        traj.f_load(load_all=2)

        self.assertTrue(traj.myres1.v_data_type == 'CARRAY')
        self.assertTrue(traj.myres2.t2.v_data_type == 'TABLE')
        traj.myres2.f_open_storage()

        self.assertTrue(traj.myres2.t3.nrows == 2)
        self.assertTrue(traj.myres2.t3[0]['ha'] == 'hu', traj.myres2.t3[0]['ha'])
        self.assertTrue(traj.myres2.t3[1]['ha'] == 'hi', traj.myres2.t3[1]['ha'])
        self.assertTrue('huhu' in traj.myres2.t1.colnames)
        self.assertTrue(traj.myres1[2,2] == 10)
        self.assertTrue(traj.myres1)
        traj.myres2.f_close_storage()

    def test_compacting(self):
        filename = make_temp_file('hdf5compacting.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name
        traj.v_storage_service.complevel = 7

        first_row = {'ha': 'hi', 'haha':np.zeros((3,3))}
        mytable = StorageData(first_row=first_row)

        traj.f_add_result(StorageDataResult, 'myres', mytable)


        traj.f_store()

        with traj.f_get('myres').f_context():
            tab = traj.myres.v_data_item
            for irun in range(10000):
                row = traj.myres.row
                for key in first_row:
                    row[key] = first_row[key]
                row.append()

        del traj
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        with traj.f_get('myres').f_context() as cm:
            tb = traj.myres
            tb.remove_rows(1000, 10000, 1)

            cm.f_flush_storage()
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



