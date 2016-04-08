__author__ = 'Henri Bunting'

import numpy as np
import os

try:
    import brian2
    from brian2.units.stdunits import mvolt, mV, mA, ms, kHz
    from brian2.units.fundamentalunits import Quantity
    from pypet.brian2.parameter import Brian2Parameter, Brian2Result, Brian2MonitorResult
except ImportError:
    brian2 = None

from pypet.tests.testutils.data import TrajectoryComparator
from pypet.tests.testutils.ioutils import make_temp_dir, make_trajectory_name, get_log_config, \
    parse_args, run_suite, unittest
from pypet import Environment, load_trajectory
from pypet.storageservice import HDF5StorageService


@unittest.skipIf(brian2 is None, 'Can only be run with brian2!')
class Brian2hdf5Test(TrajectoryComparator):

    tags = 'integration', 'brian2', 'parameter', 'monitor', 'hdf5', 'henri'

    def test_hdf5_store_load_parameter(self):
        traj_name = make_trajectory_name(self)
        file_name = make_temp_dir(os.path.join('brian2', 'tests', 'hdf5', 'test_%s.hdf5' % traj_name))
        env = Environment(trajectory=traj_name, filename=file_name, log_config=get_log_config(),
                            dynamic_imports=[Brian2Parameter], add_time=False, storage_service=HDF5StorageService)
        traj = env.v_trajectory
        traj.v_standard_parameter = Brian2Parameter
        traj.f_add_parameter('brian2.single.millivolts', 10*mvolt, comment='single value')

        #traj.f_add_parameter('brian2.array.millivolts', [11, 12]*mvolt, comment='array')
        #traj.f_add_parameter('mV1', 42.0*mV)
        #traj.f_add_parameter('ampere1', 1*mA)
        #traj.f_add_parameter('integer', 16)
        #traj.f_add_parameter('kHz05', 0.5*kHz)
        #traj.f_add_parameter('nested_array', np.array([[6.,7.,8.],[9.,10.,11.]]) * ms)
        #traj.f_add_parameter('b2a', np.array([1., 2.]) * mV)

        # We also need to check if explorations work with hdf5 store!
        #explore_dict = {'ampere1': [1*mA, 2*mA, 3*mA],
        #                'integer': [42,43,44],
        #                'b2a': [np.array([1., 2.]) * mV, np.array([1., 4.]) * mV,
        #                       np.array([1., 2.]) * mV]}
        #traj.f_explore(explore_dict)

        traj.f_store()

        traj2 = load_trajectory(filename=file_name, name=traj_name, dynamic_imports=[Brian2Parameter],
                                load_data=2)
        self.compare_trajectories(traj, traj2)


    def test_hdf5_store_load_result(self):
        traj_name = make_trajectory_name(self)
        file_name = make_temp_dir(os.path.join('brian2', 'tests', 'hdf5', 'test_%s.hdf5' % traj_name))
        env = Environment(trajectory=traj_name, filename=file_name, log_config=get_log_config(),
                            dynamic_imports=[Brian2Result], add_time=False, storage_service=HDF5StorageService)
        traj = env.v_trajectory
        traj.v_standard_result = Brian2Result
        traj.f_add_result('brian2.single.millivolts_single_a', 10*mvolt, comment='single value a')
        traj.f_add_result('brian2.single.millivolts_single_c', 11*mvolt, comment='single value b')

        traj.f_add_result('brian2.array.millivolts_array_a', [11, 12]*mvolt, comment='array')
        traj.f_add_result('mV1', 42.0*mV)
        # results can hold much more than a single data item:
        traj.f_add_result('ampere1', 1*mA, 44, test=300*mV, test2=[1,2,3],
                          test3=np.array([1,2,3])*mA, comment='Result keeping track of many things')
        traj.f_add_result('integer', 16)
        traj.f_add_result('kHz05', 0.5*kHz)
        traj.f_add_result('nested_array', np.array([[6.,7.,8.],[9.,10.,11.]]) * ms)
        traj.f_add_result('b2a', np.array([1., 2.]) * mV)

        traj.f_add_result('nounit', Quantity(np.array([[6.,7.,8.],[9.,10.,11.]])))

        traj.f_store()

        traj2 = load_trajectory(filename=file_name, name=traj_name, dynamic_imports=[Brian2Result], load_data=2)

        self.compare_trajectories(traj, traj2)


    def test_hdf5_store_load_monitorresult(self):
        traj_name = make_trajectory_name(self)
        file_name = make_temp_dir(os.path.join('brian2', 'tests', 'hdf5', 'test_%s.hdf5' % traj_name))
        env = Environment(trajectory=traj_name, filename=file_name, log_config=get_log_config(),
                            dynamic_imports=[Brian2MonitorResult], add_time=False, storage_service=HDF5StorageService)
        traj = env.v_trajectory
        traj.v_standard_result = Brian2MonitorResult
        traj.f_add_result('brian2.single.millivolts_single_a', 10*mvolt, comment='single value a')

        traj.f_add_result('brian2.single.millivolts_single_c', 11*mvolt, comment='single value b')

        traj.f_add_result('brian2.array.millivolts_array_a', [11, 12]*mvolt, comment='array')
        traj.f_add_result('mV1', 42.0*mV)
        # results can hold much more than a single data item:
        traj.f_add_result('ampere1', 1*mA, 44, test=300*mV, test2=[1,2,3],
                          test3=np.array([1,2,3])*mA, comment='Result keeping track of many things')
        traj.f_add_result('integer', 16)
        traj.f_add_result('kHz05', 0.5*kHz)
        traj.f_add_result('nested_array', np.array([[6.,7.,8.],[9.,10.,11.]]) * ms)
        traj.f_add_result('b2a', np.array([1., 2.]) * mV)


        traj.f_store()

        traj2 = load_trajectory(filename=file_name, name=traj_name, dynamic_imports=[Brian2MonitorResult], load_data=2)

        #traj._logger.error('traj :'+str(traj))
        #traj._logger.error('traj2:'+str(traj2))
        self.compare_trajectories(traj, traj2)


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)