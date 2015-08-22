__author__ = 'mehmet'

import numpy as np

from pypet.tests.testutils.ioutils import make_temp_dir, make_trajectory_name, unittest
from pypet.tests.testutils.data import TrajectoryComparator

from pypet import Trajectory, SharedResult, SharedTable, SharedArray, load_trajectory
import pypet.utils.ptcompat as ptcompat


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


    def test_something(self):
        table = self.traj.results.shared_data.table
        pass


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


    def test_read_data(self):
        the_data = np.ones((100, 100)) * 4
        shared_array = self.traj.results.shared_data.array
        self.assertTrue(shared_array is self.shared_array)

        shared_array.create_shared_data(data=the_data)

        self.traj.f_store()

        traj2 = load_trajectory(name=self.traj.v_name, filename=self.filename, load_all=2,
                               dynamic_imports=SharedResult)

        other_data = traj2.shared_data.array.read()
        self.assertTrue(np.all(the_data == other_data),
                        '%s != %s' % (str(the_data), str(other_data)))





