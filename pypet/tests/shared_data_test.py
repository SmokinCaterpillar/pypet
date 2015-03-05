__author__ = 'Robert Meyer'

import numpy as np
import tables as pt
import os
import platform
import logging
import random
import scipy.sparse as spsp
import pandas as pd

from pypet.shareddata import *
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


class StorageDataTrajectoryTests(TrajectoryComparator):

    def test_converions(self):
        filename = make_temp_file('hdf5manipulation.hdf5')
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

        array = make_ordinary_result(array, new_data_name='super')
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        array = traj.array
        self.assertTrue(isinstance(array, Result))#
        thedata[2,2] = 10
        self.assertTrue(np.all(array.super == thedata))

        t1 = traj.t1
        t1 = make_ordinary_result(t1)
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        t1 = traj.t1
        self.assertTrue(isinstance(t1, ObjectTable))#
        self.assertTrue(np.all(t1['huhu'][0] == np.ones(3)))

        df = traj.df
        df = make_ordinary_result(df)
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
        listres = make_ordinary_result(listres, new_data_name='yuppy')
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

        mytuple = make_ordinary_result(mytuple, new_data_name='k')
        traj = load_trajectory(name=trajname, filename=filename, load_all=2)
        mytuple = traj.mytuple
        self.assertTrue(isinstance(mytuple.k, tuple))
        self.assertTrue(mytuple.k[2] == 3)

        myframe = traj.myframe
        myframe = make_shared_result(myframe, traj)

        theframe = myframe.f_read()
        self.assertTrue(theframe['answer'][0] == 42)

        myframe = make_ordinary_result(myframe, new_data_name='jj')
        traj.f_load_item(myframe)
        self.assertTrue(myframe.jj['answer'][0] == 42)

        mytable = traj.f_get('mytable')
        mytable = make_shared_result(mytable, traj)

        self.assertTrue(isinstance(mytable, SharedTableResult))
        rows = mytable.f_read()

        self.assertTrue(rows[0][0] == 42)

        mytable = make_ordinary_result(mytable, new_data_name='jup')

        traj.f_load_item(mytable)

        self.assertTrue(isinstance(mytable, Result))
        self.assertTrue(mytable.jup['answer'][0] == 42)


    def test_storing_and_manipulating(self):
        filename = make_temp_file('hdf5manipulation.hdf5')
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
        filename = make_temp_file('hdf5compacting.hdf5')
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
        print('Filesize is %s' % str(size))
        name_wo_ext, ext = os.path.splitext(filename)
        backup_file_name = name_wo_ext + '_backup' + ext
        code = compact_hdf5_file(filename, keep_backup=True)
        if code != 0:
            raise RuntimeError('ptrepack fail')
        backup_size = os.path.getsize(backup_file_name)
        self.assertTrue(backup_size == size)
        new_size = os.path.getsize(filename)
        print('New filesize is %s' % str(new_size))
        self.assertTrue(new_size < size, "%s > %s" %(str(new_size), str(size)))

    def test_all_arrays(self):
        filename = make_temp_file('hdf5arrays.hdf5')
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
        filename = make_temp_file('hdf5errors.hdf5')
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
        filename = make_temp_file('hdf5errors.hdf5')
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
        print('Size is %sMB' % str(size_in_mb))
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
        print('Size is %sMB' % str(size_in_mb))
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