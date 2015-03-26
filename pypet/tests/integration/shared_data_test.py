__author__ = 'Robert Meyer'

import os
import logging
import random

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import tables as pt
import scipy.sparse as spsp

from pypet.shareddata import *
from pypet import Trajectory
from pypet.tests.testutils.ioutils import make_temp_dir, make_trajectory_name, run_suite, \
     get_root_logger, parse_args, get_log_config
from pypet import compat, Environment, cartesian_product
from pypet import pypetconstants
from pypet.tests.testutils.data import create_param_dict, add_params, TrajectoryComparator
import pypet.utils.ptcompat as ptcompat


def copy_one_entry_from_giant_matrices(traj):
    matrices = traj.matrices
    idx = traj.v_idx
    m1 = matrices.m1
    m2 = matrices.m2
    m2[idx,idx,idx] = m1[idx,idx,idx]
    traj.f_add_result('dummy.dummy', 42)


def write_into_shared_storage(traj):
    traj.f_add_result('ggg', 42)
    traj.f_add_derived_parameter('huuu', 46)

    root = get_root_logger()
    daarrays = traj.res.daarrays
    idx = traj.v_idx
    ncores = traj[traj.v_environment_name].f_get_default('ncores', 1)
    root.info('1. This')
    a = daarrays.a
    a[idx] = idx
    root.info('2. is')
    ca = daarrays.ca
    ca[idx] = idx
    root.info('3. a')
    ea = daarrays.ea
    ea.f_append(np.ones((1,10))*idx)
    root.info('4. sequential')
    vla = daarrays.vla
    vla.f_append(np.ones(idx+2)*idx)
    root.info('5. Block')
    if idx > ncores+2:
        x, y = a[idx-ncores], idx-ncores
        if x != y:
            raise RuntimeError('ERROR in write_into_shared_storage %s != %s' % (str(x), str(y)))
        x, y = ca[idx-ncores], idx-ncores
        if x != y:
            raise RuntimeError('ERROR in write_into_shared_storage %s != %s' % (str(x), str(y)))
        x, y = ea[idx-ncores, 9], ea[idx-ncores, 8]
        if x != y:
            raise RuntimeError('ERROR in write_into_shared_storage %s != %s' % (str(x), str(y)))
        x, y = vla[idx-ncores][0], vla[idx-ncores][1]
        if x != y:
            raise RuntimeError('ERROR in write_into_shared_storage %s != %s' % (str(x), str(y)))
    root.info('6. !!!!!!!!!')

    tabs = traj.tabs

    with StorageContextManager(traj) as cm:
        t1 = tabs.t1
        row = t1.v_row
        row['run_name'] = compat.tobytes(traj.v_crun)
        row['idx'] = idx
        row.append()
        t1.f_flush()

    t2 = tabs.t2
    row = t2[idx]
    if row['run_name'] != compat.tobytes(traj.v_crun):
        raise RuntimeError('Names in run table do not match, Run: %s != %s' % (row['run_name'],
                                                                                   traj.v_crun) )

    df = traj.df
    df.f_append(pd.DataFrame({'idx':[traj.v_idx], 'run_name':traj.v_crun}))

@unittest.skipIf(ptcompat.tables_version < 3, 'Only supported for PyTables 3 and newer')
class StorageDataEnvironmentTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment', 'shared'

    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1
        self.use_pool=True
        self.pandas_format='fixed'
        self.pandas_append=False
        self.complib = 'zlib'
        self.complevel=9
        self.shuffle=True
        self.fletcher32 = False
        self.encoding = 'utf8'

    def explore(self, traj, trials=3):
        self.explored ={'Normal.trial': range(trials),
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])],
            'csr_mat' :[spsp.csr_matrix((2222,22)), spsp.csr_matrix((2222,22))]}

        self.explored['csr_mat'][0][1,2]=44.0
        self.explored['csr_mat'][1][2,2]=33


        traj.f_explore(cartesian_product(self.explored))

    def explore_large(self, traj):
        self.explored ={'Normal.trial': [0,1]}
        traj.f_explore(cartesian_product(self.explored))

    def tearDown(self):
        self.env.f_disable_logging()

        super(StorageDataEnvironmentTest, self).tearDown()

    def add_array_params(self, traj):
        length = len(traj)
        da_data = np.zeros(length, dtype=np.int)
        traj.f_store(only_init=True)
        traj.f_add_result(SharedArrayResult, 'daarrays.a').f_create_shared_data(obj=da_data)
        traj.f_add_result(SharedCArrayResult, 'daarrays.ca').f_create_shared_data( obj=da_data)
        traj.f_add_result(SharedEArrayResult, 'daarrays.ea').f_create_shared_data(shape=(0, 10),
                                                            atom=pt.FloatAtom(),
                                                            expectedrows=length)
        traj.f_add_result(SharedVLArrayResult, 'daarrays.vla').f_create_shared_data(atom=pt.FloatAtom())


        traj.f_add_result(SharedTableResult, 'tabs.t1').f_create_shared_data(description={'idx': pt.IntCol(), 'run_name': pt.StringCol(30)},
                        expectedrows=length)

        traj.f_add_result(SharedTableResult, 'tabs.t2').f_create_shared_data(description={'run_name': pt.StringCol(3000)})

        traj.f_add_result(SharedPandasDataResult, 'pandas.df').f_create_shared_data()

        traj.f_store()

        with StorageContextManager(traj) as cm:
            for run_name in self.traj.f_get_run_names():
                row = traj.t2.v_row
                row['run_name'] = run_name
                row.append()
            traj.t2.f_flush()

        traj.t2.f_create_index('run_name')


    def setUp(self):
        self.set_mode()
        self.logfolder = make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))

        random.seed()
        self.trajname = make_trajectory_name(self)
        self.filename = make_temp_dir(os.path.join('experiments',
                                                    'tests',
                                                    'HDF5',
                                                    'test%s.hdf5' % self.trajname))

        env = Environment(trajectory=self.trajname, filename=self.filename,
                          file_title=self.trajname,
                          log_stdout=False,

                          log_config=get_log_config(),
                          results_per_run=5,
                          derived_parameters_per_run=5,
                          multiproc=self.multiproc,
                          ncores=self.ncores,
                          wrap_mode=self.mode,
                          use_pool=self.use_pool,
                          fletcher32=self.fletcher32,
                          complevel=self.complevel,
                          complib=self.complib,
                          shuffle=self.shuffle,
                          pandas_append=self.pandas_append,
                          pandas_format=self.pandas_format,
                          encoding=self.encoding)

        traj = env.v_trajectory

        self.param_dict={}
        create_param_dict(self.param_dict)
        add_params(traj,self.param_dict)

        self.traj = traj
        self.env = env

    def load_trajectory(self,trajectory_index=None,trajectory_name=None,as_new=False):
        ### Load The Trajectory and check if the values are still the same
        newtraj = Trajectory(filename=self.filename)
        newtraj.f_load(name=trajectory_name, index=trajectory_index, as_new=as_new,
                       load_parameters=2, load_derived_parameters=2, load_results=2,
                       load_other_data=2)
        return newtraj

    def check_insertions(self, traj):
        daarrays = traj.daarrays
        length = len(traj)
        the_short_one = 0
        self.assertTrue(length > 10)
        with StorageContextManager(traj) as cm:
            for idx in range(0, length):
                a = daarrays.a
                ca = daarrays.ca
                ea = daarrays.ea
                vla = daarrays.vla
                x, y = a[idx], idx
                if x != y:
                    raise RuntimeError('ERROR in write_into_shared_storage %s != %s' % (str(x), str(y)))
                x, y = ca[idx], idx
                if x != y:
                    raise RuntimeError('ERROR in write_into_shared_storage %s != %s' % (str(x), str(y)))
                x, y = ea[idx, 9], ea[idx, 8]
                if x != y:
                    raise RuntimeError('ERROR in write_into_shared_storage %s != %s' % (str(x), str(y)))
                x, y = vla[idx][0], vla[idx][1]
                if x != y:
                    raise RuntimeError('ERROR in write_into_shared_storage %s != %s' % (str(x), str(y)))

        tabs = traj.tabs

        t1 = tabs.t1
        self.assertTrue(len(t1) == length)

        with StorageContextManager(traj):
            for row in t1:
                run_name = compat.tostr(row['run_name'])
                idx = row['idx']
                self.assertTrue(traj.f_idx_to_run(run_name) == idx)

        for entry in traj.df.f_read().iterrows():
            run_name = entry[1]['run_name']
            idx = entry[1]['idx']
            self.assertTrue(traj.f_idx_to_run(idx) == run_name)

    def test_run(self):

        self.explore(self.traj)
        self.add_array_params(self.traj)

        self.traj.f_add_parameter('TEST', 'test_run')

        self.env.f_run(write_into_shared_storage)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name, as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        self.check_insertions(self.traj)
        self.check_insertions(newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        get_root_logger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 2.0, 'Size is %sMB > 2MB' % str(size_in_mb))

    def test_run_large(self):

        self.explore(self.traj, trials=30)
        self.add_array_params(self.traj)

        self.traj.f_add_parameter('TEST', 'test_run')

        self.env.f_run(write_into_shared_storage)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        self.check_insertions(self.traj)
        self.check_insertions(newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        get_root_logger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 10.0, 'Size is %sMB > 10MB' % str(size_in_mb))

    def add_matrix_params(self, traj):
        shape=(300,301,305)
        traj.f_store(only_init=True)
        traj.f_add_result(SharedCArrayResult, 'matrices.m1').f_create_shared_data(obj=np.random.rand(*shape))
        traj.f_add_result(SharedCArrayResult, 'matrices.m2').f_create_shared_data(obj=np.random.rand(*shape))
        traj.f_store()


    def check_matrices(self, traj):
        length = len(traj)
        self.assertTrue(self.length == length)
        matrices = traj.matrices
        for irun in range(length):
            with StorageContextManager(traj):
                m1 = matrices.m1
                m2 = matrices.m2
                self.assertTrue(m1[irun,irun,irun] == m2[irun,irun,irun])


    def test_giant_matrices(self):


        self.length = 20
        self.traj.f_explore({'trial': range(self.length)})

        self.add_matrix_params(self.traj)

        self.traj.f_add_parameter('TEST', 'test_run')

        self.env.f_run(copy_one_entry_from_giant_matrices)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        self.check_matrices(self.traj)
        self.check_matrices(newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        get_root_logger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 400.0, 'Size is %sMB > 400MB' % str(size_in_mb))


@unittest.skipIf(ptcompat.tables_version < 3, 'Only supported for PyTables 3 and newer')
class MultiprocStorageLockTest(StorageDataEnvironmentTest):

    # def test_run(self):
    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'pool', 'shared', 'lock'

    def set_mode(self):
        StorageDataEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True


@unittest.skipIf(ptcompat.tables_version < 3, 'Only supported for PyTables 3 and newer')
class MultiprocStorageNoPoolLockTest(StorageDataEnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'nopool', 'shared', 'lock'

    def set_mode(self):
        StorageDataEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)