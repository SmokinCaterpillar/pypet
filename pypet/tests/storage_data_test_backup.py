__author__ = 'Robert Meyer'

import numpy as np
import tables as pt
import os
import platform
import logging
import random
import scipy.sparse as spsp
import pickle

from pypet.shareddata import StorageDataResult, SharedDataResult, check_hdf5_init,\
    SharedArrayResult, SharedCArray, SharedEArray, SharedVLArray, SharedTableResult
from pypet import Trajectory, load_trajectory
from pypet.tests.test_helpers import make_temp_file, TrajectoryComparator, make_trajectory_name, make_run,\
    create_param_dict, add_params
from pypet import compact_hdf5_file
from pypet.utils import ptcompat
from pypet import compat, Environment, cartesian_product
from pypet import pypetconstants

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest


def copy_one_entry_from_giant_matrices(traj):
    matrices = traj.matrices
    idx = traj.v_idx
    with matrices.f_context():
        m1 = matrices.m1
        m2 = matrices.m2
        m2[idx,idx,idx] = m1[idx,idx,idx]
    traj.f_add_result('dummy.dummy', 42)


def write_into_shared_storage(traj):
    traj.f_add_result('ggg', 42)
    traj.f_add_derived_parameter('huuu', 46)

    root = logging.getLogger()
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
    ea.append(np.ones((1,10))*idx)
    root.info('4. sequential')
    vla = daarrays.vla
    vla.append(np.ones(idx+1)*idx)
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

    t1 = tabs.t1
    row = {}
    row['run_name'] = compat.tobytes(traj.v_crun)
    row['idx'] = idx
    t1.append(row)
    t1.flush()

    t2 = tabs.t2
    row = t2[idx]
    if row['run_name'] != compat.tobytes(traj.v_crun):
        raise RuntimeError('Names in run table do not match, Run: %s != %s' % (row['run_name'],
                                                                                   traj.v_crun) )


class StorageDataTrajectoryTests(TrajectoryComparator):

    def test_storing_and_manipulating(self):
        filename = make_temp_file('hdf5manipulation.hdf5')
        traj = Trajectory(name = make_trajectory_name(self), filename=filename)
        trajname = traj.v_name

        thedata = np.zeros((1000,1000))
        myarray = SharedDataResult(data=thedata)
        mytable = SharedDataResult(description={'hi': pt.IntCol(), 'huhu': pt.StringCol(33)})
        mytable2 = SharedDataResult(first_row={'ha': compat.tobytes('hi'), 'haha': np.zeros((3, 3))})
        mytable3 = SharedDataResult(first_row={'ha': compat.tobytes('hu'), 'haha': np.ones((3, 3))})

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
        mytable = SharedDataResult(first_row=first_row)

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
        carray = SharedDataResult(item_type=CARRAY, shape=(10, 10), atom=pt.atom.FloatAtom())
        earray = SharedDataResult(item_type=EARRAY, obj=npearray)
        vlarray = SharedDataResult(item_type=VLARRAY, object=thevlarray)
        array = SharedDataResult(item_type=ARRAY, data=npearray)

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
        carray = SharedDataResult(item_type=CARRAY, shape=(10, 10), atom=pt.atom.FloatAtom())
        earray = SharedDataResult(item_type=EARRAY, obj=npearray)
        vlarray = SharedDataResult(item_type=VLARRAY)
        array = SharedDataResult(item_type=ARRAY, data=npearray)

        traj.v_standard_result = StorageDataResult
        traj.f_add_result('g.arrays', carray=carray, earray=earray, vlarray=vlarray, array=array,
                          comment='the arrays')

        with self.assertRaises(Exception):
            traj.f_store()

        with self.assertRaises(Exception):
            check_hdf5_init(vlarray)

        traj.arrays['vlarray'] = SharedDataResult(item_type=VLARRAY, obj=thevlarray)

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
            check_hdf5_init(SharedDataResult(item_type=TABLE))


class StorageDataEnvironmentTest(TrajectoryComparator):

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
        a = SharedDataResult(item_type=ARRAY, obj=da_data)
        ca = SharedDataResult(item_type=CARRAY, obj=da_data)
        ea = SharedDataResult(item_type=EARRAY, shape=(0, 10), atom=pt.FloatAtom(shape=()),
                        expectedrows=length)
        vla = SharedDataResult(item_type=VLARRAY, atom=pt.FloatAtom(shape=()))

        s1 = traj.f_add_result(StorageDataResult, 'daarrays', a=a, ca=ca, ea=ea, vla=vla,
                               comment='Arrays')

        t1 = SharedDataResult(description={'idx': pt.IntCol(), 'run_name': pt.StringCol(30)},
                        expectedrows=length)

        t2 = SharedDataResult(description={'run_name': pt.StringCol(3000)})

        s2 = traj.f_add_result(StorageDataResult, 'tabs', t1=t1, t2=t2)

        traj.f_store()

        with s2.f_context() as cm:
            for run_name in self.traj.f_get_run_names():
                row = t2.row
                row['run_name'] = run_name
                row.append()
            t2.flush()


    def setUp(self):
        self.set_mode()

        logging.basicConfig(level = logging.INFO)


        self.logfolder = make_temp_file(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))

        random.seed()
        self.trajname = make_trajectory_name(self)
        self.filename = make_temp_file(os.path.join('experiments',
                                                    'tests',
                                                    'HDF5',
                                                    'test%s.hdf5' % self.trajname))

        env = Environment(trajectory=self.trajname, filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
                          log_stdout=False,
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
        newtraj.f_load(name=trajectory_name, load_parameters=2,
                       load_derived_parameters=2,load_results=2,
                       load_other_data=2,
                       index=trajectory_index, as_new=as_new)
        return newtraj

    def check_insertions(self, traj):
        daarrays = traj.daarrays
        length = len(traj)
        self.assertTrue(length > 10)
        with daarrays.f_context() as cm:
            for idx in range(1, length):
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

        tabs.f_open_store()
        t1 = tabs.t1
        self.assertTrue(len(t1) == length)

        for row in t1:
            run_name = row['run_name']
            idx = row['idx']
            self.assertTrue(traj.f_idx_to_run(run_name) == idx)

    def test_run(self):

        self.explore(self.traj)
        self.add_array_params(self.traj)

        self.traj.f_add_parameter('TEST', 'test_run')

        self.env.f_run(write_into_shared_storage)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        self.check_insertions(self.traj)
        self.check_insertions(newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        print('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 2.0, 'Size is %sMB > 2MB' % str(size_in_mb))

    def test_run_large(self):

        self.explore(self.traj, trials=30)
        self.add_array_params(self.traj)

        self.traj.f_add_parameter('TEST', 'test_run')

        self.env.f_run(write_into_shared_storage)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        self.check_insertions(self.traj)
        self.check_insertions(newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        print('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 10.0, 'Size is %sMB > 10MB' % str(size_in_mb))

    def add_matrix_params(self, traj):
        shape=(300,301,305)
        m1 = SharedDataResult(obj=np.random.rand(*shape))
        m2 = SharedDataResult(obj=np.random.rand(*shape))
        traj.f_add_result(StorageDataResult, 'matrices', m1=m1, m2=m2)
        traj.f_store()


    def check_matrices(self, traj):
        length = len(traj)
        self.assertTrue(self.length == length)
        matrices = traj.matrices
        for irun in range(length):
            with matrices.f_context() as cm:
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
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        self.check_matrices(self.traj)
        self.check_matrices(newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        print('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 400.0, 'Size is %sMB > 400MB' % str(size_in_mb))


class MultiprocStorageLockTest(StorageDataEnvironmentTest):

    # def test_run(self):
    #     super(MultiprocLockTest, self).test_run()

    def set_mode(self):
        StorageDataEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True

class MultiprocStorageNoPoolLockTest(StorageDataEnvironmentTest):

     def set_mode(self):
        StorageDataEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False

if __name__ == '__main__':
    make_run()