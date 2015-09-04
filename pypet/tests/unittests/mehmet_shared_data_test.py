__author__ = 'mehmet'

import numpy as np
import tables as pt
from pypet.tests.testutils.ioutils import make_temp_dir, make_trajectory_name, unittest
from pypet.tests.testutils.data import TrajectoryComparator

from pypet import Trajectory, SharedResult, SharedTable, SharedArray, load_trajectory, StorageContextManager
import pypet.utils.ptcompat as ptcompat


class MyTable(pt.IsDescription):

    id = pt.Int32Col()
    name = pt.StringCol(15)
    surname = pt.StringCol(15)
    weight = pt.Float16Col()


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

        self.assertItemsEqual(the_reading_table.read(), second_reading_table.read())

        second_reading_table.append([(21, 'aaa', 'bbb', 100)])

        self.assertItemsEqual(the_reading_table.read(), second_reading_table.read())

        traj3 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        third_reading_table = traj3.results.shared_data.table

        self.assertItemsEqual(the_reading_table.read(), third_reading_table.read())

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

            self.assertEqual((second_append_table.read(field='id')[-1]), 30)
            self.assertEqual((second_append_table.read(field='name')[-1]), 'mehmet')
            self.assertEqual((second_append_table.read(field='surname')[-1]), 'timur')
            self.assertEqual((second_append_table.read(field='weight')[-1]), 65.5)

        traj2.f_store()

        traj3 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2, dynamic_imports=SharedResult)

        third_append_table = traj3.results.shared_data.table

        self.assertEqual((third_append_table.read(field='id')[-1]), 30)
        self.assertEqual((third_append_table.read(field='name')[-1]), 'mehmet')
        self.assertEqual((third_append_table.read(field='surname')[-1]), 'timur')
        self.assertEqual((third_append_table.read(field='weight')[-1]), 65.5)

        third_append_table.append([(33, 'Harrison', 'Ford', 95.5)])

        self.assertEqual((third_append_table.read(field='id')[-1]), 33)
        self.assertEqual((third_append_table.read(field='name')[-1]), 'Harrison')
        self.assertEqual((third_append_table.read(field='surname')[-1]), 'Ford')
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
