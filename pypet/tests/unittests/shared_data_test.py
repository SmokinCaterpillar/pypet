__author__ = ('Robert Meyer', 'Mehmet Nevvaf Timur')

import sys
if sys.version_info < (2, 7, 0):
    import unittest2 as unittest
else:
    import unittest

import os
import platform
import numpy as np
import pandas as pd
import tables as pt
from pypet import SharedPandasFrame,  ObjectTable, compat,  make_ordinary_result, Result, \
    make_shared_result, compact_hdf5_file, SharedCArray, SharedEArray, \
    SharedVLArray

from pypet.tests.testutils.ioutils import get_root_logger, parse_args, run_suite
from pypet.tests.testutils.ioutils import make_temp_dir, make_trajectory_name, unittest
from pypet.tests.testutils.data import TrajectoryComparator
from pypet import Trajectory, SharedResult, SharedTable, SharedArray, load_trajectory, StorageContextManager
import pypet.utils.ptcompat as ptcompat
import pypet.compat as compat

class MyTable(pt.IsDescription):

    id = pt.Int32Col()
    name = pt.StringCol(15)
    surname = pt.StringCol(15)
    weight = pt.FloatCol()


@unittest.skipIf(ptcompat.tables_version < 3, 'Only supported for PyTables 3 and newer')
class StorageDataTrajectoryTests(TrajectoryComparator):

    tags = 'unittest', 'trajectory', 'shared', 'hdf5'

    def test_conversions(self):
        filename = make_temp_dir('hdf5manipulation.hdf5')
        traj = Trajectory(name=make_trajectory_name(self), filename=filename)

        trajname = traj.v_name
        traj.v_standard_result = SharedResult

        traj.f_store(only_init=True)

        traj.f_add_result('shared_data')

        thedata = np.zeros((1000, 1000))
        myarray = SharedArray('array', traj.shared_data, trajectory=traj)
        traj.shared_data['array'] = myarray
        mytable = SharedTable('t1', traj.shared_data, trajectory=traj)
        traj.shared_data['t1'] = mytable
        dadict = {'hi': [1, 2, 3, 4, 5], 'shu': ['bi', 'du', 'da', 'ha', 'hui']}
        dadict2 = {'answer': [42]}
        res = traj.f_add_result('shared.dfs')
        res['df'] = SharedPandasFrame()
        res['df'].create_shared_data(data=pd.DataFrame(dadict), trajectory=traj)
        frame = SharedPandasFrame('df1', traj.f_get('shared.dfs'), trajectory=traj,
                                  add_to_parent=True)
        frame.create_shared_data(data=pd.DataFrame(dadict2),)
        res['df1'] = frame

        traj.f_add_result('mylist', [1, 2, 3])
        traj.f_add_result('my.mytuple', k=(1, 2, 3), wa=42)
        traj.f_add_result('my.myarray', np.zeros((50, 50)))
        traj.f_add_result('my.myframe', data=pd.DataFrame(dadict2))
        traj.f_add_result('my.mytable', ObjectTable(data=dadict2))

        myarray.create_shared_data(data=thedata)
        mytable.create_shared_data(first_row={'hi': compat.tobytes('hi'), 'huhu': np.ones(3)})

        traj.f_store()

        data = myarray.read()
        myarray.get_data_node()
        self.assertTrue(np.all(data == thedata))

        with StorageContextManager(traj):
            myarray[2, 2] = 10
            data = myarray.read()
            self.assertTrue(data[2, 2] == 10)

        self.assertTrue(data[2, 2] == 10)
        self.assertFalse(traj.v_storage_service.is_open)

        traj = load_trajectory(name=trajname, filename=filename, load_all=2,
                               dynamic_imports=SharedResult)

        make_ordinary_result(traj.shared_data, 'array', trajectory=traj)
        array = traj.shared_data.array
        self.assertTrue(isinstance(array, np.ndarray))
        thedata[2, 2] = 10
        self.assertTrue(np.all(array == thedata))

        make_ordinary_result(traj.shared_data, 't1', trajectory=traj,)
        t1 = traj.shared_data.t1
        self.assertTrue(isinstance(t1, ObjectTable))
        self.assertTrue(np.all(t1['huhu'][0] == np.ones(3)))

        dfs = traj.shared.dfs
        make_ordinary_result(traj.shared.dfs, 'df', trajectory=traj)
        theframe = dfs.f_get('df')
        self.assertTrue(isinstance(dfs, Result))
        self.assertTrue(isinstance(theframe, pd.DataFrame))
        self.assertTrue(theframe['hi'][0] == 1)

        listres = traj.f_get('mylist')
        listres = make_shared_result(listres, 0, trajectory=traj)
        with StorageContextManager(traj):
            self.assertTrue(listres[0][2] == 3)
            listres[0][0] = 4

        self.assertTrue(listres[0][0] == 4)
        listres = make_ordinary_result(listres, 0, trajectory=traj)
        traj = load_trajectory(name=trajname, filename=filename, load_all=2,
                               dynamic_imports=SharedResult)
        mylist = traj.mylist
        self.assertTrue(isinstance(listres, Result))
        self.assertTrue(mylist[0] == 4)
        self.assertTrue(isinstance(mylist, list))

        mytuple = traj.mytuple

        with self.assertRaises(AttributeError):
            mytuple = make_shared_result(mytuple, 'mylist', traj, new_class=SharedArray)

        mytuple = make_shared_result(mytuple, 'k', traj, new_class=SharedArray)
        self.assertTrue(mytuple.k[1] == 2)

        mytuple = make_ordinary_result(mytuple, 'k', trajectory=traj)
        self.assertTrue(isinstance(mytuple.k, tuple))
        self.assertTrue(mytuple.k[2] == 3)

        myframe = traj.myframe
        myframe = make_shared_result(myframe, 'data', traj)

        theframe = myframe.data.read()
        self.assertTrue(theframe['answer'][0] == 42)

        myframe = make_ordinary_result(myframe, 'data', trajectory=traj)
        traj.f_load_item(myframe)
        self.assertTrue(myframe.data['answer'][0] == 42)

        mytable = traj.f_get('mytable')
        mytable = make_shared_result(mytable, 0, traj)

        self.assertTrue(isinstance(mytable[0], SharedTable))
        rows = mytable.mytable.read()

        self.assertTrue(rows[0][0] == 42)

        mytable = make_ordinary_result(mytable, 0, trajectory=traj)

        self.assertTrue(isinstance(mytable, Result))
        self.assertTrue(mytable[0]['answer'][0] == 42)

    def test_storing_and_manipulating(self):
        filename = make_temp_dir('hdf5manipulation.hdf5')
        traj = Trajectory(name=make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        thedata = np.zeros((1000, 1000))
        res = traj.f_add_result(SharedResult, 'shared')
        myarray = SharedArray('array', res, trajectory=traj, add_to_parent=True)
        mytable = SharedTable('t1', res, trajectory=traj, add_to_parent=True)
        mytable2 = SharedTable('t2', res, trajectory=traj, add_to_parent=True)
        mytable3 = SharedTable('t3', res, trajectory=traj, add_to_parent=True)

        traj.f_store(only_init=True)
        myarray.create_shared_data(data=thedata)
        mytable.create_shared_data(first_row={'hi': compat.tobytes('hi'), 'huhu': np.ones(3)})
        mytable2.create_shared_data(description={'ha': pt.StringCol(2, pos=0), 'haha': pt.FloatCol(pos=1)})
        mytable3.create_shared_data(description={'ha': pt.StringCol(2, pos=0), 'haha': pt.FloatCol(pos=1)})

        traj.f_store()

        newrow = {'ha': 'hu', 'haha': 4.0}

        with self.assertRaises(TypeError):
            traj.shared.t2.row

        with StorageContextManager(traj) as cm:
            row = traj.shared.t2.row
            for irun in range(11):
                for key, val in newrow.items():
                    row[key] = val
                row.append()
            traj.shared.t3.flush()

        data = myarray.read()
        myarray.get_data_node()
        self.assertTrue(np.all(data == thedata))

        with StorageContextManager(traj):
            myarray[2, 2] = 10
            data = myarray.read()
            self.assertTrue(data[2, 2] == 10)

        self.assertTrue(data[2, 2] == 10)
        self.assertFalse(traj.v_storage_service.is_open)

        traj = load_trajectory(name=trajname, filename=filename)

        traj.f_load(load_data=2)

        traj.shared.t2.traj = traj
        traj.shared.t1.traj = traj
        traj.shared.array.traj = traj

        self.assertTrue(traj.shared.t2.nrows == 11, '%s != 11' % str(traj.shared.t2.nrows))
        self.assertTrue(traj.shared.t2[0]['ha'] == compat.tobytes('hu'), traj.shared.t2[0]['ha'])
        self.assertTrue(traj.shared.t2[1]['ha'] == compat.tobytes('hu'), traj.shared.t2[1]['ha'])
        self.assertTrue('huhu' in traj.shared.t1.colnames)
        self.assertTrue(traj.shared.array[2, 2] == 10)

    @unittest.skipIf(platform.system() == 'Windows', 'Not supported under Windows')
    def test_compacting(self):
        filename = make_temp_dir('hdf5compacting.hdf5')
        traj = Trajectory(name=make_trajectory_name(self), filename=filename)
        trajname = traj.v_name
        traj.v_storage_service.complevel = 7

        first_row = {'ha': compat.tobytes('hi'), 'haha': np.zeros((3, 3))}

        traj.f_store(only_init=True)

        traj.f_add_result('My.Tree.Will.Be.Deleted', 42)
        traj.f_add_result('Mine.Too.HomeBoy', 42, comment='Don`t cry for me!')

        res = traj.f_add_result(SharedResult, 'myres')

        res['myres'] = SharedTable()

        res['myres'].create_shared_data(first_row=first_row)

        with StorageContextManager(traj):
            traj.myres
            for irun in range(10000):
                row = traj.myres.row
                for key in first_row:
                    row[key] = first_row[key]
                row.append()
        traj.f_store()
        del traj
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        with StorageContextManager(traj) as cm:
            tb = traj.myres.get_data_node()
            ptcompat.remove_rows(tb, 1000, 10000)

            cm.flush_store()
            self.assertTrue(traj.myres.nrows == 1001)

        traj.f_delete_item(traj.My, recursive=True)
        traj.f_delete_item(traj.Mine, recursive=True)

        size = os.path.getsize(filename)
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
        self.assertTrue(new_size < size, "%s > %s" % (str(new_size), str(size)))

    def test_all_arrays(self):
        filename = make_temp_dir('hdf5arrays.hdf5')
        traj = Trajectory(name=make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        npearray = np.ones((2, 10, 3), dtype=np.float)
        thevlarray = np.array([compat.tobytes('j'), 22.2, compat.tobytes('gutter')])
        traj.f_store(only_init=True)
        res = traj.f_add_result(SharedResult, 'arrays')
        res['carray'] = SharedCArray()
        res['carray'].create_shared_data(shape=(10, 10), atom=pt.atom.FloatAtom())
        res['earray'] = SharedEArray()
        res['earray'].create_shared_data(obj=npearray)
        res['vlarray'] = SharedVLArray()
        res['vlarray'].create_shared_data(obj=thevlarray)
        res['array'] = SharedArray()
        res['array'].create_shared_data(data=npearray)

        traj.f_store()

        traj = load_trajectory(name=trajname, filename=filename, load_all=2,
                               dynamic_imports=SharedResult)

        toappned = [44, compat.tobytes('k')]
        with StorageContextManager(traj):
            a1 = traj.arrays.array
            a1[0, 0, 0] = 4.0

            a2 = traj.arrays.carray
            a2[0, 1] = 4

            a4 = traj.arrays.vlarray
            a4.append(toappned)

            a3 = traj.arrays.earray
            a3.append(np.zeros((1, 10, 3)))

        traj = load_trajectory(name=trajname, filename=filename, load_all=2,
                               dynamic_imports=SharedResult)

        with StorageContextManager(traj):
            a1 = traj.arrays.array
            self.assertTrue(a1[0, 0, 0] == 4.0)

            a2 = traj.arrays.carray
            self.assertTrue(a2[0, 1] == 4)

            a3 = traj.arrays.earray
            self.assertTrue(a3.read().shape == (3, 10, 3))

            a4 = traj.arrays.vlarray
            for idx, x in enumerate(a4):
                if idx == 0:
                    self.assertTrue(np.all(x == np.array(thevlarray)))
                elif idx == 1:
                    self.assertTrue(np.all(x == np.array(toappned)))
                else:
                    raise RuntimeError()

    def test_df(self):
        filename = make_temp_dir('hdf5errors.hdf5')
        traj = Trajectory(name=make_trajectory_name(self), filename=filename)
        traj.f_store()
        dadict = {'hi': [1, 2, 3, 4, 5], 'shu': ['bi', 'du', 'da', 'ha', 'hui']}
        dadict2 = {'answer': [42]}
        traj.f_add_result(SharedResult, 'dfs.df', SharedPandasFrame()).create_shared_data(data=pd.DataFrame(dadict))
        traj.f_add_result(SharedResult, 'dfs.df1', SharedPandasFrame()).create_shared_data(data=pd.DataFrame(dadict2))
        traj.f_add_result(SharedResult, 'dfs.df3', SharedPandasFrame())

        for irun in range(10):
            traj.df3.append(traj.df1.read())

        dframe = traj.df3.read()

        self.assertTrue(len(dframe) == 10)

        what = traj.df.select(where='index == 2')
        self.assertTrue(len(what) == 1)

    def test_errors(self):
        filename = make_temp_dir('hdf5errors.hdf5')
        traj = Trajectory(name=make_trajectory_name(self), filename=filename)

        npearray = np.ones((2, 10, 3), dtype=np.float)
        thevlarray = np.array([compat.tobytes('j'), 22.2, compat.tobytes('gutter')])

        with self.assertRaises(TypeError):
            traj.f_add_result(SharedResult, 'arrays.vlarray', SharedVLArray()).create_shared_data(obj=thevlarray)
        traj.f_store()
        traj.arrays.vlarray.create_shared_data(obj=thevlarray)
        traj.f_add_result(SharedResult, 'arrays.array', SharedArray()).create_shared_data(data=npearray)
        traj.arrays.f_add_result(SharedResult, 'super.carray', SharedCArray(),
                                 comment='carray').create_shared_data(shape=(10, 10), atom=pt.atom.FloatAtom())
        traj.arrays.f_add_result(SharedResult, 'earray', SharedEArray()).create_shared_data('earray',
                                                                                            obj=npearray)

        traj.f_store()

        with self.assertRaises(TypeError):
            traj.arrays.array.iterrows()

        with StorageContextManager(traj):
            with self.assertRaises(RuntimeError):
                with StorageContextManager(traj):
                    pass
            self.assertTrue(traj.v_storage_service.is_open)
            with self.assertRaises(RuntimeError):
                StorageContextManager(traj).open_store()

        self.assertFalse(traj.v_storage_service.is_open)


@unittest.skipIf(ptcompat.tables_version < 3, 'Only supported for PyTables 3 and newer')
class SharedTableTest(TrajectoryComparator):

    tags = 'unittest', 'trajectory', 'shared', 'hdf5', 'table', 'mehmet'

    def setUp(self):
        self.filename = make_temp_dir('shared_table_test.hdf5')

        self.traj = Trajectory(name=make_trajectory_name(self), filename=self.filename)

        self.traj.v_standard_result = SharedResult

        self.traj.f_store(only_init=True)

        self.traj.f_add_result('shared_data')

        self.shared_table = SharedTable(name='table',
                                        parent=self.traj.shared_data,
                                        trajectory=self.traj,
                                        add_to_parent=True)

    def test_table_read(self):
        the_reading_table = self.traj.results.shared_data.table
        self.assertTrue(the_reading_table is self.shared_table)
        the_reading_table.create_shared_data(description=MyTable)

        with StorageContextManager(self.traj):
            row = the_reading_table.row
            for i in range(10):
                row['id'] = i
                row['name'] = 'mehmet %d' % i
                row['surname'] = 'Timur'
                row['weight'] = 65.5 + i * 1.5
                row.append()
            the_reading_table.flush()

            for idx, row in enumerate(the_reading_table.iterrows()):
                self.assertEqual(row['id'], idx)

        self.traj.f_store()

        traj2 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        second_reading_table = traj2.results.shared_data.table

        self.assertTrue(np.all(the_reading_table.read() == second_reading_table.read()))

        second_reading_table.append([(21, 'aaa', 'bbb', 100)])

        self.assertTrue(np.all(the_reading_table.read() == second_reading_table.read()))

        traj3 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        third_reading_table = traj3.results.shared_data.table

        self.assertTrue(np.all(the_reading_table.read() == third_reading_table.read()))

    def test_table_append(self):
        the_append_table = self.traj.results.shared_data.table
        self.assertTrue(the_append_table is self.shared_table)
        the_append_table.create_shared_data(description=MyTable)

        with StorageContextManager(self.traj):
            row = the_append_table.row
            for i in range(15):
                row['id'] = i * 2
                row['name'] = 'name %d' % i
                row['surname'] = '%d surname' % i
                row['weight'] = (i*0.5 + 50.0)
                row.append()
            the_append_table.flush()

            for idx, row in enumerate(the_append_table.iterrows()):
                self.assertEqual(row['id'], idx * 2)

        self.traj.f_store()

        traj2 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        second_append_table = traj2.results.shared_data.table

        with StorageContextManager(traj2):
            for idx, row in enumerate(second_append_table.iterrows()):
                self.assertEqual(row['id'], idx * 2)

            second_append_table.append([(30, 'mehmet', 'timur', 65.5)])

            self.assertEqual(second_append_table.read(field='id')[-1], 30)
            self.assertEqual(second_append_table.read(field='name')[-1], compat.tobytes('mehmet'))
            self.assertEqual(second_append_table.read(field='surname')[-1], compat.tobytes('timur'))
            self.assertEqual(second_append_table.read(field='weight')[-1], 65.5)

        traj2.f_store()

        traj3 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        third_append_table = traj3.results.shared_data.table

        self.assertEqual((third_append_table.read(field='id')[-1]), 30)
        self.assertEqual((third_append_table.read(field='name')[-1]), compat.tobytes('mehmet'))
        self.assertEqual((third_append_table.read(field='surname')[-1]), compat.tobytes('timur'))
        self.assertEqual((third_append_table.read(field='weight')[-1]), 65.5)

        third_append_table.append([(33, 'Harrison', 'Ford', 95.5)])

        self.assertEqual((third_append_table.read(field='id')[-1]), 33)
        self.assertEqual((third_append_table.read(field='name')[-1]), compat.tobytes('Harrison'))
        self.assertEqual((third_append_table.read(field='surname')[-1]), compat.tobytes('Ford'))
        self.assertEqual((third_append_table.read(field='weight')[-1]), 95.5)

    def test_table_iterrows(self):
        the_iterrows_table = self.traj.results.shared_data.table
        self.assertTrue(the_iterrows_table is self.shared_table)
        the_iterrows_table.create_shared_data(description=MyTable)

        with StorageContextManager(self.traj):
            row = the_iterrows_table.row
            for i in range(10):
                row['id'] = i
                row['name'] = 'mehmet %d' % i
                row['surname'] = 'Timur'
                row['weight'] = 65.5 + i * 1.5
                row.append()
            the_iterrows_table.flush()

            for idx, row in enumerate(the_iterrows_table.iterrows()):
                self.assertEqual(row['id'], idx)

        self.traj.f_store()

        traj2 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        second_iterrows_table = traj2.results.shared_data.table

        with StorageContextManager(traj2):
            for idx, row in enumerate(second_iterrows_table.iterrows()):
                self.assertEqual(row['id'], idx)


@unittest.skipIf(ptcompat.tables_version < 3, 'Only supported for PyTables 3 and newer')
class SharedArrayTest(TrajectoryComparator):

    tags = 'unittest', 'trajectory', 'shared', 'hdf5', 'array', 'mehmet'

    def setUp(self):
        self.filename = make_temp_dir('shared_table_test.hdf5')

        self.traj = Trajectory(name=make_trajectory_name(self), filename=self.filename)

        self.traj.v_standard_result = SharedResult

        self.traj.f_store(only_init=True)

        self.traj.f_add_result('shared_data')

        self.shared_array = SharedArray(name='array',
                                        parent=self.traj.shared_data,
                                        trajectory=self.traj,
                                        add_to_parent=True)

    def test_array_read(self):
        the_reading_array = np.ones((100, 100)) * 4

        first_reading_array = self.traj.results.shared_data.array

        self.assertTrue(first_reading_array is self.shared_array)

        first_reading_array.create_shared_data(obj=the_reading_array)

        self.traj.f_store()

        traj2 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        second_reading_array = traj2.shared_data.array.read()

        self.assertTrue(np.all(the_reading_array == second_reading_array),
                        '%s != %s' % (str(the_reading_array), str(second_reading_array)))

    def test_array_getitem(self):
        the_getitem_array = np.array(range(100))

        first_getitem_array = self.traj.results.shared_data.array

        first_getitem_array.create_shared_data(obj=the_getitem_array)

        for k in range(len(the_getitem_array)):
            self.assertEqual(the_getitem_array[k], first_getitem_array[k])

        self.traj.f_store()

        traj2 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        for j in range(len(the_getitem_array)):
            self.assertEqual(the_getitem_array[j], traj2.results.shared_data.array[j])

    def test_array_getenum(self):
        the_getenum_array = np.array(range(100))

        first_getenum_array = self.traj.results.shared_data.array

        first_getenum_array.create_shared_data(obj=the_getenum_array)

        with self.assertRaises(TypeError):
            first_getenum_array.get_enum()

        self.traj.f_store()

        traj2 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        second_enum_array = traj2.results.shared_data.array

        with self.assertRaises(TypeError):
            second_enum_array.get_enum()

    def test_array_iterrows(self):
        the_iterrows_array = np.random.randint(0, 100, (100, 100))

        first_iterrows_array = self.traj.results.shared_data.array

        first_iterrows_array.create_shared_data(obj=the_iterrows_array)

        with StorageContextManager(self.traj):
            for idx, row in enumerate(first_iterrows_array.iterrows()):
                self.assertTrue(np.all(row == the_iterrows_array[idx, :]))

        self.traj.f_store()

        traj2 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        second_iterrows_array = traj2.results.shared_data.array

        with StorageContextManager(traj2):
            for idx, row in enumerate(second_iterrows_array.iterrows()):
                self.assertTrue(np.all(row == the_iterrows_array[idx, :]))

    def test_array_setitem(self):
        the_setitem_array = np.zeros((50, 50))

        first_setitem_array = self.traj.results.shared_data.array

        first_setitem_array.create_shared_data(obj=the_setitem_array)

        first_setitem_array[2, 2] = 10

        self.assertEqual(first_setitem_array[2, 2], 10)

        self.traj.f_store()

        traj2 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        second_setitem_array = traj2.results.shared_data.array

        self.assertEqual(second_setitem_array[2, 2], 10)

        second_setitem_array[3, 3] = 17

        self.assertEqual(second_setitem_array[3, 3], 17)

if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)