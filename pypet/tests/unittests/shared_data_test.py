__author__ = 'Robert Meyer'

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import os
import platform
import logging
import numpy as np
import pandas as pd
import tables as pt
from pypet import Trajectory, SharedArrayResult, SharedTableResult, SharedPandasDataResult, \
    ObjectTable, compat, StorageContextManager, load_trajectory, make_ordinary_result, Result, \
    make_shared_result, compact_hdf5_file, SharedCArrayResult, SharedEArrayResult, \
    SharedVLArrayResult
from pypet.tests.testutils.data import TrajectoryComparator
from pypet.tests.testutils.ioutils import make_temp_dir, make_trajectory_name, get_root_logger, \
    parse_args, run_suite
from pypet.utils import ptcompat


@unittest.skipIf(ptcompat.tables_version < 3, 'Only supported for PyTables 3 and newer')
class StorageDataTrajectoryTests(TrajectoryComparator):

    tags = 'unittest', 'trajectory', 'shared', 'hdf5'

    def test_converions(self):
        filename = make_temp_dir('hdf5manipulation.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        traj.f_store(only_init=True)

        thedata = np.zeros((1000,1000))
        myarray = SharedArrayResult('array', trajectory=traj)
        mytable = SharedTableResult('t1', trajectory=traj)
        # mytable2 = SharedTableResult('h.t2', trajectory=traj)
        # mytable3 = SharedTableResult('jjj.t3', trajectory=traj)
        dadict = {'hi': [ 1,2,3,4,5], 'shu':['bi', 'du', 'da', 'ha', 'hui']}
        dadict2 = {'answer': [42]}
        traj.f_add_result(SharedPandasDataResult, 'dfs.df').f_create_shared_data(pd.DataFrame(dadict))
        traj.f_add_result(SharedPandasDataResult, 'dfs.df1').f_create_shared_data(data=pd.DataFrame(dadict2))

        traj.f_add_result('mylist', [1,2,3])
        traj.f_add_result('my.mytuple', k=(1,2,3), wa=42)
        traj.f_add_result('my.myarray', np.zeros((50,50)))
        traj.f_add_result('my.myframe', data=pd.DataFrame(dadict2))
        traj.f_add_result('my.mytable', ObjectTable(data=dadict2))


        traj.f_add_result(myarray)
        myarray.f_create_shared_data(data=thedata)
        traj.f_add_result(mytable)
        mytable.f_create_shared_data(first_row={'hi':compat.tobytes('hi'), 'huhu':np.ones(3)})

        traj.f_store()


        data = myarray.f_read()
        arr = myarray.f_get_data_node()
        self.assertTrue(np.all(data == thedata))

        with StorageContextManager(traj) as cm:
            myarray[2,2] = 10
            data = myarray.f_read()
            self.assertTrue(data[2,2] == 10)

        self.assertTrue(data[2,2] == 10 )
        self.assertFalse(traj.v_storage_service.is_open)

        traj = load_trajectory(name=trajname, filename=filename, load_all=2)

        array = traj.array

        array = make_ordinary_result(array, trajectory=traj, new_data_name='super')
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        array = traj.array
        self.assertTrue(isinstance(array, Result))#
        thedata[2,2] = 10
        self.assertTrue(np.all(array.super == thedata))

        t1 = traj.t1
        t1 = make_ordinary_result(t1, trajectory=traj,)
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        t1 = traj.t1
        self.assertTrue(isinstance(t1, ObjectTable))#
        self.assertTrue(np.all(t1['huhu'][0] == np.ones(3)))

        df = traj.df
        df = make_ordinary_result(df, trajectory=traj,)
        traj.f_load_item(df)
        theframe = df.f_get()
        self.assertTrue(isinstance(df, Result))
        self.assertTrue(isinstance(theframe, pd.DataFrame))
        self.assertTrue(theframe['hi'][0] == 1)

        listres = traj.f_get('mylist')
        listres = make_shared_result(listres, trajectory=traj)
        with StorageContextManager(traj) as cm:
            self.assertTrue(listres[2] == 3)
            listres[0] = 4

        self.assertTrue(listres[0] == 4)
        listres = make_ordinary_result(listres, trajectory=traj, new_data_name='yuppy')
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        listres = traj.mylist
        self.assertTrue(isinstance(listres, Result))
        self.assertTrue(listres.yuppy[0] == 4)
        self.assertTrue(isinstance(listres.yuppy, list))

        mytuple = traj.mytuple
        with self.assertRaises(TypeError):
            mytuple = make_shared_result(mytuple, traj)

        mytuple.f_empty()
        with self.assertRaises(RuntimeError):
            mytuple = make_shared_result(mytuple, traj, old_data_name='k',
                                         new_class=SharedArrayResult)

        traj.f_load_item(mytuple)
        traj.f_delete_item(mytuple, delete_only='wa')
        mytuple.f_empty()

        with self.assertRaises(pt.NoSuchNodeError):
            mytuple = make_shared_result(mytuple, traj, old_data_name='hjh',
                                         new_class=SharedArrayResult)

        mytuple = make_shared_result(mytuple, traj, old_data_name='k', new_class=SharedArrayResult)
        self.assertTrue(mytuple[1] == 2)

        mytuple = make_ordinary_result(mytuple, trajectory=traj, new_data_name='k')
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        mytuple = traj.mytuple
        self.assertTrue(isinstance(mytuple.k, tuple))
        self.assertTrue(mytuple.k[2] == 3)

        myframe = traj.myframe
        myframe = make_shared_result(myframe, traj)

        theframe = myframe.f_read()
        self.assertTrue(theframe['answer'][0] == 42)

        myframe = make_ordinary_result(myframe, trajectory=traj, new_data_name='jj')
        traj.f_load_item(myframe)
        self.assertTrue(myframe.jj['answer'][0] == 42)

        mytable = traj.f_get('mytable')
        mytable = make_shared_result(mytable, traj)

        self.assertTrue(isinstance(mytable, SharedTableResult))
        rows = mytable.f_read()

        self.assertTrue(rows[0][0] == 42)

        mytable = make_ordinary_result(mytable, trajectory=traj, new_data_name='jup')

        traj.f_load_item(mytable)

        self.assertTrue(isinstance(mytable, Result))
        self.assertTrue(mytable.jup['answer'][0] == 42)


    def test_storing_and_manipulating(self):
        filename = make_temp_dir('hdf5manipulation.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        thedata = np.zeros((1000,1000))
        myarray = SharedArrayResult('array', trajectory=traj)
        mytable = SharedTableResult('t1', trajectory=traj)
        mytable2 = SharedTableResult('h.t2', trajectory=traj)
        mytable3 = SharedTableResult('jjj.t3', trajectory=traj)

        traj.f_store(only_init=True)
        traj.f_add_result(myarray)
        myarray.f_create_shared_data(data=thedata)
        traj.f_add_result(mytable)
        mytable.f_create_shared_data(first_row={'hi':compat.tobytes('hi'), 'huhu':np.ones(3)})
        traj.f_add_result(mytable2)
        mytable2.f_create_shared_data(description={'ha': pt.StringCol(2, pos=0),'haha': pt.FloatCol( pos=1)})
        traj.f_add_result(mytable3)
        mytable3.f_create_shared_data(description={'ha': pt.StringCol(2, pos=0),'haha': pt.FloatCol( pos=1)})

        traj.f_store()

        newrow = {'ha':'hu', 'haha': 4.0}

        with self.assertRaises(RuntimeError):
            row = traj.t2.v_row

        with StorageContextManager(traj) as cm:
            row = traj.t2.v_row
            for irun in range(11):
                for key, val in newrow.items():
                    row[key] = val
                row.append()
            traj.t3.f_flush()

        data = myarray.f_read()
        arr = myarray.f_get_data_node()
        self.assertTrue(np.all(data == thedata))

        with StorageContextManager(traj) as cm:
            myarray[2,2] = 10
            data = myarray.f_read()
            self.assertTrue(data[2,2] == 10)

        self.assertTrue(data[2,2] == 10 )
        self.assertFalse(traj.v_storage_service.is_open)

        traj = load_trajectory(name=trajname, filename=filename)

        traj.f_load(load_data=2)


        self.assertTrue(traj.t2.v_nrows == 11, '%s != 11'  % str(traj.t2.v_nrows))
        self.assertTrue(traj.t2[0]['ha'] == compat.tobytes('hu'), traj.t2[0]['ha'])
        self.assertTrue(traj.t2[1]['ha'] == compat.tobytes('hu'), traj.t2[1]['ha'])
        self.assertTrue('huhu' in traj.t1.v_colnames)
        self.assertTrue(traj.array[2,2] == 10)

    @unittest.skipIf(platform.system() == 'Windows', 'Not supported under Windows')
    def test_compacting(self):
        filename = make_temp_dir('hdf5compacting.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name
        traj.v_storage_service.complevel = 7

        first_row = {'ha': compat.tobytes('hi'), 'haha':np.zeros((3,3))}

        traj.f_store(only_init=True)

        res1 = traj.f_add_result('My.Tree.Will.Be.Deleted', 42)
        res2 = traj.f_add_result('Mine.Too.HomeBoy', 42, comment='Don`t cry for me!')

        traj.f_add_result(SharedTableResult, 'myres').f_create_shared_data(first_row=first_row)

        with StorageContextManager(traj):
            tab = traj.myres
            for irun in range(10000):
                row = traj.myres.v_row
                for key in first_row:
                    row[key] = first_row[key]
                row.append()
        traj.f_store()
        del traj
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        with StorageContextManager(traj) as cm:
            tb = traj.myres.f_get_data_node()
            ptcompat.remove_rows(tb, 1000, 10000)

            cm.f_flush_store()
            self.assertTrue(traj.myres.v_nrows == 1001)

        traj.f_delete_item(traj.My, recursive=True)
        traj.f_delete_item(traj.Mine, recursive=True)

        size =  os.path.getsize(filename)
        get_root_logger().info('Filesize is %s' % str(size))
        name_wo_ext, ext = os.path.splitext(filename)
        backup_file_name = name_wo_ext + '_backup' + ext
        code = compact_hdf5_file(filename, keep_backup=True)
        if code != 0:
            raise RuntimeError('ptrepack fail')
        backup_size = os.path.getsize(backup_file_name)
        self.assertTrue(backup_size == size)
        new_size = os.path.getsize(filename)
        get_root_logger().info('New filesize is %s' % str(new_size))
        self.assertTrue(new_size < size, "%s > %s" %(str(new_size), str(size)))

    def test_all_arrays(self):
        filename = make_temp_dir('hdf5arrays.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        npearray = np.ones((2,10,3), dtype=np.float)
        thevlarray = np.array([compat.tobytes('j'), 22.2, compat.tobytes('gutter')])
        traj.f_store(only_init=True)
        traj.f_add_result(SharedCArrayResult, 'super.carray', comment='carray').f_create_shared_data(shape=(10, 10), atom=pt.atom.FloatAtom())
        traj.f_add_result(SharedEArrayResult, 'earray').f_create_shared_data(obj=npearray)
        traj.f_add_result(SharedVLArrayResult, 'vlarray').f_create_shared_data(object=thevlarray)
        traj.f_add_result(SharedArrayResult, 'array').f_create_shared_data(data=npearray)

        traj.f_store()

        traj = load_trajectory(name=trajname, filename=filename, load_all=2)

        toappned = [44, compat.tobytes('k')]
        with StorageContextManager(traj) as cm:
            a1 = traj.array
            a1[0,0,0] = 4.0

            a2 = traj.carray
            a2[0,1] = 4

            a4 = traj.vlarray
            a4.f_append(toappned)


            a3 = traj.earray
            a3.f_append(np.zeros((1,10,3)))

            #cm.f_flush_storage()

        traj = load_trajectory(name=trajname, filename=filename, load_all=2)

        with StorageContextManager(traj) as cm:
            a1 = traj.array
            self.assertTrue(a1[0,0,0] == 4.0)

            a2 = traj.carray
            self.assertTrue(a2[0,1] == 4)

            a3 = traj.earray
            self.assertTrue(a3.f_read().shape == (3,10,3))

            a4 = traj.vlarray
            for idx, x in enumerate(a4):
                if idx == 0:
                    self.assertTrue(np.all(x == np.array(thevlarray)))
                elif idx == 1:
                    self.assertTrue(np.all(x == np.array(toappned)))
                else:
                    raise RuntimeError()

    def test_df(self):
        filename = make_temp_dir('hdf5errors.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        traj.f_store()
        dadict = {'hi': [ 1,2,3,4,5], 'shu':['bi', 'du', 'da', 'ha', 'hui']}
        dadict2 = {'answer': [42]}
        traj.f_add_result(SharedPandasDataResult, 'dfs.df').f_create_shared_data(pd.DataFrame(dadict))
        traj.f_add_result(SharedPandasDataResult, 'dfs.df1').f_create_shared_data(data=pd.DataFrame(dadict2))
        traj.f_add_result(SharedPandasDataResult, 'dfs.df3').f_create_shared_data()

        for irun in range(10):
            traj.df3.f_append(traj.df1.f_read())

        dframe = traj.df3.f_read()

        self.assertTrue(len(dframe) == 10)

        what = traj.df.f_select(where='index == 2')
        self.assertTrue(len(what)==1)


    def test_errors(self):
        filename = make_temp_dir('hdf5errors.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        npearray = np.ones((2,10,3), dtype=np.float)
        thevlarray = np.array([compat.tobytes('j'), 22.2, compat.tobytes('gutter')])

        with self.assertRaises(TypeError):
            traj.f_add_result(SharedVLArrayResult, 'arrays.vlarray').f_create_shared_data(object=thevlarray)
        traj.f_store()
        traj.arrays.vlarray.f_create_shared_data(object=thevlarray)
        traj.f_add_result(SharedArrayResult, 'arrays.array').f_create_shared_data(data=npearray)
        traj.arrays.f_add_result(SharedCArrayResult, 'super.carray', comment='carray').f_create_shared_data(shape=(10, 10), atom=pt.atom.FloatAtom())
        traj.arrays.f_add_result(SharedEArrayResult, 'earray').f_create_shared_data(obj=npearray)


        traj.f_store()

        with self.assertRaises(RuntimeError):
            traj.arrays.array.f_iter_rows()


        with StorageContextManager(traj) as cm:
            with self.assertRaises(RuntimeError):
                with StorageContextManager(traj) as cm2:
                    pass
            self.assertTrue(traj.v_storage_service.is_open)
            with self.assertRaises(RuntimeError):
                StorageContextManager(traj).f_open_store()

        self.assertFalse(traj.v_storage_service.is_open)


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)